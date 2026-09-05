from datetime import datetime

import pytest

from venares_aulas.config import ConfigPdf, Mentoria, Nomeacao
from venares_aulas.nomeacao import montar_nomes
from venares_aulas.pdf.render import (
    data_por_extenso,
    duracao_por_extenso,
    montar_glossario_final,
    renderizar_html,
)
from venares_aulas.resumo.modelos import (
    Caso,
    PerguntaResposta,
    ResumoAula,
    TermoGlossario,
    Topico,
)
from venares_aulas.transcricao.glossario import Glossario, Participante, Termo

START = Mentoria(id="start", nome="Mentoria Start", palavras_chave=["start"], pasta_drive_id="x")


@pytest.fixture
def resumo() -> ResumoAula:
    return ResumoAula(
        titulo="Reposicao hormonal masculina",
        resumo_executivo="Aula sobre inicio de TRH em homens com hipogonadismo.",
        objetivos=["Reconhecer hipogonadismo", "Escolher a via de administracao"],
        topicos=[
            Topico(
                titulo="Diagnostico",
                timestamp="00:04:12",
                pontos=["Dosar testosterona total em jejum", "Confirmar em duas coletas"],
            )
        ],
        pontos_chave=["SHBG alterada muda a interpretacao da testosterona total"],
        condutas_praticas=["Undecanoato 1000 mg a cada 10 semanas"],
        casos_discutidos=[
            Caso(titulo="Paciente de 40 e poucos anos", descricao="Fadiga e libido baixa.", conduta="Iniciar TRH.")
        ],
        perguntas_respostas=[PerguntaResposta(pergunta="E se a SHBG estiver alta?", resposta="Avaliar a livre.")],
        termos_glossario=[TermoGlossario(termo="SHBG", definicao="Definicao vinda do modelo.")],
        referencias=["Diretriz da Endocrine Society citada na aula"],
        proximos_passos=["Trazer um caso para a proxima aula"],
    )


@pytest.fixture
def glossario() -> Glossario:
    return Glossario(
        termos=[Termo(correto="SHBG", definicao="Globulina ligadora de hormonios sexuais.")],
        abreviacoes={"TRH": "Terapia de Reposicao Hormonal"},
        participantes=[Participante(zoom="Dr. Fulano", exibir="Dr. Fulano de Tal", papel="professor")],
    )


def _html(resumo, glossario) -> str:
    nomes = montar_nomes(
        numero=4,
        data_aula=datetime(2026, 3, 17),
        mentoria=START,
        titulo_zoom="Mentoria Start - Aula 4",
        nomeacao=Nomeacao(),
    )
    return renderizar_html(
        resumo=resumo,
        config_pdf=ConfigPdf(rodape="Uso exclusivo dos alunos."),
        glossario=glossario,
        nomes=nomes,
        mentoria="Mentoria Start",
        titulo_zoom="Mentoria Start - Aula 4",
        data_aula=datetime(2026, 3, 17),
        duracao_min=95,
        palavras=8420,
    )


def test_capa_traz_numero_mentoria_e_data(resumo, glossario):
    html = _html(resumo, glossario)
    assert "Mentoria Start" in html
    assert "Aula 04" in html
    assert "17 de marco de 2026" in html
    assert "1h35min" in html
    assert "Dr. Fulano de Tal" in html


def test_todas_as_secoes_do_modelo_aparecem(resumo, glossario):
    html = _html(resumo, glossario)
    for esperado in [
        "Resumo da aula",
        "Objetivos de aprendizagem",
        "Conteudo abordado",
        "Pontos-chave",
        "Condutas e protocolos citados",
        "Casos discutidos",
        "Perguntas dos alunos",
        "Glossario",
        "Referencias citadas na aula",
        "Proximos passos",
        "00:04:12",
    ]:
        assert esperado in html, esperado


def test_secao_vazia_nao_e_renderizada(glossario):
    vazio = ResumoAula(titulo="Aula curta", resumo_executivo="Muito curta.")
    html = _html(vazio, glossario)
    assert "Casos discutidos" not in html
    assert "Perguntas dos alunos" not in html
    assert "Resumo da aula" in html


def test_definicao_oficial_vence_a_do_modelo(resumo, glossario):
    final = dict(montar_glossario_final(resumo, glossario))
    assert final["SHBG"] == "Globulina ligadora de hormonios sexuais."


def test_sigla_citada_no_texto_entra_no_glossario(resumo, glossario):
    final = dict(montar_glossario_final(resumo, glossario))
    assert final["TRH"] == "Terapia de Reposicao Hormonal"


def test_html_e_escapado(glossario):
    perigoso = ResumoAula(
        titulo="Aula <script>alert(1)</script>",
        resumo_executivo="Dose de 5 mg > 2 mg.",
    )
    html = _html(perigoso, glossario)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_formatacao_de_data_e_duracao():
    assert data_por_extenso(datetime(2026, 12, 1)) == "1 de dezembro de 2026"
    assert duracao_por_extenso(45) == "45min"
    assert duracao_por_extenso(120) == "2h"
    assert duracao_por_extenso(0) == "-"
