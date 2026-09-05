"""Montagem dos prompts do resumo.

O prompt de sistema e mantido estavel de proposito: ele e a parte cacheada
(prompt caching), entao qualquer coisa variavel - titulo, data, transcricao -
fica na mensagem do usuario.
"""

from __future__ import annotations

SISTEMA = """Voce e um assistente de ensino medico que transforma a transcricao \
bruta de uma aula ao vivo em um material de estudo para os alunos de uma mentoria.

Regras invioláveis:
1. Use SOMENTE o que esta na transcricao. Nunca acrescente doses, condutas, \
diretrizes, valores de referencia ou referencias bibliograficas que nao tenham \
sido ditos na aula. Se algo ficou incompleto na fala, escreva o que foi dito e \
pare ali - nao complete com conhecimento proprio.
2. Preserve a terminologia da equipe. A lista de termos e siglas fornecida e a \
grafia oficial: use exatamente aquela forma, mesmo que a transcricao tenha \
escrito de outro jeito. Nao traduza siglas no corpo do texto (escreva TRH, nao \
"terapia de reposicao hormonal") - a expansao vai na secao de glossario.
3. Transcricao automatica erra. Quando uma palavra estiver claramente corrompida \
mas o sentido for obvio pelo contexto clinico, corrija em silencio. Quando o \
sentido NAO for recuperavel, escreva "[trecho inaudivel]" em vez de adivinhar.
4. Nao inclua nome, idade exata, documento ou qualquer dado que identifique \
pacientes. Descreva os casos de forma despersonalizada ("paciente de 40 e poucos \
anos, sexo feminino").
5. Ignore conversa fora do tema: saudacoes, problemas de audio/conexao, avisos \
sobre gravacao, combinados de horario.
6. Escreva em portugues do Brasil, em tom direto e clinico, na terceira pessoa. \
Sem enfeite, sem "nesta aula o professor falou sobre" - va direto ao conteudo.
7. Cada topico deve trazer o timestamp em que ele comeca, copiado das marcas de \
tempo da transcricao.

Voce sempre responde no formato estruturado solicitado, sem texto fora dele."""


def contexto_aula(
    *,
    titulo_zoom: str,
    mentoria: str,
    data_aula: str,
    duracao_min: int,
    participantes: list[str],
    professores: list[str],
) -> str:
    linhas = [
        "Dados da aula:",
        f"- Mentoria: {mentoria}",
        f"- Titulo no Zoom: {titulo_zoom}",
        f"- Data: {data_aula}",
        f"- Duracao aproximada: {duracao_min} minutos",
    ]
    if professores:
        linhas.append(f"- Professor(es): {', '.join(professores)}")
    if participantes:
        linhas.append(f"- Vozes na transcricao: {', '.join(participantes[:15])}")
    return "\n".join(linhas)


def bloco_glossario(glossario_texto: str) -> str:
    if not glossario_texto.strip():
        return ""
    return (
        "Terminologia oficial da equipe (grafia obrigatoria):\n"
        f"{glossario_texto}\n"
    )


def usuario_resumo_direto(
    *, contexto: str, glossario: str, instrucoes_extras: str, transcricao: str
) -> str:
    partes = [
        contexto,
        "",
        bloco_glossario(glossario),
        instrucoes_extras.strip(),
        "",
        "Transcricao completa da aula (marcas de tempo entre colchetes):",
        "<transcricao>",
        transcricao,
        "</transcricao>",
        "",
        "Produza o material de estudo desta aula no formato estruturado.",
    ]
    return "\n".join(p for p in partes if p is not None)


def usuario_notas_bloco(
    *, contexto: str, glossario: str, indice: int, total: int, trecho: str
) -> str:
    return "\n".join(
        [
            contexto,
            "",
            bloco_glossario(glossario),
            f"Este e o trecho {indice} de {total} da transcricao da aula.",
            "Extraia notas fieis deste trecho - ainda NAO e o resumo final.",
            "Registre tudo que for clinicamente relevante, com numeros e doses",
            "exatamente como foram ditos, e mantenha as marcas de tempo.",
            "",
            "<trecho>",
            trecho,
            "</trecho>",
        ]
    )


def usuario_consolidacao(
    *, contexto: str, glossario: str, instrucoes_extras: str, notas: str
) -> str:
    return "\n".join(
        [
            contexto,
            "",
            bloco_glossario(glossario),
            instrucoes_extras.strip(),
            "",
            "Abaixo estao as notas extraidas de cada trecho da aula, em ordem",
            "cronologica. Consolide tudo em um unico material de estudo,",
            "eliminando repeticoes e mantendo a ordem em que os assuntos",
            "apareceram. Nao acrescente nada que nao esteja nas notas.",
            "",
            "<notas>",
            notas,
            "</notas>",
        ]
    )
