"""Validacao e leitura dos eventos de webhook do Zoom.

O Zoom assina cada requisicao com HMAC-SHA256 sobre
    v0:{timestamp}:{corpo cru}
usando o "Secret Token" do app. Alem disso, ao cadastrar a URL, ele manda
um evento `endpoint.url_validation` que precisa ser respondido com o
plainToken devolvido e o mesmo token cifrado com HMAC.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

# Eventos que interessam ao fluxo das aulas.
EVENTO_VALIDACAO = "endpoint.url_validation"
EVENTO_GRAVACAO_PRONTA = "recording.completed"
EVENTO_TRANSCRICAO_PRONTA = "recording.transcript_completed"
EVENTOS_TRATADOS = {EVENTO_GRAVACAO_PRONTA, EVENTO_TRANSCRICAO_PRONTA}

# Tolerancia para o timestamp da requisicao (protecao contra replay).
JANELA_MAXIMA_S = 5 * 60


def _assinar(segredo: str, mensagem: str) -> str:
    return hmac.new(
        segredo.encode("utf-8"), mensagem.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verificar_assinatura(
    segredo: str,
    corpo: bytes,
    assinatura: str | None,
    timestamp: str | None,
    *,
    agora: float | None = None,
) -> bool:
    """Confere o cabecalho x-zm-signature de uma requisicao do Zoom."""
    if not segredo or not assinatura or not timestamp:
        return False
    try:
        enviado_em = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs((agora if agora is not None else time.time()) - enviado_em) > JANELA_MAXIMA_S:
        return False
    esperado = "v0=" + _assinar(segredo, f"v0:{timestamp}:{corpo.decode('utf-8')}")
    return hmac.compare_digest(esperado, assinatura)


def resposta_validacao_url(segredo: str, payload: dict[str, Any]) -> dict[str, str]:
    """Monta a resposta do desafio `endpoint.url_validation`."""
    plain = str((payload.get("payload") or {}).get("plainToken", ""))
    return {"plainToken": plain, "encryptedToken": _assinar(segredo, plain)}


@dataclass(frozen=True)
class EventoZoom:
    tipo: str
    uuid: str
    meeting_id: str
    titulo: str
    inicio: str
    duracao_min: int
    bruto: dict[str, Any]

    @property
    def tratado(self) -> bool:
        return self.tipo in EVENTOS_TRATADOS

    @property
    def tem_transcricao(self) -> bool:
        return self.tipo == EVENTO_TRANSCRICAO_PRONTA


def ler_evento(payload: dict[str, Any]) -> EventoZoom:
    objeto = ((payload.get("payload") or {}).get("object")) or {}
    return EventoZoom(
        tipo=str(payload.get("event", "")),
        uuid=str(objeto.get("uuid", "")),
        meeting_id=str(objeto.get("id", "")),
        titulo=str(objeto.get("topic", "")).strip(),
        inicio=str(objeto.get("start_time", "")),
        duracao_min=int(objeto.get("duration") or 0),
        bruto=payload,
    )
