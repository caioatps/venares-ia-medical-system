"""Token de acesso do Zoom via Server-to-Server OAuth, com cache em memoria."""

from __future__ import annotations

import threading
import time

import requests

from ..config import Ambiente

URL_TOKEN = "https://zoom.us/oauth/token"
_MARGEM_SEGURANCA_S = 60


class ErroAutenticacaoZoom(RuntimeError):
    pass


class TokenZoom:
    """Busca e reaproveita o access token enquanto ele for valido."""

    def __init__(self, ambiente: Ambiente, tempo_limite_s: int = 30) -> None:
        ambiente.exigir("zoom_account_id", "zoom_client_id", "zoom_client_secret")
        self._ambiente = ambiente
        self._tempo_limite = tempo_limite_s
        self._token: str | None = None
        self._expira_em: float = 0.0
        self._trava = threading.Lock()

    def obter(self) -> str:
        with self._trava:
            if self._token and time.time() < self._expira_em:
                return self._token
            self._token, self._expira_em = self._renovar()
            return self._token

    def invalidar(self) -> None:
        with self._trava:
            self._token = None
            self._expira_em = 0.0

    def _renovar(self) -> tuple[str, float]:
        amb = self._ambiente
        resposta = requests.post(
            URL_TOKEN,
            params={
                "grant_type": "account_credentials",
                "account_id": amb.zoom_account_id,
            },
            auth=(amb.zoom_client_id, amb.zoom_client_secret),
            timeout=self._tempo_limite,
        )
        if resposta.status_code != 200:
            raise ErroAutenticacaoZoom(
                f"Falha ao obter token do Zoom ({resposta.status_code}): {resposta.text[:500]}"
            )
        dados = resposta.json()
        token = dados.get("access_token")
        if not token:
            raise ErroAutenticacaoZoom(f"Resposta do Zoom sem access_token: {dados}")
        validade = int(dados.get("expires_in", 3600))
        return token, time.time() + validade - _MARGEM_SEGURANCA_S
