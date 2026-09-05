"""Fluxo completo da aula, com Zoom, Drive, Claude e WhatsApp simulados.

Verifica exatamente o que voce faz hoje na mao: identificar a mentoria,
achar o proximo numero na pasta, nomear com data e mentoria, subir os dois
arquivos na pasta certa e avisar o TI.
"""

from __future__ import annotations


from pathlib import Path

import pytest

from venares_aulas import db
from venares_aulas.config import (
    Ambiente,
    Config,
    ConfigNotificacao,
    ConfigPdf,
    ConfigResumo,
    ConfigWhatsapp,
    ConfigZoom,
    Mentoria,
    Nomeacao,
)
from venares_aulas.db import Banco
from venares_aulas.drive.cliente import ArquivoDrive
from venares_aulas.pipeline import Pipeline
from venares_aulas.resumo.modelos import ResumoAula, Topico
from venares_aulas.transcricao.glossario import Glossario, Termo
from venares_aulas.zoom.cliente import ArquivoGravacao, Gravacao

FIXTURE = Path(__file__).parent / "fixtures" / "aula_exemplo.vtt"

START = Mentoria(id="start", nome="Mentoria Start", palavras_chave=["start"], pasta_drive_id="pasta_start")
SURGICAL = Mentoria(
    id="surgical", nome="Mentoria Surgical", palavras_chave=["surgical", "cirurgica"], pasta_drive_id="pasta_surgical"
)


# --------------------------------------------------------------------------
# dublês
# --------------------------------------------------------------------------
class ZoomFalso:
    def __init__(self, gravacao: Gravacao) -> None:
        self.gravacao_alvo = gravacao
        self.baixados: list[str] = []
        self.apagou = False

    def gravacao(self, uuid: str) -> Gravacao:  # noqa: D102
        return self.gravacao_alvo

    def baixar(self, arquivo: ArquivoGravacao, destino: Path) -> Path:
        destino.parent.mkdir(parents=True, exist_ok=True)
        if arquivo.tipo == "TRANSCRIPT":
            destino.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            destino.write_bytes(b"video-falso" * 100)
        self.baixados.append(arquivo.tipo)
        return destino

    def apagar_gravacao(self, uuid: str, **kwargs) -> None:
        self.apagou = True


class DriveFalso:
    def __init__(self, conteudo: dict[str, list[str]]) -> None:
        self.conteudo = conteudo
        self.enviados: list[tuple[str, str]] = []  # (nome, pasta)
        self.pastas_criadas: list[tuple[str, str]] = []

    def nomes_na_pasta(self, pasta_id: str, **kwargs) -> list[str]:
        return list(self.conteudo.get(pasta_id, []))

    def criar_pasta(self, nome: str, pai_id: str, **kwargs) -> ArquivoDrive:
        self.pastas_criadas.append((nome, pai_id))
        return ArquivoDrive(id=f"sub_{nome}", nome=nome, mime="application/vnd.google-apps.folder", link=f"https://drive/{nome}")

    def enviar(self, caminho: Path, *, nome: str, pasta_id: str, **kwargs) -> ArquivoDrive:
        assert caminho.exists(), f"{nome} nao existe no disco na hora do upload"
        assert caminho.stat().st_size > 0
        self.enviados.append((nome, pasta_id))
        return ArquivoDrive(id=f"id_{nome}", nome=nome, mime="", link=f"https://drive.google.com/file/{nome}")


class NotificadorFalso:
    def __init__(self) -> None:
        self.avisos: list = []
        self.erros: list[tuple[str, str]] = []

    def avisar_aula(self, aviso) -> list[str]:
        self.avisos.append(aviso)
        return ["msg-1"]

    def avisar_erro(self, destinatarios, titulo, mensagem) -> list[str]:
        self.erros.append((titulo, mensagem))
        return []


