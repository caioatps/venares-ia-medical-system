"""Operacoes no Google Drive: listar a pasta, descobrir o proximo numero e subir arquivos."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from ..config import Ambiente
from ..logging_setup import log
from .auth import obter_credenciais

_LOG = log(__name__)

PASTA = "application/vnd.google-apps.folder"
_TENTATIVAS = 4


class ErroDrive(RuntimeError):
    pass


@dataclass(frozen=True)
class ArquivoDrive:
    id: str
    nome: str
    mime: str
    link: str

    @property
    def e_pasta(self) -> bool:
        return self.mime == PASTA


def _escapar(valor: str) -> str:
    return valor.replace("\\", "\\\\").replace("'", "\\'")


def _vale_retentar(erro: HttpError) -> bool:
    """Distingue erro transitorio de erro de permissao.

    O Google usa 403 tanto para "sem permissao" (nao adianta insistir)
    quanto para limite de taxa (adianta) - a diferenca esta no motivo.
    """
    status = erro.resp.status
    if status in (429, 500, 502, 503, 504):
        return True
    if status == 403:
        conteudo = (erro.content or b"").lower()
        return b"ratelimit" in conteudo or b"quotaexceeded" in conteudo
    return False


class ClienteDrive:
    def __init__(self, ambiente: Ambiente) -> None:
        self._servico = build(
            "drive", "v3", credentials=obter_credenciais(ambiente), cache_discovery=False
        )

    # -- util ---------------------------------------------------------------
    def _executar(self, requisicao) -> Any:
        """Executa com retentativa em erro transitorio do Google."""
        ultimo: Exception | None = None
        for tentativa in range(_TENTATIVAS):
            try:
                return requisicao.execute()
            except HttpError as erro:
                ultimo = erro
                if _vale_retentar(erro):
                    espera = 2 ** tentativa
                    _LOG.warning(
                        "Drive respondeu %s; nova tentativa em %ss", erro.resp.status, espera
                    )
                    time.sleep(espera)
                    continue
                raise ErroDrive(f"Erro do Google Drive: {erro}") from erro
        raise ErroDrive(f"Google Drive falhou apos {_TENTATIVAS} tentativas: {ultimo}")

    def _parametros_drive(self, drive_compartilhado_id: str | None) -> dict[str, Any]:
        if drive_compartilhado_id:
            return {
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
                "corpora": "drive",
                "driveId": drive_compartilhado_id,
            }
        return {"supportsAllDrives": True, "includeItemsFromAllDrives": True}

    # -- leitura ------------------------------------------------------------
    def listar_pasta(
        self, pasta_id: str, *, drive_compartilhado_id: str | None = None
    ) -> list[ArquivoDrive]:
        itens: list[ArquivoDrive] = []
        pagina: str | None = None
        base = self._parametros_drive(drive_compartilhado_id)
        while True:
            parametros: dict[str, Any] = {
                "q": f"'{_escapar(pasta_id)}' in parents and trashed = false",
                "fields": "nextPageToken, files(id, name, mimeType, webViewLink)",
                "pageSize": 1000,
                "orderBy": "name",
                **base,
            }
            if pagina:
                parametros["pageToken"] = pagina
            resposta = self._executar(self._servico.files().list(**parametros))
            for arquivo in resposta.get("files", []):
                itens.append(
                    ArquivoDrive(
                        id=arquivo["id"],
                        nome=arquivo.get("name", ""),
                        mime=arquivo.get("mimeType", ""),
                        link=arquivo.get("webViewLink", ""),
                    )
                )
            pagina = resposta.get("nextPageToken")
            if not pagina:
                return itens

    def nomes_na_pasta(
        self, pasta_id: str, *, drive_compartilhado_id: str | None = None, recursivo: bool = True
    ) -> list[str]:
        """Nomes de arquivos e subpastas - a base da numeracao sequencial.

        Com `recursivo`, entra um nivel nas subpastas (util quando cada aula
        tem a propria pasta e o numero esta no nome dos arquivos dentro).
        """
        itens = self.listar_pasta(pasta_id, drive_compartilhado_id=drive_compartilhado_id)
        nomes = [i.nome for i in itens]
        if recursivo:
            for item in itens:
                if item.e_pasta:
                    nomes.extend(
                        f.nome
                        for f in self.listar_pasta(
                            item.id, drive_compartilhado_id=drive_compartilhado_id
                        )
                    )
        return nomes

    def verificar_pasta(
        self, pasta_id: str, *, drive_compartilhado_id: str | None = None
    ) -> ArquivoDrive:
        arquivo = self._executar(
            self._servico.files().get(
                fileId=pasta_id,
                fields="id, name, mimeType, webViewLink",
                supportsAllDrives=True,
            )
        )
        item = ArquivoDrive(
            id=arquivo["id"],
            nome=arquivo.get("name", ""),
            mime=arquivo.get("mimeType", ""),
            link=arquivo.get("webViewLink", ""),
        )
        if not item.e_pasta:
            raise ErroDrive(f"O ID {pasta_id} nao e uma pasta ({item.mime}).")
        return item

    # -- escrita ------------------------------------------------------------
    def criar_pasta(
        self, nome: str, pai_id: str, *, drive_compartilhado_id: str | None = None
    ) -> ArquivoDrive:
        existente = next(
            (
                i
                for i in self.listar_pasta(
                    pai_id, drive_compartilhado_id=drive_compartilhado_id
                )
                if i.e_pasta and i.nome == nome
            ),
            None,
        )
        if existente:
            return existente
        criado = self._executar(
            self._servico.files().create(
                body={"name": nome, "mimeType": PASTA, "parents": [pai_id]},
                fields="id, name, mimeType, webViewLink",
                supportsAllDrives=True,
            )
        )
        return ArquivoDrive(
            id=criado["id"],
            nome=criado.get("name", nome),
            mime=PASTA,
            link=criado.get("webViewLink", ""),
        )

    def enviar(
        self,
        caminho: Path,
        *,
        nome: str,
        pasta_id: str,
        mime: str | None = None,
        drive_compartilhado_id: str | None = None,
    ) -> ArquivoDrive:
        """Upload retomavel - video de aula costuma passar de 1 GB."""
        if not caminho.exists():
            raise ErroDrive(f"Arquivo inexistente para upload: {caminho}")
        midia = MediaFileUpload(
            str(caminho),
            mimetype=mime,
            resumable=True,
            chunksize=8 * 1024 * 1024,
        )
        requisicao = self._servico.files().create(
            body={"name": nome, "parents": [pasta_id]},
            media_body=midia,
            fields="id, name, mimeType, webViewLink",
            supportsAllDrives=True,
        )
        _LOG.info("Enviando %s (%.1f MB) para o Drive", nome, caminho.stat().st_size / 1e6)
        resposta = None
        progresso_anterior = 0
        while resposta is None:
            try:
                status, resposta = requisicao.next_chunk()
            except HttpError as erro:
                if _vale_retentar(erro):
                    _LOG.warning("Upload interrompido (%s); retomando.", erro.resp.status)
                    time.sleep(3)
                    continue
                raise ErroDrive(f"Falha no upload de {nome}: {erro}") from erro
            if status:
                atual = int(status.progress() * 100)
                if atual >= progresso_anterior + 20:
                    _LOG.info("  %s: %d%%", nome, atual)
                    progresso_anterior = atual
        return ArquivoDrive(
            id=resposta["id"],
            nome=resposta.get("name", nome),
            mime=resposta.get("mimeType", mime or ""),
            link=resposta.get("webViewLink", ""),
        )

    def compartilhar_com_leitura(self, arquivo_id: str, email: str) -> None:
        self._executar(
            self._servico.permissions().create(
                fileId=arquivo_id,
                body={"type": "user", "role": "reader", "emailAddress": email},
                sendNotificationEmail=False,
                supportsAllDrives=True,
            )
        )
