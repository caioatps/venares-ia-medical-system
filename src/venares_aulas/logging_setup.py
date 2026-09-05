"""Configuracao unica de logging para a API e para a CLI."""

from __future__ import annotations

import logging
import os
import sys

_FORMATO = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"


def configurar_logging(nivel: str | None = None) -> None:
    nivel = (nivel or os.getenv("LOG_LEVEL") or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, nivel, logging.INFO),
        format=_FORMATO,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    # Bibliotecas verbosas demais em nivel INFO.
    for ruidoso in ("googleapiclient.discovery_cache", "urllib3", "httpx", "httpcore"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


def log(nome: str) -> logging.Logger:
    return logging.getLogger(nome)