class GeradorFalso:
    def __init__(self, *args, **kwargs) -> None:
        self.chamado_com = None

    def gerar(self, transcricao, **kwargs) -> ResumoAula:
        self.chamado_com = {"transcricao": transcricao, **kwargs}
        GeradorFalso.ultimo = self
        return ResumoAula(
            titulo="Reposicao hormonal masculina",
            resumo_executivo="Resumo da aula gerado no teste.",
            topicos=[Topico(titulo="Diagnostico", timestamp="00:04", pontos=["Ponto um."])],
            pontos_chave=["Confirmar com duas dosagens."],
        )


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def montar_gravacao(titulo: str, *, com_transcricao: bool = True, duracao: int = 95) -> Gravacao:
    arquivos = [
        ArquivoGravacao(
            id="v1", tipo="MP4", extensao="mp4", tamanho=1000,
            url_download="https://zoom/v", status="completed",
            tipo_gravacao="shared_screen_with_speaker_view",
        )
    ]
    if com_transcricao:
        arquivos.append(
            ArquivoGravacao(
                id="t1", tipo="TRANSCRIPT", extensao="vtt", tamanho=100,
                url_download="https://zoom/t", status="completed",
            )
        )
    return Gravacao(
        uuid="uuid-aula", meeting_id="812", titulo=titulo,
        inicio="2026-03-17T13:00:00Z", duracao_min=duracao,
        host_email="dr@exemplo.com", arquivos=arquivos, bruto={},
    )


@pytest.fixture
def config() -> Config:
    return Config(
        fuso_horario="America/Sao_Paulo", idioma="pt-BR",
        mentorias=[START, SURGICAL], mentoria_padrao=None,
        nomeacao=Nomeacao(), zoom=ConfigZoom(), resumo=ConfigResumo(),
        pdf=ConfigPdf(rodape="Uso exclusivo."),
        notificacao=ConfigNotificacao(whatsapp=ConfigWhatsapp(ativo=False)),
    )


@pytest.fixture
def ambiente(tmp_path) -> Ambiente:
    campos = dict.fromkeys(
        [
            "zoom_account_id", "zoom_client_id", "zoom_client_secret", "zoom_secret_token",
            "anthropic_api_key", "google_client_id", "google_client_secret",
            "google_refresh_token", "google_service_account_file", "google_delegar_para",
            "meta_whatsapp_token", "meta_whatsapp_phone_number_id", "twilio_account_sid",
            "twilio_auth_token", "twilio_whatsapp_from", "admin_api_key",
        ],
        "",
    )
    return Ambiente(dir_trabalho=tmp_path / "trabalho", banco=tmp_path / "b.db", **campos)


def montar_pipeline(config, ambiente, monkeypatch, *, gravacao, conteudo_drive):
    monkeypatch.setattr("venares_aulas.pipeline.GeradorResumo", GeradorFalso)
    glossario = Glossario(
        termos=[Termo(correto="testosterona", variacoes=["testoterona"])],
        remover_frases=["esta reuniao esta sendo gravada"],
    )
    pipeline = Pipeline(config, ambiente, banco=Banco(ambiente.banco), glossario=glossario)
    pipeline._zoom = ZoomFalso(gravacao)
    pipeline._drive = DriveFalso(conteudo_drive)
    pipeline._notificador = NotificadorFalso()
    return pipeline


# --------------------------------------------------------------------------
# testes
# --------------------------------------------------------------------------
def test_aula_start_vira_a_proxima_da_sequencia(config, ambiente, monkeypatch):
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Start - hormonios"),
        conteudo_drive={
            "pasta_start": [
                "Aula 01 - 03-02-2026 - Mentoria Start.mp4",
                "Aula 02 - 10-02-2026 - Mentoria Start.mp4",
                "Aula 03 - 17-02-2026 - Mentoria Start.mp4",
            ],
            "pasta_surgical": ["Aula 07 - x.mp4"],
        },
    )
    resultado = pipeline.processar("uuid-aula")

    assert resultado.mentoria == "Mentoria Start"
    assert resultado.numero == 4
    assert resultado.data_aula.strftime("%d/%m/%Y") == "17/03/2026"
    assert resultado.nome_base == "Aula 04 - 17-03-2026 - Mentoria Start"

    enviados = dict(pipeline.drive.enviados)
    assert set(enviados) == {
        "Aula 04 - 17-03-2026 - Mentoria Start.mp4",
        "Aula 04 - 17-03-2026 - Mentoria Start - Resumo.pdf",
    }
    # Os dois foram para a pasta da Start, nao para a da Surgical.
    assert set(enviados.values()) == {"pasta_start"}


