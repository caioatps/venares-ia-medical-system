"""Estado persistente: uma fila de trabalhos em SQLite.

Guarda o que ja foi processado (para nunca duplicar upload) e o que esta
aguardando a transcricao do Zoom ficar pronta. Sobrevive a reinicio do
container -- o que importa quando o webhook chega antes da transcricao.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

PENDENTE = "pendente"
PROCESSANDO = "processando"
CONCLUIDO = "concluido"
ERRO = "erro"
IGNORADO = "ignorado"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS trabalhos (
    uuid                TEXT PRIMARY KEY,
    meeting_id          TEXT,
    titulo              TEXT,
    inicio              TEXT,
    status              TEXT NOT NULL,
    tentativas          INTEGER NOT NULL DEFAULT 0,
    primeira_vez_em     REAL NOT NULL,
    proxima_tentativa   REAL NOT NULL DEFAULT 0,
    atualizado_em       REAL NOT NULL,
    mentoria            TEXT,
    numero_aula         INTEGER,
    drive_video_id      TEXT,
    drive_pdf_id        TEXT,
    erro                TEXT,
    extra               TEXT
);
CREATE INDEX IF NOT EXISTS idx_trabalhos_status ON trabalhos(status, proxima_tentativa);
"""


@dataclass
class Trabalho:
    uuid: str
    meeting_id: str | None
    titulo: str | None
    inicio: str | None
    status: str
    tentativas: int
    primeira_vez_em: float
    proxima_tentativa: float
    mentoria: str | None = None
    numero_aula: int | None = None
    drive_video_id: str | None = None
    drive_pdf_id: str | None = None
    erro: str | None = None
    extra: dict[str, Any] | None = None

    @classmethod
    def de_linha(cls, linha: sqlite3.Row) -> "Trabalho":
        return cls(
            uuid=linha["uuid"],
            meeting_id=linha["meeting_id"],
            titulo=linha["titulo"],
            inicio=linha["inicio"],
            status=linha["status"],
            tentativas=linha["tentativas"],
            primeira_vez_em=linha["primeira_vez_em"],
            proxima_tentativa=linha["proxima_tentativa"],
            mentoria=linha["mentoria"],
            numero_aula=linha["numero_aula"],
            drive_video_id=linha["drive_video_id"],
            drive_pdf_id=linha["drive_pdf_id"],
            erro=linha["erro"],
            extra=json.loads(linha["extra"]) if linha["extra"] else None,
        )


