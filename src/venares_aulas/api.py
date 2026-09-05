"""Servidor de webhook do Zoom.

Fluxo:
  1. O Zoom chama POST /webhooks/zoom quando a gravacao (ou a transcricao)
     fica pronta na nuvem.
  2. A assinatura e conferida, o trabalho e gravado no SQLite e a resposta
     sai em milissegundos - o Zoom desiste de webhooks lentos.
  3. Um worker em segundo plano processa um trabalho por vez (video grande
     nao pode disputar banda com outro) e um agendador reexamina os
     pendentes, cobrindo webhook perdido e transcricao que demorou.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, AsyncIterator

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, Response

from .config import Ambiente, Config, carregar_config
from .db import Banco
from .logging_setup import configurar_logging, log
from .pipeline import Pipeline
from .zoom import webhook as wh

_LOG = log(__name__)

INTERVALO_AGENDADOR_S = 60


def criar_app(config: Config | None = None, ambiente: Ambiente | None = None) -> FastAPI:
    configurar_logging()
    config = config or carregar_config()
    ambiente = ambiente or Ambiente.do_ambiente()
    ambiente.exigir("zoom_secret_token")

    banco = Banco(ambiente.banco)
    pipeline = Pipeline(config, ambiente, banco=banco)
    fila: asyncio.Queue[str] = asyncio.Queue()
    # O webhook e o agendador podem apontar para a mesma gravacao; este
    # conjunto evita processar duas vezes a mesma coisa em sequencia.
    enfileirados: set[str] = set()

    async def enfileirar(uuid: str) -> bool:
        if uuid in enfileirados:
            return False
        enfileirados.add(uuid)
        await fila.put(uuid)
        return True

    async def _worker() -> None:
        """Processa um trabalho por vez, fora do laco de eventos."""
        while True:
            uuid = await fila.get()
            try:
                await asyncio.to_thread(pipeline.processar_com_retentativa, uuid)
            except Exception:  # noqa: BLE001
                _LOG.exception("Worker falhou processando %s", uuid)
            finally:
                enfileirados.discard(uuid)
                fila.task_done()

    async def _agendador() -> None:
        """Reenfileira o que ficou pendente (transcricao atrasada, falha transitoria)."""
        while True:
            await asyncio.sleep(INTERVALO_AGENDADOR_S)
            try:
                for trabalho in await asyncio.to_thread(banco.pendentes_vencidos):
                    if await enfileirar(trabalho.uuid):
                        _LOG.info("Reenfileirando %s (%s)", trabalho.titulo, trabalho.uuid)
            except Exception:  # noqa: BLE001
                _LOG.exception("Agendador falhou")

    @contextlib.asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        tarefas = [asyncio.create_task(_worker()), asyncio.create_task(_agendador())]
        _LOG.info(
            "Servidor pronto. Mentorias: %s",
            ", ".join(f"{m.id} -> {m.nome}" for m in config.mentorias),
        )
        try:
            yield
        finally:
            for tarefa in tarefas:
                tarefa.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await tarefa
            banco.fechar()

    app = FastAPI(title="Venares Aulas", version="0.1.0", lifespan=ciclo_de_vida)
    app.state.config = config
    app.state.ambiente = ambiente
    app.state.banco = banco
    app.state.pipeline = pipeline
    app.state.fila = fila

    # -- endpoints ---------------------------------------------------------
    @app.get("/health")
    async def saude() -> dict[str, Any]:
        return {
            "ok": True,
            "fila": fila.qsize(),
            "mentorias": [m.id for m in config.mentorias],
        }

    @app.post("/webhooks/zoom")
    async def webhook_zoom(
        request: Request,
        x_zm_signature: str | None = Header(default=None),
        x_zm_request_timestamp: str | None = Header(default=None),
    ) -> Any:
        corpo = await request.body()
        if not wh.verificar_assinatura(
            ambiente.zoom_secret_token, corpo, x_zm_signature, x_zm_request_timestamp
        ):
            _LOG.warning("Webhook com assinatura invalida recusado.")
            raise HTTPException(status_code=401, detail="assinatura invalida")

        payload = await request.json()

        # Desafio de validacao da URL no cadastro do app.
        if payload.get("event") == wh.EVENTO_VALIDACAO:
            return wh.resposta_validacao_url(ambiente.zoom_secret_token, payload)

        evento = wh.ler_evento(payload)
        if not evento.tratado or not evento.uuid:
            return {"ignorado": evento.tipo}

        if banco.ja_concluido(evento.uuid):
            _LOG.info("Evento %s de gravacao ja concluida; ignorado.", evento.tipo)
            return {"ja_processado": evento.uuid}

        await asyncio.to_thread(
            banco.registrar,
            evento.uuid,
            meeting_id=evento.meeting_id,
            titulo=evento.titulo,
            inicio=evento.inicio,
        )
        _LOG.info("Evento %s recebido: %r", evento.tipo, evento.titulo)

        # `recording.completed` chega antes da transcricao existir. Enfileirar
        # mesmo assim e barato: o pipeline detecta e reagenda sozinho.
        novo = await enfileirar(evento.uuid)
        return {"recebido": evento.tipo, "uuid": evento.uuid, "enfileirado": novo}

    # -- administracao ------------------------------------------------------
    def _conferir_admin(chave: str | None) -> None:
        if not ambiente.admin_api_key:
            raise HTTPException(status_code=503, detail="ADMIN_API_KEY nao configurada")
        if chave != ambiente.admin_api_key:
            raise HTTPException(status_code=401, detail="chave administrativa invalida")

    @app.post("/admin/reprocessar/{uuid:path}")
    async def reprocessar(
        uuid: str,
        tarefas: BackgroundTasks,
        x_admin_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _conferir_admin(x_admin_key)
        tarefas.add_task(pipeline.processar_com_retentativa, uuid, forcar=True)
        return {"reprocessando": uuid}

    @app.get("/admin/trabalhos")
    async def trabalhos(
        status: str | None = None,
        limite: int = 50,
        x_admin_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _conferir_admin(x_admin_key)
        itens = banco.listar(status=status, limite=limite)
        return {
            "total": len(itens),
            "trabalhos": [
                {
                    "uuid": t.uuid,
                    "titulo": t.titulo,
                    "status": t.status,
                    "mentoria": t.mentoria,
                    "numero_aula": t.numero_aula,
                    "tentativas": t.tentativas,
                    "erro": t.erro,
                }
                for t in itens
            ],
        }

    @app.get("/", include_in_schema=False)
    async def raiz() -> Response:
        return Response(content="Venares Aulas em execucao.", media_type="text/plain")

    return app


app = None  # criado sob demanda por `uvicorn venares_aulas.api:obter_app`


def obter_app() -> FastAPI:
    global app
    if app is None:
        app = criar_app()
    return app
