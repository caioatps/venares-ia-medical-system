"""Credenciais do Google Drive.

Dois caminhos suportados:

* OAuth do proprio usuario (recomendado para o "Meu Drive" pessoal): os
  arquivos ficam com voce como dono e consomem a sua cota.
* Conta de servico (Workspace / Drive Compartilhado): sem interacao, mas
  uma conta de servico nao tem cota propria no "Meu Drive" - use apenas
  com Drive Compartilhado ou com delegacao em todo o dominio.
"""

from __future__ import annotations

from pathlib import Path

from google.oauth2.credentials import Credentials as CredenciaisUsuario
from google.oauth2.service_account import Credentials as CredenciaisServico

from ..config import Ambiente, ErroConfig

ESCOPO = ["https://www.googleapis.com/auth/drive"]
URL_TOKEN = "https://oauth2.googleapis.com/token"


def obter_credenciais(ambiente: Ambiente):
    if ambiente.google_service_account_file:
        caminho = Path(ambiente.google_service_account_file)
        if not caminho.exists():
            raise ErroConfig(f"GOOGLE_SERVICE_ACCOUNT_FILE nao encontrado: {caminho}")
        credenciais = CredenciaisServico.from_service_account_file(
            str(caminho), scopes=ESCOPO
        )
        if ambiente.google_delegar_para:
            credenciais = credenciais.with_subject(ambiente.google_delegar_para)
        return credenciais

    ambiente.exigir("google_client_id", "google_client_secret", "google_refresh_token")
    return CredenciaisUsuario(
        token=None,
        refresh_token=ambiente.google_refresh_token,
        client_id=ambiente.google_client_id,
        client_secret=ambiente.google_client_secret,
        token_uri=URL_TOKEN,
        scopes=ESCOPO,
    )
