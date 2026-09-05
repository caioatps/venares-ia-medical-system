"""Glossario medico: corrige a transcricao e alimenta o prompt do resumo."""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..config import RAIZ
from ..logging_setup import log

_LOG = log(__name__)


def sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", texto)
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn")


_EQUIVALENTES = {
    "a": "[aàáâãä]", "e": "[eèéêë]", "i": "[iìíîï]",
    "o": "[oòóôõö]", "u": "[uùúûü]", "c": "[cç]",
}


def _letra_flexivel(palavra: str) -> str:
    """Converte 'gravacao' em um padrao que tambem casa 'gravação'."""
    return "".join(_EQUIVALENTES.get(c, re.escape(c)) for c in palavra)


def normalizar(texto: str) -> str:
    """Minusculas, sem acento e com espacos colapsados - para comparacoes."""
    return re.sub(r"\s+", " ", sem_acento(texto).lower()).strip()


@dataclass(frozen=True)
class Termo:
    correto: str
    variacoes: list[str] = field(default_factory=list)
    definicao: str = ""


@dataclass(frozen=True)
class Participante:
    zoom: str
    exibir: str
    papel: str = "aluno"


@dataclass
class Glossario:
    termos: list[Termo] = field(default_factory=list)
    abreviacoes: dict[str, str] = field(default_factory=dict)
    substituicoes_regex: list[tuple[str, str]] = field(default_factory=list)
    remover_frases: list[str] = field(default_factory=list)
    participantes: list[Participante] = field(default_factory=list)
    _cache_padroes: list[tuple[re.Pattern[str], str]] | None = field(
        default=None, repr=False, compare=False
    )

    # -- carregamento -------------------------------------------------------
    @classmethod
    def vazio(cls) -> "Glossario":
        return cls()

    @classmethod
    def carregar(cls, caminho: str | os.PathLike[str] | None = None) -> "Glossario":
        alvo = Path(caminho or os.getenv("VENARES_GLOSSARIO", "config/glossario.yaml"))
        if not alvo.is_absolute():
            alvo = RAIZ / alvo
        if not alvo.exists():
            _LOG.warning("Glossario nao encontrado em %s; seguindo sem ele.", alvo)
            return cls.vazio()
        dados = yaml.safe_load(alvo.read_text(encoding="utf-8")) or {}
        return cls(
            termos=[
                Termo(
                    correto=str(t["correto"]),
                    variacoes=[str(v) for v in (t.get("variacoes") or [])],
                    definicao=str(t.get("definicao") or ""),
                )
                for t in (dados.get("termos") or [])
                if t.get("correto")
            ],
            abreviacoes={str(k): str(v) for k, v in (dados.get("abreviacoes") or {}).items()},
            substituicoes_regex=[
                (str(s["de"]), str(s.get("para", "")))
                for s in (dados.get("substituicoes_regex") or [])
                if s.get("de")
            ],
            remover_frases=[str(f) for f in (dados.get("remover_frases") or [])],
            participantes=[
                Participante(
                    zoom=str(p["zoom"]),
                    exibir=str(p.get("exibir") or p["zoom"]),
                    papel=str(p.get("papel") or "aluno"),
                )
                for p in (dados.get("participantes") or [])
                if p.get("zoom")
            ],
        )

    # -- aplicacao ----------------------------------------------------------
    def _padroes_de_termos(self) -> list[tuple[re.Pattern[str], str]]:
        if self._cache_padroes is not None:
            return self._cache_padroes
        """Uma expressao por termo, casando qualquer variacao sem acento/caixa.

        As variacoes mais longas vem primeiro para que 'implante hormonal'
        seja trocado antes de 'implante'.
        """
        padroes: list[tuple[re.Pattern[str], str]] = []
        for termo in self.termos:
            alternativas = sorted(
                {v for v in [*termo.variacoes, termo.correto] if v.strip()},
                key=len,
                reverse=True,
            )
            corpo = "|".join(re.escape(sem_acento(a)) for a in alternativas)
            if not corpo:
                continue
            padroes.append((re.compile(rf"(?i)\b(?:{corpo})\b"), termo.correto))
        self._cache_padroes = padroes
        return padroes

    def aplicar(self, texto: str) -> tuple[str, int]:
        """Corrige o texto. Devolve (texto corrigido, numero de trocas).

        As buscas rodam sobre uma versao sem acentos do texto, mas as
        posicoes sao preservadas (a remocao de acento e feita caractere a
        caractere, mantendo o mesmo comprimento), entao os recortes valem
        para o texto original.
        """
        base = "".join(
            sem_acento(c) if len(sem_acento(c)) == 1 else c for c in texto
        )
        if len(base) != len(texto):  # seguranca: cai para o caminho simples
            base = texto

        trocas: list[tuple[int, int, str]] = []
        for padrao, substituto in self._padroes_de_termos():
            for achado in padrao.finditer(base):
                trocas.append((achado.start(), achado.end(), substituto))

        # Resolve sobreposicoes ficando com o casamento mais longo.
        trocas.sort(key=lambda t: (t[0], -(t[1] - t[0])))
        resultado: list[str] = []
        cursor = 0
        aplicadas = 0
        for inicio, fim, substituto in trocas:
            if inicio < cursor:
                continue
            trecho = texto[inicio:fim]
            resultado.append(texto[cursor:inicio])
            resultado.append(substituto)
            cursor = fim
            if trecho != substituto:
                aplicadas += 1
        resultado.append(texto[cursor:])
        saida = "".join(resultado)

        for de, para in self.substituicoes_regex:
            saida, n = re.subn(de, para, saida)
            aplicadas += n
        return saida, aplicadas

    def _nucleo(self, linha: str) -> str:
        """A linha sem o prefixo de tempo e sem o nome do falante."""
        alvo = normalizar(linha)
        alvo = re.sub(r"^\[[^\]]*\]\s*", "", alvo)
        return re.sub(r"^[^:]{1,60}:\s*", "", alvo)

    def limpar_ruido(self, linha: str) -> str | None:
        """Tira o ruido de gravacao de uma fala.

        Devolve None quando a fala inteira e ruido, ou o texto sem os
        trechos de ruido quando eles vieram grudados em conteudo real
        ("Bom dia a todos, esta reuniao esta sendo gravada.").

        Frases curtas (ate duas palavras, como "you") so derrubam a fala
        quando sao a fala inteira - recortar "you" de dentro de uma frase
        legitima estragaria o texto.
        """
        if not linha.strip():
            return None
        nucleo = self._nucleo(linha)
        saida = linha
        for frase in self.remover_frases:
            ruido = normalizar(frase)
            if not ruido:
                continue
            # Fala que e so o ruido (com ou sem pontuacao) some inteira.
            if re.fullmatch(rf"{re.escape(ruido)}[\s.,!?;:]*", nucleo):
                return None
            # Ruido especifico (3+ palavras) e recortado de dentro da fala.
            if len(ruido.split()) >= 3:
                padrao = re.compile(
                    r"[,;]?\s*" + r"\s+".join(
                        rf"{_letra_flexivel(p)}" for p in ruido.split()
                    ) + r"[.,!?;:]*",
                    re.IGNORECASE,
                )
                saida = padrao.sub("", saida)
        saida = re.sub(r"\s{2,}", " ", saida).strip(" ,;")
        return saida or None

    def deve_remover(self, linha: str) -> bool:
        """True quando a fala inteira deve ser descartada."""
        return self.limpar_ruido(linha) is None

    def nome_exibicao(self, nome_zoom: str | None) -> str | None:
        if not nome_zoom:
            return None
        alvo = normalizar(nome_zoom)
        for p in self.participantes:
            if normalizar(p.zoom) == alvo:
                return p.exibir
        return nome_zoom

    def professores(self) -> list[str]:
        return [p.exibir for p in self.participantes if p.papel.lower() == "professor"]

    # -- contexto para o modelo --------------------------------------------
    def para_prompt(self, limite: int = 120) -> str:
        """Lista compacta de termos e siglas para colar no prompt do Claude."""
        linhas: list[str] = []
        for termo in self.termos[:limite]:
            definicao = f" - {termo.definicao}" if termo.definicao else ""
            linhas.append(f"- {termo.correto}{definicao}")
        for sigla, expansao in list(self.abreviacoes.items())[:limite]:
            linhas.append(f"- {sigla} = {expansao}")
        return "\n".join(linhas)

    def definicoes(self, termos_usados: list[str]) -> list[tuple[str, str]]:
        """Definicoes dos termos citados, para a secao de glossario do PDF."""
        indice = {normalizar(t.correto): t.definicao for t in self.termos if t.definicao}
        indice.update({normalizar(k): v for k, v in self.abreviacoes.items()})
        saida: list[tuple[str, str]] = []
        for termo in termos_usados:
            definicao = indice.get(normalizar(termo))
            if definicao:
                saida.append((termo, definicao))
        return saida


