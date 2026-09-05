from pathlib import Path

from venares_aulas.transcricao.vtt import (
    agrupar_em_turnos,
    analisar_vtt,
    carregar_transcricao,
    formatar_tempo,
)

FIXTURE = Path(__file__).parent / "fixtures" / "aula_exemplo.vtt"


def test_analisa_legendas_com_falante():
    legendas = analisar_vtt(FIXTURE.read_text(encoding="utf-8"))
    assert len(legendas) == 7
    assert legendas[0].falante == "Dr. Fulano"
    assert legendas[0].texto.startswith("Bom dia")
    assert legendas[0].inicio == 1.0
    assert legendas[0].fim == 4.5


def test_hora_cheia_e_lida():
    legendas = analisar_vtt(FIXTURE.read_text(encoding="utf-8"))
    assert legendas[-1].inicio == 3740.0  # 01:02:20


def test_agrupa_turnos_do_mesmo_falante():
    legendas = analisar_vtt(FIXTURE.read_text(encoding="utf-8"))
    turnos = agrupar_em_turnos(legendas)
    # As tres primeiras falas seguidas do professor viram um turno so.
    assert turnos[0].falante == "Dr. Fulano"
    assert "reposicao" in turnos[0].texto
    assert "shbg elevado" in turnos[0].texto
    assert turnos[1].falante == "Aluna Beatriz"


def test_intervalo_longo_quebra_o_turno():
    legendas = analisar_vtt(FIXTURE.read_text(encoding="utf-8"))
    turnos = agrupar_em_turnos(legendas)
    # A fala de 01:02 nao pode ser colada na de 00:00 do mesmo falante.
    inicios = [t.inicio for t in turnos]
    assert 3740.0 in inicios


def test_texto_traz_marcas_de_tempo():
    transcricao = carregar_transcricao(FIXTURE.read_text(encoding="utf-8"))
    texto = transcricao.para_texto()
    assert texto.startswith("[00:01] Dr. Fulano:")
    assert "Aluna Beatriz" in transcricao.falantes


def test_dois_pontos_no_meio_da_frase_nao_vira_falante():
    legendas = analisar_vtt(
        "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\n"
        "Atencao, o ponto mais importante e este: a dose muda por paciente.\n"
    )
    assert legendas[0].falante is None


def test_formatar_tempo():
    assert formatar_tempo(65) == "01:05"
    assert formatar_tempo(3725) == "01:02:05"
