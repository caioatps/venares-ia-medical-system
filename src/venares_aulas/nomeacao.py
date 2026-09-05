"""Classificacao da mentoria, numeracao sequencial e nome dos arquivos."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from .config import Config, Mentoria, Nomeacao
from .transcricao.glossario import normalizar

# Caracteres que o Drive aceita mas atrapalham em download/sincronizacao.
_PROIBIDOS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


class ErroClassificacao(RuntimeError):
    """O titulo da reuniao nao permite identificar a mentoria."""


def sanitizar(nome: str) -> str:
    limpo = _PROIBIDOS.sub("-", nome)
    limpo = re.sub(r"\s+", " ", limpo).strip(" .-")
    return limpo[:180] or "Aula"


def classificar_mentoria(titulo: str, config: Config) -> Mentoria:
    """Descobre a mentoria a partir do titulo da reuniao no Zoom.

    Compara sem acento e sem diferenciar maiusculas. Quando mais de uma
    mentoria casa, vence a que teve a palavra-chave mais longa (mais
    especifica).
    """
    alvo = normalizar(titulo or "")
    melhor: tuple[int, Mentoria] | None = None
    for mentoria in config.mentorias:
        for chave in mentoria.palavras_chave:
            chave_normalizada = normalizar(chave)
            if not chave_normalizada:
                continue
            if re.search(rf"\b{re.escape(chave_normalizada)}\b", alvo):
                if melhor is None or len(chave_normalizada) > melhor[0]:
                    melhor = (len(chave_normalizada), mentoria)
    if melhor:
        return melhor[1]

    if config.mentoria_padrao:
        padrao = config.mentoria_por_id(config.mentoria_padrao)
        if padrao:
            return padrao
    raise ErroClassificacao(
        f"Nao consegui identificar a mentoria pelo titulo {titulo!r}. "
        "Inclua 'Start' ou 'Surgical' no nome da reuniao, ou acrescente a "
        "palavra-chave em config.yaml."
    )


def numeros_em_nomes(nomes: list[str], regex: str) -> list[int]:
    """Extrai os numeros de aula ja usados a partir dos nomes no Drive."""
    padrao = re.compile(regex)
    encontrados: list[int] = []
    for nome in nomes:
        achado = padrao.search(nome)
        if achado:
            try:
                encontrados.append(int(achado.group(1)))
            except (IndexError, ValueError):
                continue
    return encontrados


def proximo_numero(
    nomes_existentes: list[str],
    nomeacao: Nomeacao,
    *,
    reservados: set[int] | None = None,
) -> int:
    """Proximo numero da sequencia: maior numero encontrado + 1.

    `reservados` sao numeros que este sistema ja atribuiu mas que podem
    ainda nao aparecer na listagem do Drive (upload concorrente).
    """
    usados = set(numeros_em_nomes(nomes_existentes, nomeacao.regex_numero))
    usados |= reservados or set()
    if not usados:
        return nomeacao.numero_inicial
    return max(max(usados) + 1, nomeacao.numero_inicial)


@dataclass(frozen=True)
class NomesArquivos:
    base: str
    video: str
    resumo: str
    pasta: str | None
    numero: int


def montar_nomes(
    *,
    numero: int,
    data_aula: datetime,
    mentoria: Mentoria,
    titulo_zoom: str,
    nomeacao: Nomeacao,
    extensao_video: str = "mp4",
) -> NomesArquivos:
    base = sanitizar(
        nomeacao.padrao.format(
            numero=numero,
            data=data_aula.strftime(nomeacao.formato_data),
            mentoria=mentoria.nome,
            titulo_zoom=titulo_zoom,
        )
    )
    extensao = extensao_video.lstrip(".").lower() or "mp4"
    return NomesArquivos(
        base=base,
        video=f"{sanitizar(base + nomeacao.sufixo_video)}.{extensao}",
        resumo=f"{sanitizar(base + nomeacao.sufixo_resumo)}.pdf",
        pasta=base if nomeacao.criar_subpasta_por_aula else None,
        numero=numero,
    )
