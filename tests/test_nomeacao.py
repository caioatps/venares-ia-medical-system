from datetime import datetime

import pytest

from venares_aulas.config import (
    Config,
    ConfigNotificacao,
    ConfigPdf,
    ConfigResumo,
    ConfigZoom,
    Mentoria,
    Nomeacao,
)
from venares_aulas.nomeacao import (
    ErroClassificacao,
    classificar_mentoria,
    montar_nomes,
    numeros_em_nomes,
    proximo_numero,
    sanitizar,
)

START = Mentoria(
    id="start",
    nome="Mentoria Start",
    palavras_chave=["start", "mentoria start"],
    pasta_drive_id="pasta_start",
)
SURGICAL = Mentoria(
    id="surgical",
    nome="Mentoria Surgical",
    palavras_chave=["surgical", "cirurgica", "sandico"],
    pasta_drive_id="pasta_surgical",
)


def montar_config(padrao: str | None = None, nomeacao: Nomeacao | None = None) -> Config:
    return Config(
        fuso_horario="America/Sao_Paulo",
        idioma="pt-BR",
        mentorias=[START, SURGICAL],
        mentoria_padrao=padrao,
        nomeacao=nomeacao or Nomeacao(),
        zoom=ConfigZoom(),
        resumo=ConfigResumo(),
        pdf=ConfigPdf(),
        notificacao=ConfigNotificacao(),
    )


# --- classificacao ---------------------------------------------------------
@pytest.mark.parametrize(
    "titulo, esperado",
    [
        ("Mentoria Start - Aula 5", "start"),
        ("MENTORIA SURGICAL | reposicao", "surgical"),
        ("Aula cirurgica de quinta", "surgical"),
        ("aula surgical", "surgical"),
        ("Encontro START 12/03", "start"),
        ("Mentoria Sandico - modulo 2", "surgical"),
    ],
)
def test_classifica_pelo_titulo(titulo, esperado):
    assert classificar_mentoria(titulo, montar_config()).id == esperado


def test_acento_e_caixa_nao_atrapalham():
    assert classificar_mentoria("Aula CIRÚRGICA", montar_config()).id == "surgical"


def test_palavra_chave_mais_especifica_vence():
    config = montar_config()
    # "mentoria start" (14) e mais especifica que "start" (5).
    assert classificar_mentoria("Mentoria Start", config).id == "start"


def test_palavra_dentro_de_outra_nao_casa():
    # "restart" nao deve ativar "start".
    with pytest.raises(ErroClassificacao):
        classificar_mentoria("Reuniao de restart do projeto", montar_config())


def test_titulo_sem_pista_falha_com_orientacao():
    with pytest.raises(ErroClassificacao, match="Start"):
        classificar_mentoria("Reuniao de quinta-feira", montar_config())


def test_mentoria_padrao_salva_o_titulo_sem_pista():
    assert classificar_mentoria("Reuniao de quinta", montar_config(padrao="start")).id == "start"


# --- numeracao -------------------------------------------------------------
def test_le_numeros_dos_nomes_existentes():
    nomes = [
        "Aula 01 - 03-02-2026 - Mentoria Start.mp4",
        "Aula 02 - 10-02-2026 - Mentoria Start.mp4",
        "Aula 03 - 17-02-2026 - Mentoria Start - Resumo.pdf",
        "Notas soltas.txt",
    ]
    assert sorted(numeros_em_nomes(nomes, Nomeacao().regex_numero)) == [1, 2, 3]


def test_proximo_numero_e_o_maior_mais_um():
    nomes = ["Aula 01 - x.mp4", "Aula 03 - y.mp4"]
    assert proximo_numero(nomes, Nomeacao()) == 4


def test_pasta_vazia_comeca_no_numero_inicial():
    assert proximo_numero([], Nomeacao()) == 1
    assert proximo_numero([], Nomeacao(numero_inicial=10)) == 10


def test_numeros_reservados_evitam_colisao():
    # O Drive ainda nao mostra a aula 4, mas o banco sabe que ela foi criada.
    nomes = ["Aula 03 - y.mp4"]
    assert proximo_numero(nomes, Nomeacao(), reservados={4}) == 5


def test_variacoes_de_escrita_do_numero():
    nomes = ["Aula nº 07 - antiga.mp4", "AULA 12 - outra.pdf", "aula8.mp4"]
    assert proximo_numero(nomes, Nomeacao()) == 13


def test_arquivos_sem_numeracao_sao_ignorados():
    assert proximo_numero(["material de apoio.pdf", "leia-me.txt"], Nomeacao()) == 1


# --- nomes dos arquivos ----------------------------------------------------
def test_monta_nomes_no_padrao_configurado():
    nomes = montar_nomes(
        numero=4,
        data_aula=datetime(2026, 3, 17),
        mentoria=START,
        titulo_zoom="Mentoria Start - hormonios",
        nomeacao=Nomeacao(),
    )
    assert nomes.base == "Aula 04 - 17-03-2026 - Mentoria Start"
    assert nomes.video == "Aula 04 - 17-03-2026 - Mentoria Start.mp4"
    assert nomes.resumo == "Aula 04 - 17-03-2026 - Mentoria Start - Resumo.pdf"
    assert nomes.pasta is None


def test_subpasta_por_aula_quando_configurado():
    nomes = montar_nomes(
        numero=4,
        data_aula=datetime(2026, 3, 17),
        mentoria=SURGICAL,
        titulo_zoom="x",
        nomeacao=Nomeacao(criar_subpasta_por_aula=True),
    )
    assert nomes.pasta == "Aula 04 - 17-03-2026 - Mentoria Surgical"


def test_padrao_personalizado_com_titulo_do_zoom():
    nomes = montar_nomes(
        numero=9,
        data_aula=datetime(2026, 1, 5),
        mentoria=START,
        titulo_zoom="Reposicao masculina",
        nomeacao=Nomeacao(padrao="{mentoria} {numero:03d} ({data}) {titulo_zoom}"),
    )
    assert nomes.base == "Mentoria Start 009 (05-01-2026) Reposicao masculina"


def test_o_nome_gerado_pode_ser_lido_de_volta():
    """A numeracao so funciona se o proprio padrao casar com o regex de leitura."""
    nomeacao = Nomeacao()
    nomes = montar_nomes(
        numero=7,
        data_aula=datetime(2026, 5, 1),
        mentoria=START,
        titulo_zoom="x",
        nomeacao=nomeacao,
    )
    assert proximo_numero([nomes.video, nomes.resumo], nomeacao) == 8


def test_sanitiza_caracteres_proibidos():
    assert sanitizar('Aula 1: reposicao / hormonal?') == "Aula 1- reposicao - hormonal"
