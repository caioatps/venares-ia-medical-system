"""Orquestracao ponta a ponta de uma aula gravada.

Zoom (video + transcricao) -> limpeza pelo glossario -> resumo com Claude ->
PDF -> Google Drive na pasta certa com numeracao sequencial -> WhatsApp.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import db
from .config import Ambiente, Config
from .db import Banco
from .logging_setup import log
from .nomeacao import (
    ErroClassificacao,
    classificar_mentoria,
    montar_nomes,
    proximo_numero,
)
from .notificacao.whatsapp import AvisoAula, NotificadorWhatsapp
from .drive.cliente import ClienteDrive, ErroDrive
from .pdf.render import gerar_pdf, renderizar_html
from .resumo.gerador import GeradorResumo
from .resumo.modelos import ResumoAula
from .transcricao.glossario import Glossario, aplicar_glossario
from .transcricao.vtt import carregar_transcricao
from .zoom.cliente import ClienteZoom, ErroZoom, Gravacao

_LOG = log(__name__)


class TranscricaoIndisponivel(RuntimeError):
    """A transcricao ainda nao foi publicada pelo Zoom - vale tentar de novo."""


class AulaIgnorada(RuntimeError):
    """A gravacao nao e uma aula (teste, reuniao curta, titulo na lista de ignorados)."""


@dataclass
class ResultadoAula:
    uuid: str
    mentoria: str
    numero: int
    data_aula: datetime
    nome_base: str
    link_video: str
    link_resumo: str
    link_pasta: str


class Pipeline:
    def __init__(
        self,
        config: Config,
        ambiente: Ambiente,
        *,
        banco: Banco | None = None,
        glossario: Glossario | None = None,
    ) -> None:
        self.config = config
        self.ambiente = ambiente
        self.banco = banco or Banco(ambiente.banco)
        self.glossario = glossario if glossario is not None else Glossario.carregar()
        self._zoom: ClienteZoom | None = None
        self._drive: ClienteDrive | None = None
        self._notificador = NotificadorWhatsapp(config.notificacao.whatsapp, ambiente)

    # -- clientes preguicosos ----------------------------------------------
    @property
    def zoom(self) -> ClienteZoom:
        if self._zoom is None:
            self._zoom = ClienteZoom(self.ambiente)
        return self._zoom

    @property
    def drive(self) -> ClienteDrive:
        if self._drive is None:
            self._drive = ClienteDrive(self.ambiente)
        return self._drive

    # -- utilidades ---------------------------------------------------------
    def _fuso(self) -> ZoneInfo:
        return ZoneInfo(self.config.fuso_horario)

    def _data_local(self, inicio_iso: str) -> datetime:
        if not inicio_iso:
            return datetime.now(self._fuso())
        try:
            bruto = datetime.fromisoformat(inicio_iso.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(self._fuso())
        if bruto.tzinfo is None:
            bruto = bruto.replace(tzinfo=timezone.utc)
        return bruto.astimezone(self._fuso())

    def _deve_ignorar(self, gravacao: Gravacao) -> str | None:
        from .transcricao.glossario import normalizar

        titulo = normalizar(gravacao.titulo)
        for padrao in self.config.zoom.ignorar_titulos:
            if normalizar(padrao) and normalizar(padrao) in titulo:
                return f"titulo casa com o filtro '{padrao}'"
        if gravacao.duracao_min and gravacao.duracao_min < self.config.zoom.duracao_minima_min:
            return (
                f"duracao de {gravacao.duracao_min} min abaixo do minimo "
                f"({self.config.zoom.duracao_minima_min} min)"
            )
        return None

    # -- fluxo principal ----------------------------------------------------
    def processar(self, uuid: str, *, forcar: bool = False) -> ResultadoAula:
        if not forcar and self.banco.ja_concluido(uuid):
            raise AulaIgnorada(f"Gravacao {uuid} ja foi processada.")

        gravacao = self.zoom.gravacao(uuid)
        self.banco.registrar(
            uuid,
            meeting_id=gravacao.meeting_id,
            titulo=gravacao.titulo,
            inicio=gravacao.inicio,
        )
        self.banco.incrementar_tentativa(uuid)

        motivo = self._deve_ignorar(gravacao)
        if motivo and not forcar:
            self.banco.atualizar(uuid, status=db.IGNORADO, erro=motivo)
            raise AulaIgnorada(f"{gravacao.titulo!r} ignorada: {motivo}")

        mentoria = classificar_mentoria(gravacao.titulo, self.config)
        data_aula = self._data_local(gravacao.inicio)
        _LOG.info(
            "Processando %r -> %s (%s)",
            gravacao.titulo,
            mentoria.nome,
            data_aula.strftime("%d/%m/%Y"),
        )

        arquivo_video = gravacao.video
        arquivo_transcricao = gravacao.transcricao
        if arquivo_video is None:
            raise TranscricaoIndisponivel("O video ainda nao terminou de processar no Zoom.")
        if arquivo_transcricao is None:
            raise TranscricaoIndisponivel(
                "A transcricao ainda nao esta disponivel na nuvem do Zoom."
            )

        trabalho_dir = self.ambiente.dir_trabalho / _sanitizar_id(uuid)
        trabalho_dir.mkdir(parents=True, exist_ok=True)
        try:
            return self._executar_etapas(
                uuid=uuid,
                gravacao=gravacao,
                mentoria=mentoria,
                data_aula=data_aula,
                trabalho_dir=trabalho_dir,
                arquivo_video=arquivo_video,
                arquivo_transcricao=arquivo_transcricao,
            )
        finally:
            shutil.rmtree(trabalho_dir, ignore_errors=True)

    def _executar_etapas(
        self,
        *,
        uuid: str,
        gravacao: Gravacao,
        mentoria,
        data_aula: datetime,
        trabalho_dir: Path,
        arquivo_video,
        arquivo_transcricao,
    ) -> ResultadoAula:
        # 1. Baixa a transcricao (leve) antes do video (pesado).
        caminho_vtt = self.zoom.baixar(arquivo_transcricao, trabalho_dir / "transcricao.vtt")
        bruto = caminho_vtt.read_text(encoding="utf-8", errors="replace")
        transcricao = carregar_transcricao(bruto)
        if not transcricao.turnos:
            raise TranscricaoIndisponivel("A transcricao baixada esta vazia.")

        # 2. Glossario: remove ruido e corrige termos, turno a turno, para
        #    preservar os tempos e os falantes.
        transcricao_corrigida = aplicar_glossario(transcricao, self.glossario)

        # 3. Resumo com o Claude.
        gerador = GeradorResumo(self.config.resumo, api_key=self.ambiente.anthropic_api_key or None)
        resumo: ResumoAula = gerador.gerar(
            transcricao_corrigida,
            titulo_zoom=gravacao.titulo,
            mentoria=mentoria.nome,
            data_aula=data_aula.strftime("%d/%m/%Y"),
            duracao_min=gravacao.duracao_min,
            glossario=self.glossario,
        )

        # 4. Numeracao sequencial, lida da propria pasta do Drive.
        nomes_existentes = self.drive.nomes_na_pasta(
            mentoria.pasta_drive_id,
            drive_compartilhado_id=mentoria.drive_compartilhado_id,
            recursivo=self.config.nomeacao.criar_subpasta_por_aula,
        )
        numero = proximo_numero(
            nomes_existentes,
            self.config.nomeacao,
            reservados=self.banco.numeros_ja_usados(mentoria.id),
        )
        nomes = montar_nomes(
            numero=numero,
            data_aula=data_aula,
            mentoria=mentoria,
            titulo_zoom=gravacao.titulo,
            nomeacao=self.config.nomeacao,
            extensao_video=arquivo_video.extensao or "mp4",
        )
        self.banco.atualizar(uuid, mentoria=mentoria.id, numero_aula=numero)
        _LOG.info("Numeracao: aula %02d em %s", numero, mentoria.nome)

        # 5. PDF.
        html = renderizar_html(
            resumo=resumo,
            config_pdf=self.config.pdf,
            glossario=self.glossario,
            nomes=nomes,
            mentoria=mentoria.nome,
            titulo_zoom=gravacao.titulo,
            data_aula=data_aula,
            duracao_min=gravacao.duracao_min,
            palavras=transcricao_corrigida.total_palavras,
        )
        caminho_pdf = gerar_pdf(html, trabalho_dir / nomes.resumo)

        # 6. Video.
        caminho_video = self.zoom.baixar(arquivo_video, trabalho_dir / nomes.video)

        # 7. Upload.
        pasta_destino = mentoria.pasta_drive_id
        link_pasta = ""
        if nomes.pasta:
            subpasta = self.drive.criar_pasta(
                nomes.pasta,
                mentoria.pasta_drive_id,
                drive_compartilhado_id=mentoria.drive_compartilhado_id,
            )
            pasta_destino = subpasta.id
            link_pasta = subpasta.link

        enviado_video = self.drive.enviar(
            caminho_video,
            nome=nomes.video,
            pasta_id=pasta_destino,
            mime="video/mp4",
            drive_compartilhado_id=mentoria.drive_compartilhado_id,
        )
        enviado_pdf = self.drive.enviar(
            caminho_pdf,
            nome=nomes.resumo,
            pasta_id=pasta_destino,
            mime="application/pdf",
            drive_compartilhado_id=mentoria.drive_compartilhado_id,
        )

        self.banco.atualizar(
            uuid,
            status=db.CONCLUIDO,
            drive_video_id=enviado_video.id,
            drive_pdf_id=enviado_pdf.id,
            erro=None,
            extra={
                "titulo_resumo": resumo.titulo,
                "nome_base": nomes.base,
                "link_video": enviado_video.link,
                "link_resumo": enviado_pdf.link,
            },
        )

        # 8. Aviso ao responsavel de TI.
        self._notificador.avisar_aula(
            AvisoAula(
                mentoria=mentoria.nome,
                numero=numero,
                data=data_aula.strftime("%d/%m/%Y"),
                titulo=resumo.titulo or gravacao.titulo,
                link_video=enviado_video.link,
                link_resumo=enviado_pdf.link,
                link_pasta=link_pasta,
            )
        )

        # 9. Limpeza opcional da nuvem do Zoom.
        if self.config.zoom.apagar_da_nuvem_apos_upload:
            try:
                self.zoom.apagar_gravacao(uuid)
                _LOG.info("Gravacao movida para a lixeira do Zoom.")
            except ErroZoom as erro:
                _LOG.warning("Nao consegui apagar a gravacao no Zoom: %s", erro)

        return ResultadoAula(
            uuid=uuid,
            mentoria=mentoria.nome,
            numero=numero,
            data_aula=data_aula,
            nome_base=nomes.base,
            link_video=enviado_video.link,
            link_resumo=enviado_pdf.link,
            link_pasta=link_pasta,
        )

    # -- tratamento de falhas ----------------------------------------------
    def processar_com_retentativa(self, uuid: str, *, forcar: bool = False) -> ResultadoAula | None:
        """Executa e decide entre reagendar, desistir ou concluir.

        Devolve o resultado em caso de sucesso; None quando a aula foi
        ignorada ou reagendada para uma nova tentativa.
        """
        trabalho = self.banco.obter(uuid)
        try:
            return self.processar(uuid, forcar=forcar)
        except AulaIgnorada as erro:
            _LOG.info("%s", erro)
            return None
        except TranscricaoIndisponivel as erro:
            primeira = trabalho.primeira_vez_em if trabalho else time.time()
            limite_s = self.config.zoom.espera_maxima_transcricao_min * 60
            if time.time() - primeira < limite_s:
                espera = self.config.zoom.intervalo_nova_tentativa_min * 60
                _LOG.info("%s Nova tentativa em %d min.", erro, espera // 60)
                self.banco.marcar_erro(uuid, str(erro), reagendar_em_s=espera)
                return None
            self._falhar(uuid, f"Desisti de esperar a transcricao: {erro}")
            return None
        except ErroClassificacao as erro:
            self._falhar(uuid, str(erro))
            return None
        except (ErroZoom, ErroDrive) as erro:
            # Erros de infraestrutura merecem mais uma chance.
            tentativas = (trabalho.tentativas if trabalho else 0) + 1
            if tentativas < 4:
                self.banco.marcar_erro(uuid, str(erro), reagendar_em_s=300 * tentativas)
                _LOG.warning("Falha transitoria (%s). Nova tentativa agendada.", erro)
                return None
            self._falhar(uuid, str(erro))
            return None
        except Exception as erro:  # noqa: BLE001 - o pipeline nunca pode morrer calado
            _LOG.exception("Erro inesperado processando %s", uuid)
            self._falhar(uuid, f"{type(erro).__name__}: {erro}")
            return None

    def _falhar(self, uuid: str, mensagem: str) -> None:
        self.banco.marcar_erro(uuid, mensagem)
        trabalho = self.banco.obter(uuid)
        self._notificador.avisar_erro(
            self.config.notificacao.avisar_erros_para,
            (trabalho.titulo if trabalho else uuid) or uuid,
            mensagem,
        )

    def processar_pendentes(self, limite: int = 10) -> int:
        """Roda os trabalhos que estao aguardando nova tentativa."""
        pendentes = self.banco.pendentes_vencidos(limite=limite)
        for trabalho in pendentes:
            self.processar_com_retentativa(trabalho.uuid)
        return len(pendentes)


def _sanitizar_id(uuid: str) -> str:
    import hashlib

    return hashlib.sha1(uuid.encode("utf-8")).hexdigest()[:16]
