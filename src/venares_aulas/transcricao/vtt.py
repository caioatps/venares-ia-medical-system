"""Leitura do arquivo .vtt que o Zoom gera junto com a gravacao.

O formato do Zoom e:

    WEBVTT

    1
    00:00:03.120 --> 00:00:07.480
    Dr. Fulano: entao vamos falar de reposicao...

Cada fala vira uma legenda curta. Aqui elas sao agrupadas em turnos por
falante, o que reduz muito o tamanho do texto e deixa a transcricao
legivel para o modelo e para uma eventual revisao humana.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_TEMPO = r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
_LINHA_TEMPO = re.compile(rf"^\s*{_TEMPO}\s*-->\s*{_TEMPO}")
_FALANTE = re.compile(r"^\s*([^:]{1,60}?)\s*:\s*(.*)$")
_TAGS = re.compile(r"</?[cvibu][^>]*>")


def _para_segundos(h: str | None, m: str, s: str, ms: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def formatar_tempo(segundos: float) -> str:
    total = int(segundos)
    h, resto = divmod(total, 3600)
    m, s = divmod(resto, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


@dataclass
class Legenda:
    inicio: float
    fim: float
    falante: str | None
    texto: str


@dataclass
class Turno:
    """Uma fala continua do mesmo participante."""

    falante: str | None
    inicio: float
    fim: float
    partes: list[str] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return " ".join(p.strip() for p in self.partes if p.strip())


@dataclass
class Transcricao:
    turnos: list[Turno]

    @property
    def falantes(self) -> list[str]:
        vistos: list[str] = []
        for t in self.turnos:
            if t.falante and t.falante not in vistos:
                vistos.append(t.falante)
        return vistos

    @property
    def duracao_s(self) -> float:
        return self.turnos[-1].fim if self.turnos else 0.0

    @property
    def total_palavras(self) -> int:
        return sum(len(t.texto.split()) for t in self.turnos)

    def para_texto(self, *, com_tempo: bool = True) -> str:
        """Texto plano com marcacao de falante e timestamp por turno."""
        linhas = []
        for turno in self.turnos:
            prefixo = f"[{formatar_tempo(turno.inicio)}] " if com_tempo else ""
            quem = f"{turno.falante}: " if turno.falante else ""
            linhas.append(f"{prefixo}{quem}{turno.texto}")
        return "\n".join(linhas)


def analisar_vtt(conteudo: str) -> list[Legenda]:
    """Converte o conteudo de um .vtt/.srt em legendas."""
    legendas: list[Legenda] = []
    blocos = re.split(r"\n\s*\n", conteudo.replace("\r\n", "\n").replace("\r", "\n"))
    for bloco in blocos:
        linhas = [l for l in bloco.split("\n") if l.strip()]
        if not linhas:
            continue
        if linhas[0].strip().upper().startswith("WEBVTT"):
            linhas = linhas[1:]
        indice_tempo = next(
            (i for i, l in enumerate(linhas) if _LINHA_TEMPO.match(l)), None
        )
        if indice_tempo is None:
            continue
        casamento = _LINHA_TEMPO.match(linhas[indice_tempo])
        assert casamento is not None
        g = casamento.groups()
        inicio = _para_segundos(g[0], g[1], g[2], g[3])
        fim = _para_segundos(g[4], g[5], g[6], g[7])

        corpo = " ".join(linhas[indice_tempo + 1 :]).strip()
        corpo = _TAGS.sub("", corpo)
        if not corpo:
            continue
        falante = None
        casamento_falante = _FALANTE.match(corpo)
        if casamento_falante:
            candidato, resto = casamento_falante.groups()
            # Evita confundir "Atencao: isso e importante" com um falante.
            if resto and len(candidato.split()) <= 5 and not candidato.endswith((".", "?", "!")):
                falante, corpo = candidato.strip(), resto.strip()
        legendas.append(Legenda(inicio=inicio, fim=fim, falante=falante, texto=corpo))
    return legendas


def agrupar_em_turnos(
    legendas: list[Legenda], *, intervalo_maximo_s: float = 15.0
) -> list[Turno]:
    """Junta legendas seguidas do mesmo falante em um unico turno."""
    turnos: list[Turno] = []
    for legenda in legendas:
        atual = turnos[-1] if turnos else None
        mesmo_falante = atual is not None and atual.falante == legenda.falante
        proximo = atual is not None and (legenda.inicio - atual.fim) <= intervalo_maximo_s
        if atual is not None and mesmo_falante and proximo:
            atual.partes.append(legenda.texto)
            atual.fim = legenda.fim
        else:
            turnos.append(
                Turno(
                    falante=legenda.falante,
                    inicio=legenda.inicio,
                    fim=legenda.fim,
                    partes=[legenda.texto],
                )
            )
    return turnos


def carregar_transcricao(conteudo: str) -> Transcricao:
    return Transcricao(turnos=agrupar_em_turnos(analisar_vtt(conteudo)))
