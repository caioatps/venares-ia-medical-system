"""Acesso a API de gravacoes em nuvem do Zoom."""

from __future__ import annotations

import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import requests

from ..config import Ambiente
from ..logging_setup import log
from .auth import TokenZoom

BASE = "https://api.zoom.us/v2"
_LOG = log(__name__)

# Tipos de arquivo que interessam na resposta do Zoom.
TIPO_VIDEO = "MP4"
TIPO_AUDIO = "M4A"
TIPO_TRANSCRICAO = "TRANSCRIPT"
TIPO_LEGENDA = "CC"
TIPO_CHAT = "CHAT"


class ErroZoom(RuntimeError):
    pass


@dataclass(frozen=True)
class ArquivoGravacao:
    id: str
    tipo: str
    extensao: str
    tamanho: int
    url_download: str
    status: str
    tipo_gravacao: str = ""

    @property
    def pronto(self) -> bool:
        # O Zoom usa "completed" para arquivos ja processados.
        return self.status.lower() in {"completed", ""}


@dataclass(frozen=True)
class Gravacao:
    uuid: str
    meeting_id: str
    titulo: str
    inicio: str
    duracao_min: int
    host_email: str
    arquivos: list[ArquivoGravacao]
    bruto: dict[str, Any]

    def _melhor(self, tipo: str) -> ArquivoGravacao | None:
        candidatos = [a for a in self.arquivos if a.tipo.upper() == tipo and a.pronto]
        if not candidatos:
            return None
        # Prefere a gravacao de tela compartilhada + camera quando houver varias.
        prioridade = {
            "shared_screen_with_speaker_view": 0,
            "shared_screen_with_gallery_view": 1,
            "speaker_view": 2,
            "gallery_view": 3,
            "active_speaker": 4,
            "shared_screen": 5,
        }
        return sorted(
            candidatos,
            key=lambda a: (prioridade.get(a.tipo_gravacao, 9), -a.tamanho),
        )[0]

    @property
    def video(self) -> ArquivoGravacao | None:
        return self._melhor(TIPO_VIDEO)

    @property
    def transcricao(self) -> ArquivoGravacao | None:
        return self._melhor(TIPO_TRANSCRICAO) or self._melhor(TIPO_LEGENDA)

    @property
    def audio(self) -> ArquivoGravacao | None:
        return self._melhor(TIPO_AUDIO)


def _codificar_uuid(uuid: str) -> str:
    """UUIDs de reuniao com '/' ou '//' precisam ser codificados duas vezes."""
    if uuid.startswith("/") or "//" in uuid:
        return urllib.parse.quote(urllib.parse.quote(uuid, safe=""), safe="")
    return urllib.parse.quote(uuid, safe="")


def _para_gravacao(dados: dict[str, Any]) -> Gravacao:
    arquivos = [
        ArquivoGravacao(
            id=str(a.get("id", "")),
            tipo=str(a.get("file_type", "")),
            extensao=str(a.get("file_extension", "")).lower(),
            tamanho=int(a.get("file_size") or 0),
            url_download=str(a.get("download_url", "")),
            status=str(a.get("status", "")),
            tipo_gravacao=str(a.get("recording_type", "")),
        )
        for a in dados.get("recording_files") or []
    ]
    return Gravacao(
        uuid=str(dados.get("uuid", "")),
        meeting_id=str(dados.get("id", "")),
        titulo=str(dados.get("topic", "")).strip(),
        inicio=str(dados.get("start_time", "")),
        duracao_min=int(dados.get("duration") or 0),
        host_email=str(dados.get("host_email", "")),
        arquivos=arquivos,
        bruto=dados,
    )


