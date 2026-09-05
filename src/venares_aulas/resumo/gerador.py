"""Geracao do resumo estruturado da aula com o Claude.

Aulas curtas cabem em uma unica chamada (o modelo tem 1M de contexto).
Aulas muito longas passam por map-reduce: notas por trecho e depois uma
consolidacao. O corte dos trechos respeita limites de turno de fala.
"""

from __future__ import annotations

import json

import anthropic

from ..config import ConfigResumo
from ..logging_setup import log
from ..transcricao.glossario import Glossario
from ..transcricao.vtt import Transcricao, formatar_tempo
from . import prompt as P
from .modelos import NotasBloco, ResumoAula

_LOG = log(__name__)


class ErroResumo(RuntimeError):
    pass


def dividir_em_blocos(transcricao: Transcricao, caracteres_por_bloco: int) -> list[str]:
    """Corta a transcricao em trechos, sempre em fronteira de turno."""
    blocos: list[str] = []
    atual: list[str] = []
    tamanho = 0
    for turno in transcricao.turnos:
        quem = f"{turno.falante}: " if turno.falante else ""
        linha = f"[{formatar_tempo(turno.inicio)}] {quem}{turno.texto}"
        if atual and tamanho + len(linha) > caracteres_por_bloco:
            blocos.append("\n".join(atual))
            atual, tamanho = [], 0
        atual.append(linha)
        tamanho += len(linha) + 1
    if atual:
        blocos.append("\n".join(atual))
    return blocos


class GeradorResumo:
    def __init__(self, config: ConfigResumo, *, api_key: str | None = None) -> None:
        self._config = config
        self._cliente = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    # -- chamada ao modelo --------------------------------------------------
    def _chamar(self, mensagem_usuario: str, formato):
        """Uma chamada estruturada, com o prompt de sistema cacheado.

        `messages.parse` devolve a resposta ja validada contra o modelo
        Pydantic. O timeout e alargado porque uma transcricao de 2-3 horas
        leva bem mais que o padrao de 10 minutos do SDK.
        """
        try:
            resposta = self._cliente.with_options(
                timeout=self._config.timeout_s
            ).messages.parse(
                model=self._config.modelo,
                max_tokens=self._config.max_tokens,
                output_config={"effort": self._config.effort},
                system=[
                    {
                        "type": "text",
                        "text": P.SISTEMA,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": mensagem_usuario}],
                output_format=formato,
            )
        except anthropic.APIStatusError as erro:
            raise ErroResumo(
                f"Claude recusou ou falhou ({erro.status_code}): {erro.message}"
            ) from erro
        except anthropic.APIConnectionError as erro:
            raise ErroResumo(f"Falha de rede ao falar com a API do Claude: {erro}") from erro

        if getattr(resposta, "stop_reason", None) == "refusal":
            detalhes = getattr(resposta, "stop_details", None)
            raise ErroResumo(f"O modelo recusou gerar o resumo: {detalhes}")

        analisado = getattr(resposta, "parsed_output", None)
        if analisado is not None:
            return analisado
        # Rede de seguranca: o formato estruturado garante JSON no 1o bloco.
        texto = next((b.text for b in resposta.content if b.type == "text"), "")
        try:
            return formato.model_validate(json.loads(texto))
        except (json.JSONDecodeError, ValueError) as erro:
            raise ErroResumo(f"Resposta do modelo nao pode ser interpretada: {erro}") from erro

    # -- fluxo --------------------------------------------------------------
    def gerar(
        self,
        transcricao: Transcricao,
        *,
        titulo_zoom: str,
        mentoria: str,
        data_aula: str,
        duracao_min: int,
        glossario: Glossario,
    ) -> ResumoAula:
        contexto = P.contexto_aula(
            titulo_zoom=titulo_zoom,
            mentoria=mentoria,
            data_aula=data_aula,
            duracao_min=duracao_min,
            participantes=[
                glossario.nome_exibicao(f) or f for f in transcricao.falantes
            ],
            professores=glossario.professores(),
        )
        texto_glossario = glossario.para_prompt()
        texto = transcricao.para_texto()

        if len(texto) <= self._config.limite_caracteres_chamada_unica:
            _LOG.info(
                "Gerando resumo em uma chamada (%d caracteres, %d palavras).",
                len(texto),
                transcricao.total_palavras,
            )
            return self._chamar(
                P.usuario_resumo_direto(
                    contexto=contexto,
                    glossario=texto_glossario,
                    instrucoes_extras=self._config.instrucoes_extras,
                    transcricao=texto,
                ),
                ResumoAula,
            )

        blocos = dividir_em_blocos(transcricao, self._config.caracteres_por_bloco)
        _LOG.info("Transcricao longa: %d trechos em map-reduce.", len(blocos))
        notas: list[NotasBloco] = []
        for indice, bloco in enumerate(blocos, start=1):
            notas.append(
                self._chamar(
                    P.usuario_notas_bloco(
                        contexto=contexto,
                        glossario=texto_glossario,
                        indice=indice,
                        total=len(blocos),
                        trecho=bloco,
                    ),
                    NotasBloco,
                )
            )
        notas_texto = "\n\n".join(
            f"--- Trecho {i} ({n.intervalo}) ---\n"
            + json.dumps(n.model_dump(), ensure_ascii=False, indent=1)
            for i, n in enumerate(notas, start=1)
        )
        return self._chamar(
            P.usuario_consolidacao(
                contexto=contexto,
                glossario=texto_glossario,
                instrucoes_extras=self._config.instrucoes_extras,
                notas=notas_texto,
            ),
            ResumoAula,
        )