class Banco:
    def __init__(self, caminho: str | Path) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._conexao = sqlite3.connect(self.caminho, check_same_thread=False)
        self._conexao.row_factory = sqlite3.Row
        self._conexao.execute("PRAGMA journal_mode=WAL")
        self._conexao.executescript(_ESQUEMA)
        self._conexao.commit()

    def fechar(self) -> None:
        self._conexao.close()

    # -- escrita ------------------------------------------------------------
    def registrar(
        self,
        uuid: str,
        *,
        meeting_id: str | None = None,
        titulo: str | None = None,
        inicio: str | None = None,
    ) -> Trabalho:
        """Cria o trabalho se ainda nao existir; devolve o estado atual."""
        agora = time.time()
        with self._conexao as cx:
            cx.execute(
                """
                INSERT INTO trabalhos (uuid, meeting_id, titulo, inicio, status,
                                       primeira_vez_em, proxima_tentativa, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET
                    meeting_id    = COALESCE(excluded.meeting_id, trabalhos.meeting_id),
                    titulo        = COALESCE(excluded.titulo, trabalhos.titulo),
                    inicio        = COALESCE(excluded.inicio, trabalhos.inicio),
                    atualizado_em = excluded.atualizado_em
                """,
                (uuid, meeting_id, titulo, inicio, PENDENTE, agora, agora, agora),
            )
        trabalho = self.obter(uuid)
        assert trabalho is not None
        return trabalho

    def atualizar(self, uuid: str, **campos: Any) -> None:
        if not campos:
            return
        if "extra" in campos and campos["extra"] is not None:
            campos["extra"] = json.dumps(campos["extra"], ensure_ascii=False)
        # Carimba a hora da atualizacao, a menos que o chamador informe uma
        # (usado para reposicionar um registro no tempo).
        campos.setdefault("atualizado_em", time.time())
        atribuicoes = ", ".join(f"{c} = ?" for c in campos)
        with self._conexao as cx:
            cx.execute(
                f"UPDATE trabalhos SET {atribuicoes} WHERE uuid = ?",
                (*campos.values(), uuid),
            )

    def marcar_erro(self, uuid: str, mensagem: str, *, reagendar_em_s: float | None = None) -> None:
        campos: dict[str, Any] = {"erro": mensagem[:4000]}
        if reagendar_em_s is None:
            campos["status"] = ERRO
        else:
            campos["status"] = PENDENTE
            campos["proxima_tentativa"] = time.time() + reagendar_em_s
        self.atualizar(uuid, **campos)

    def incrementar_tentativa(self, uuid: str) -> None:
        with self._conexao as cx:
            cx.execute(
                "UPDATE trabalhos SET tentativas = tentativas + 1, atualizado_em = ? WHERE uuid = ?",
                (time.time(), uuid),
            )

    # -- leitura ------------------------------------------------------------
    def obter(self, uuid: str) -> Trabalho | None:
        linha = self._conexao.execute(
            "SELECT * FROM trabalhos WHERE uuid = ?", (uuid,)
        ).fetchone()
        return Trabalho.de_linha(linha) if linha else None

    def ja_concluido(self, uuid: str) -> bool:
        trabalho = self.obter(uuid)
        return bool(trabalho and trabalho.status == CONCLUIDO)

    def pendentes_vencidos(self, limite: int = 20) -> list[Trabalho]:
        linhas = self._conexao.execute(
            """
            SELECT * FROM trabalhos
            WHERE status = ? AND proxima_tentativa <= ?
            ORDER BY primeira_vez_em ASC
            LIMIT ?
            """,
            (PENDENTE, time.time(), limite),
        ).fetchall()
        return [Trabalho.de_linha(l) for l in linhas]

    def listar(self, status: str | None = None, limite: int = 50) -> list[Trabalho]:
        if status:
            linhas = self._conexao.execute(
                "SELECT * FROM trabalhos WHERE status = ? ORDER BY primeira_vez_em DESC LIMIT ?",
                (status, limite),
            ).fetchall()
        else:
            linhas = self._conexao.execute(
                "SELECT * FROM trabalhos ORDER BY primeira_vez_em DESC LIMIT ?", (limite,)
            ).fetchall()
        return [Trabalho.de_linha(l) for l in linhas]

    def numeros_ja_usados(self, mentoria: str, *, janela_s: float = 3600) -> set[int]:
        """Numeros de aula que este sistema considera ocupados.

        Trava extra contra numero repetido quando duas gravacoes terminam
        quase juntas e a listagem do Drive ainda nao reflete o upload
        anterior.

        So conta o que foi concluido e o que ainda esta em andamento
        (atualizado dentro da janela). Um numero atribuido a uma tentativa
        que falhou ha muito tempo e liberado - do contrario, cada erro
        deixaria um buraco permanente na sequencia.
        """
        linhas = self._conexao.execute(
            """
            SELECT numero_aula FROM trabalhos
            WHERE mentoria = ? AND numero_aula IS NOT NULL
              AND (status = ? OR atualizado_em >= ?)
            """,
            (mentoria, CONCLUIDO, time.time() - janela_s),
        ).fetchall()
        return {int(l["numero_aula"]) for l in linhas}

    def uuids(self, status: str | None = None) -> Iterable[str]:
        return (t.uuid for t in self.listar(status=status, limite=1000))