def test_aula_surgical_vai_para_a_outra_pasta(config, ambiente, monkeypatch):
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Surgical - modulo 2"),
        conteudo_drive={"pasta_start": ["Aula 09 - x.mp4"], "pasta_surgical": ["Aula 01 - y.mp4"]},
    )
    resultado = pipeline.processar("uuid-aula")
    assert resultado.numero == 2  # a sequencia da Surgical, nao a da Start
    assert all(pasta == "pasta_surgical" for _, pasta in pipeline.drive.enviados)


def test_pasta_vazia_comeca_na_aula_um(config, ambiente, monkeypatch):
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Aula cirurgica"),
        conteudo_drive={"pasta_surgical": []},
    )
    assert pipeline.processar("uuid-aula").numero == 1


def test_ti_recebe_os_links_e_o_numero(config, ambiente, monkeypatch):
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Start"),
        conteudo_drive={"pasta_start": ["Aula 05 - x.mp4"]},
    )
    pipeline.processar("uuid-aula")
    aviso = pipeline._notificador.avisos[0]
    assert aviso.mentoria == "Mentoria Start"
    assert aviso.numero == 6
    assert aviso.data == "17/03/2026"
    assert aviso.link_video.endswith(".mp4")
    assert aviso.link_resumo.endswith(".pdf")
    assert "Aula 06" in aviso.texto()


def test_glossario_chega_corrigido_no_resumo(config, ambiente, monkeypatch):
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Start"),
        conteudo_drive={"pasta_start": []},
    )
    pipeline.processar("uuid-aula")
    texto = GeradorFalso.ultimo.chamado_com["transcricao"].para_texto()
    assert "testosterona" in texto and "testoterona" not in texto
    assert "esta reuniao esta sendo gravada" not in texto
    assert GeradorFalso.ultimo.chamado_com["mentoria"] == "Mentoria Start"
    assert GeradorFalso.ultimo.chamado_com["data_aula"] == "17/03/2026"


def test_banco_registra_conclusao(config, ambiente, monkeypatch):
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Start"),
        conteudo_drive={"pasta_start": []},
    )
    pipeline.processar("uuid-aula")
    trabalho = pipeline.banco.obter("uuid-aula")
    assert trabalho.status == db.CONCLUIDO
    assert trabalho.mentoria == "start"
    assert trabalho.numero_aula == 1
    assert trabalho.drive_pdf_id and trabalho.drive_video_id


def test_nao_processa_duas_vezes(config, ambiente, monkeypatch):
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Start"),
        conteudo_drive={"pasta_start": []},
    )
    pipeline.processar("uuid-aula")
    from venares_aulas.pipeline import AulaIgnorada

    with pytest.raises(AulaIgnorada, match="ja foi processada"):
        pipeline.processar("uuid-aula")


def test_area_temporaria_e_limpa(config, ambiente, monkeypatch):
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Start"),
        conteudo_drive={"pasta_start": []},
    )
    pipeline.processar("uuid-aula")
    restos = list(ambiente.dir_trabalho.rglob("*")) if ambiente.dir_trabalho.exists() else []
    assert restos == []


