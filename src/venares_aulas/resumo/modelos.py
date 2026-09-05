"""Estrutura do resumo da aula - e o contrato com o Claude e com o PDF."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Topico(BaseModel):
    titulo: str = Field(description="Titulo curto do topico abordado.")
    timestamp: str = Field(
        default="",
        description="Momento em que o topico comeca, no formato HH:MM:SS ou MM:SS.",
    )
    pontos: list[str] = Field(
        default_factory=list,
        description="De 2 a 6 frases objetivas com o conteudo do topico.",
    )


class Caso(BaseModel):
    titulo: str = Field(description="Identificacao do caso, sem dados que identifiquem o paciente.")
    descricao: str = Field(description="Quadro clinico e exames relevantes discutidos.")
    conduta: str = Field(default="", description="Conduta proposta na aula.")


class PerguntaResposta(BaseModel):
    pergunta: str
    resposta: str


class TermoGlossario(BaseModel):
    termo: str
    definicao: str


class ResumoAula(BaseModel):
    """Saida estruturada esperada do modelo."""

    titulo: str = Field(description="Titulo da aula, derivado do conteudo discutido.")
    resumo_executivo: str = Field(
        description="Um paragrafo de 4 a 8 linhas com a essencia da aula."
    )
    objetivos: list[str] = Field(
        default_factory=list, description="Objetivos de aprendizagem da aula."
    )
    topicos: list[Topico] = Field(
        default_factory=list, description="Topicos na ordem em que foram abordados."
    )
    pontos_chave: list[str] = Field(
        default_factory=list, description="As mensagens que o aluno precisa levar."
    )
    condutas_praticas: list[str] = Field(
        default_factory=list,
        description="Condutas, doses, protocolos e criterios de decisao citados.",
    )
    casos_discutidos: list[Caso] = Field(default_factory=list)
    perguntas_respostas: list[PerguntaResposta] = Field(default_factory=list)
    termos_glossario: list[TermoGlossario] = Field(
        default_factory=list,
        description="Termos tecnicos citados na aula, com definicao curta.",
    )
    referencias: list[str] = Field(
        default_factory=list, description="Artigos, diretrizes e livros citados na aula."
    )
    proximos_passos: list[str] = Field(
        default_factory=list, description="Tarefas ou avisos dados aos alunos."
    )


class NotasBloco(BaseModel):
    """Resumo intermediario de um trecho, no fluxo map-reduce."""

    intervalo: str = Field(default="", description="Intervalo de tempo do trecho.")
    assuntos: list[str] = Field(default_factory=list)
    detalhes: list[str] = Field(
        default_factory=list,
        description="Fatos, numeros, doses, condutas e falas relevantes do trecho.",
    )
    casos: list[str] = Field(default_factory=list)
    perguntas: list[str] = Field(default_factory=list)
    termos: list[str] = Field(default_factory=list)
    referencias: list[str] = Field(default_factory=list)