def limpar_transcricao(texto: str, glossario: Glossario) -> tuple[str, int]:
    """Remove ruido linha a linha e aplica as correcoes do glossario."""
    linhas = [l for l in texto.split("\n") if not glossario.deve_remover(l)]
    return glossario.aplicar("\n".join(linhas))


def aplicar_glossario(transcricao, glossario: Glossario):
    """Versao da transcricao com ruido removido e termos corrigidos.

    Trabalha turno a turno para nao perder marcas de tempo nem os nomes
    dos participantes, e ja troca o nome do Zoom pelo nome de exibicao.
    """
    from .vtt import Transcricao, Turno

    limpos: list[Turno] = []
    correcoes = 0
    descartadas = 0
    for turno in transcricao.turnos:
        # A filtragem e por fala (cada `parte` e uma legenda original), nao
        # pelo turno inteiro: um "gravacao iniciada" no comeco nao pode
        # levar junto o conteudo clinico que veio na sequencia.
        partes: list[str] = []
        for parte in turno.partes:
            sem_ruido = glossario.limpar_ruido(parte)
            if sem_ruido is None:
                descartadas += 1
                continue
            texto, trocas = glossario.aplicar(sem_ruido)
            correcoes += trocas
            if texto.strip():
                partes.append(texto)
        if not partes:
            continue
        limpos.append(
            Turno(
                falante=glossario.nome_exibicao(turno.falante),
                inicio=turno.inicio,
                fim=turno.fim,
                partes=partes,
            )
        )
    _LOG.info(
        "Transcricao: %d turnos, %d fala(s) descartada(s) como ruido, "
        "%d correcao(oes) do glossario.",
        len(limpos),
        descartadas,
        correcoes,
    )
    return Transcricao(turnos=limpos)
