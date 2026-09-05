import pytest

from venares_aulas.transcricao.glossario import (
    Glossario,
    Participante,
    Termo,
    aplicar_glossario,
    normalizar,
)
from venares_aulas.transcricao.vtt import carregar_transcricao
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "aula_exemplo.vtt"


@pytest.fixture
def glossario() -> Glossario:
    return Glossario(
        termos=[
            Termo(correto="testosterona", variacoes=["testoterona"]),
            Termo(correto="estradiol", variacoes=["extradiol"], definicao="Principal estrogenio."),
            Termo(correto="SHBG", variacoes=["shbg"], definicao="Globulina ligadora."),
            Termo(correto="undecanoato", variacoes=["andecanoato"]),
            Termo(correto="GnRH", variacoes=["genarra ache"]),
        ],
        abreviacoes={"TRH": "Terapia de Reposicao Hormonal"},
        substituicoes_regex=[(r"(?i)\bmiligramas?\b", "mg")],
        remover_frases=["esta reuniao esta sendo gravada", "you"],
        participantes=[Participante(zoom="Dr. Fulano", exibir="Dr. Fulano de Tal", papel="professor")],
    )


def test_normalizar_remove_acento_e_caixa():
    assert normalizar("Cirúrgica  START") == "cirurgica start"


def test_corrige_variacoes(glossario):
    texto, trocas = glossario.aplicar("reposicao com testoterona e extradiol baixo")
    assert texto == "reposicao com testosterona e estradiol baixo"
    assert trocas == 2


def test_corrige_termo_de_varias_palavras(glossario):
    texto, _ = glossario.aplicar("semana que vem falamos de genarra ache.")
    assert "GnRH" in texto


def test_substituicao_por_regex(glossario):
    texto, _ = glossario.aplicar("250 miligramas a cada dez semanas")
    assert texto == "250 mg a cada dez semanas"


def test_termo_ja_correto_nao_conta_como_troca(glossario):
    _, trocas = glossario.aplicar("dose de testosterona")
    assert trocas == 0


def test_remove_frase_de_ruido(glossario):
    assert glossario.deve_remover("[00:01] Dr. Fulano: esta reuniao esta sendo gravada")
    assert glossario.deve_remover("you")


def test_frase_de_ruido_nao_derruba_frase_legitima(glossario):
    linha = "Dr. Fulano: quando you esta na frase legitima o conteudo clinico continua aqui"
    assert not glossario.deve_remover(linha)


def test_aplicar_glossario_na_transcricao(glossario):
    transcricao = carregar_transcricao(FIXTURE.read_text(encoding="utf-8"))
    limpa = aplicar_glossario(transcricao, glossario)
    texto = limpa.para_texto()
    assert "testosterona" in texto
    assert "estradiol" in texto
    assert "undecanoato" in texto
    assert "esta reuniao esta sendo gravada" not in texto
    # O nome do Zoom vira o nome de exibicao.
    assert "Dr. Fulano de Tal" in limpa.falantes


def test_professores_e_definicoes(glossario):
    assert glossario.professores() == ["Dr. Fulano de Tal"]
    assert glossario.definicoes(["SHBG", "inexistente"]) == [("SHBG", "Globulina ligadora.")]


def test_para_prompt_lista_termos_e_siglas(glossario):
    prompt = glossario.para_prompt()
    assert "- SHBG - Globulina ligadora." in prompt
    assert "- TRH = Terapia de Reposicao Hormonal" in prompt


def test_ruido_grudado_em_fala_legitima_e_recortado(glossario):
    saida = glossario.limpar_ruido("Bom dia a todos, esta reuniao esta sendo gravada.")
    assert saida == "Bom dia a todos"


def test_ruido_com_acento_no_texto_original(glossario):
    saida = glossario.limpar_ruido("Pessoal, esta reunião está sendo gravada, podem falar.")
    assert saida is not None
    assert "gravada" not in saida
    assert "podem falar" in saida


def test_fala_que_e_so_ruido_some(glossario):
    assert glossario.limpar_ruido("Esta reuniao esta sendo gravada.") is None
    assert glossario.limpar_ruido("You") is None
