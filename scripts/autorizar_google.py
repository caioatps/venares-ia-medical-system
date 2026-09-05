#!/usr/bin/env python3
"""Gera o GOOGLE_REFRESH_TOKEN para o .env.

Passo a passo:
  1. No Google Cloud Console, crie um projeto e ative a Google Drive API.
  2. Em "Credenciais", crie um OAuth client ID do tipo "Desktop app".
  3. Baixe o JSON e rode:

        python scripts/autorizar_google.py caminho/do/client_secret.json

  4. Faca login com a conta dona do Drive e autorize.
  5. Copie as tres linhas impressas para o seu .env.
"""

from __future__ import annotations

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ESCOPO = ["https://www.googleapis.com/auth/drive"]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    segredo = Path(sys.argv[1])
    if not segredo.exists():
        print(f"Arquivo nao encontrado: {segredo}")
        return 1

    fluxo = InstalledAppFlow.from_client_secrets_file(str(segredo), ESCOPO)
    # access_type=offline + prompt=consent garantem que venha o refresh token.
    credenciais = fluxo.run_local_server(
        port=0, access_type="offline", prompt="consent", open_browser=True
    )
    if not credenciais.refresh_token:
        print(
            "O Google nao devolveu refresh token. Revogue o acesso do app em "
            "https://myaccount.google.com/permissions e rode de novo."
        )
        return 1

    print("\nCopie para o seu .env:\n")
    print(f"GOOGLE_CLIENT_ID={credenciais.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={credenciais.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={credenciais.refresh_token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