class ClienteZoom:
    def __init__(self, ambiente: Ambiente, tempo_limite_s: int = 60) -> None:
        self._token = TokenZoom(ambiente)
        self._tempo_limite = tempo_limite_s
        self._sessao = requests.Session()

    # -- baixo nivel --------------------------------------------------------
    def _requisitar(self, metodo: str, caminho: str, **kwargs: Any) -> requests.Response:
        url = caminho if caminho.startswith("http") else f"{BASE}{caminho}"
        for tentativa in range(3):
            cabecalhos = {"Authorization": f"Bearer {self._token.obter()}"}
            cabecalhos.update(kwargs.pop("headers", {}))
            resposta = self._sessao.request(
                metodo, url, headers=cabecalhos, timeout=self._tempo_limite, **kwargs
            )
            if resposta.status_code == 401 and tentativa == 0:
                self._token.invalidar()
                continue
            if resposta.status_code == 429:
                espera = int(resposta.headers.get("Retry-After", 5)) * (tentativa + 1)
                _LOG.warning("Zoom limitou a taxa; aguardando %ss", espera)
                time.sleep(espera)
                continue
            return resposta
        return resposta

    # -- alto nivel ---------------------------------------------------------
    def gravacao(self, uuid_ou_id: str) -> Gravacao:
        """Busca os arquivos de uma gravacao pelo UUID (preferencial) ou ID."""
        resposta = self._requisitar("GET", f"/meetings/{_codificar_uuid(uuid_ou_id)}/recordings")
        if resposta.status_code == 404:
            raise ErroZoom(f"Gravacao nao encontrada no Zoom: {uuid_ou_id}")
        if resposta.status_code != 200:
            raise ErroZoom(
                f"Erro ao consultar gravacao {uuid_ou_id} "
                f"({resposta.status_code}): {resposta.text[:500]}"
            )
        return _para_gravacao(resposta.json())

    def gravacoes_recentes(
        self, usuario: str = "me", *, de: str | None = None, ate: str | None = None
    ) -> Iterator[Gravacao]:
        """Percorre as gravacoes em nuvem de um usuario (paginado)."""
        parametros: dict[str, Any] = {"page_size": 100}
        if de:
            parametros["from"] = de
        if ate:
            parametros["to"] = ate
        while True:
            resposta = self._requisitar(
                "GET", f"/users/{urllib.parse.quote(usuario)}/recordings", params=parametros
            )
            if resposta.status_code != 200:
                raise ErroZoom(
                    f"Erro ao listar gravacoes ({resposta.status_code}): {resposta.text[:500]}"
                )
            dados = resposta.json()
            for reuniao in dados.get("meetings") or []:
                yield _para_gravacao(reuniao)
            proximo = dados.get("next_page_token")
            if not proximo:
                return
            parametros["next_page_token"] = proximo

    def baixar(self, arquivo: ArquivoGravacao, destino: Path) -> Path:
        """Baixa um arquivo da gravacao em streaming (video pode ter GBs)."""
        destino.parent.mkdir(parents=True, exist_ok=True)
        parcial = destino.with_suffix(destino.suffix + ".parcial")
        _LOG.info("Baixando %s (%s, %.1f MB)", destino.name, arquivo.tipo, arquivo.tamanho / 1e6)
        with self._sessao.get(
            arquivo.url_download,
            headers={"Authorization": f"Bearer {self._token.obter()}"},
            stream=True,
            timeout=self._tempo_limite,
            allow_redirects=True,
        ) as resposta:
            if resposta.status_code != 200:
                raise ErroZoom(
                    f"Falha ao baixar {arquivo.tipo} ({resposta.status_code}): "
                    f"{resposta.text[:300]}"
                )
            # iter_content (e nao resposta.raw) porque ele desfaz o
            # content-encoding: um .vtt vem gzipado da CDN do Zoom.
            with parcial.open("wb") as saida:
                for pedaco in resposta.iter_content(chunk_size=1024 * 1024):
                    if pedaco:
                        saida.write(pedaco)
        baixado = parcial.stat().st_size
        if arquivo.tamanho and baixado < arquivo.tamanho * 0.95:
            parcial.unlink(missing_ok=True)
            raise ErroZoom(
                f"Download incompleto de {arquivo.tipo}: {baixado} de {arquivo.tamanho} bytes"
            )
        parcial.replace(destino)
        return destino

    def apagar_gravacao(self, uuid: str, *, para_lixeira: bool = True) -> None:
        resposta = self._requisitar(
            "DELETE",
            f"/meetings/{_codificar_uuid(uuid)}/recordings",
            params={"action": "trash" if para_lixeira else "delete"},
        )
        if resposta.status_code not in (200, 204):
            raise ErroZoom(
                f"Falha ao apagar gravacao {uuid} "
                f"({resposta.status_code}): {resposta.text[:300]}"
            )