def test_transcricao_ausente_reagenda_em_vez_de_falhar(config, ambiente, monkeypatch):
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Start", com_transcricao=False),
        conteudo_drive={"pasta_start": []},
    )
    assert pipeline.processar_com_retentativa("uuid-aula") is None
    trabalho = pipeline.banco.obter("uuid-aula")
    assert trabalho.status == db.PENDENTE
    assert trabalho.proxima_tentativa > 0
    assert pipeline._notificador.erros == []  # ainda nao e para incomodar ninguem


def test_titulo_sem_mentoria_avisa_e_nao_sobe_nada(config, ambiente, monkeypatch):
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Reuniao de quinta-feira"),
        conteudo_drive={"pasta_start": []},
    )
    assert pipeline.processar_com_retentativa("uuid-aula") is None
    assert pipeline.banco.obter("uuid-aula").status == db.ERRO
    assert pipeline.drive.enviados == []
    assert pipeline._notificador.erros, "o responsavel precisa ser avisado"


def test_reuniao_curta_e_ignorada(config, ambiente, monkeypatch):
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Start - alinhamento", duracao=5),
        conteudo_drive={"pasta_start": []},
    )
    assert pipeline.processar_com_retentativa("uuid-aula") is None
    assert pipeline.banco.obter("uuid-aula").status == db.IGNORADO
    assert pipeline.drive.enviados == []


def test_titulo_de_teste_e_ignorado(ambiente, monkeypatch):
    config = Config(
        fuso_horario="America/Sao_Paulo", idioma="pt-BR",
        mentorias=[START, SURGICAL], mentoria_padrao=None, nomeacao=Nomeacao(),
        zoom=ConfigZoom(ignorar_titulos=["teste"]), resumo=ConfigResumo(),
        pdf=ConfigPdf(), notificacao=ConfigNotificacao(whatsapp=ConfigWhatsapp(ativo=False)),
    )
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Start - teste de audio"),
        conteudo_drive={"pasta_start": []},
    )
    assert pipeline.processar_com_retentativa("uuid-aula") is None
    assert pipeline.banco.obter("uuid-aula").status == db.IGNORADO


def test_subpasta_por_aula_quando_configurado(ambiente, monkeypatch):
    config = Config(
        fuso_horario="America/Sao_Paulo", idioma="pt-BR",
        mentorias=[START, SURGICAL], mentoria_padrao=None,
        nomeacao=Nomeacao(criar_subpasta_por_aula=True), zoom=ConfigZoom(),
        resumo=ConfigResumo(), pdf=ConfigPdf(),
        notificacao=ConfigNotificacao(whatsapp=ConfigWhatsapp(ativo=False)),
    )
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Start"),
        conteudo_drive={"pasta_start": ["Aula 02 - antiga"]},
    )
    pipeline.processar("uuid-aula")
    assert pipeline.drive.pastas_criadas == [("Aula 03 - 17-03-2026 - Mentoria Start", "pasta_start")]
    assert all(pasta.startswith("sub_") for _, pasta in pipeline.drive.enviados)


def test_pdf_gerado_tem_conteudo(config, ambiente, monkeypatch):
    """O PDF que sobe precisa ser um PDF de verdade, nao um arquivo vazio."""
    tamanhos: dict[str, int] = {}
    pipeline = montar_pipeline(
        config, ambiente, monkeypatch,
        gravacao=montar_gravacao("Mentoria Start"),
        conteudo_drive={"pasta_start": []},
    )
    enviar_original = pipeline.drive.enviar

    def espiar(caminho: Path, *, nome: str, pasta_id: str, **kwargs):
        tamanhos[nome] = caminho.stat().st_size
        if nome.endswith(".pdf"):
            assert caminho.read_bytes()[:4] == b"%PDF"
        return enviar_original(caminho, nome=nome, pasta_id=pasta_id, **kwargs)

    pipeline.drive.enviar = espiar
    pipeline.processar("uuid-aula")
    pdf = next(n for n in tamanhos if n.endswith(".pdf"))
    assert tamanhos[pdf] > 3000
