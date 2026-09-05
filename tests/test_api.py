"""Teste de ponta a ponta do endpoint de webhook, sem tocar em Zoom/Drive."""

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from venares_aulas import db
from venares_aulas.api import criar_app
from venares_aulas.config import (
    Ambiente,
    Config,
    ConfigNotificacao,
    ConfigPdf,
    ConfigResumo,
    ConfigWhatsapp,
    ConfigZoom,
    Mentoria,
    Nomeacao,
)

SEGREDO = "segredo-de-teste"


@pytest.fixture
def ambiente(tmp_path) -> Ambiente:
    vazio = dict.fromkeys(
        [
            "zoom_account_id", "zoom_client_id", "zoom_client_secret",
            "anthropic_api_key", "google_client_id", "google_client_secret",
            "google_refresh_token", "google_service_account_file",
            "google_delegar_para", "meta_whatsapp_token",
            "meta_whatsapp_phone_number_id", "twilio_account_sid",
            "twilio_auth_token", "twilio_whatsapp_from",
        ],
        "",
    )
    return Ambiente(
        zoom_secret_token=SEGREDO,
        admin_api_key="chave-admin",
        dir_trabalho=tmp_path / "trabalho",
        banco=tmp_path / "banco.db",
        **vazio,
    )


@pytest.fixture
def config() -> Config:
    return Config(
        fuso_horario="America/Sao_Paulo",
        idioma="pt-BR",
        mentorias=[
            Mentoria(id="start", nome="Mentoria Start", palavras_chave=["start"], pasta_drive_id="p1")
        ],
        mentoria_padrao=None,
        nomeacao=Nomeacao(),
        zoom=ConfigZoom(),
        resumo=ConfigResumo(),
        pdf=ConfigPdf(),
        notificacao=ConfigNotificacao(whatsapp=ConfigWhatsapp(ativo=False)),
    )


@pytest.fixture
def cliente(config, ambiente):
    app = criar_app(config, ambiente)
    with TestClient(app) as c:
        c.app_ref = app
        yield c


def assinar(corpo: bytes) -> dict[str, str]:
    ts = str(int(time.time()))
    mensagem = f"v0:{ts}:{corpo.decode()}"
    return {
        "x-zm-request-timestamp": ts,
        "x-zm-signature": "v0="
        + hmac.new(SEGREDO.encode(), mensagem.encode(), hashlib.sha256).hexdigest(),
        "content-type": "application/json",
    }


def enviar(cliente, payload: dict):
    corpo = json.dumps(payload).encode()
    return cliente.post("/webhooks/zoom", content=corpo, headers=assinar(corpo))


def test_health(cliente):
    resposta = cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json()["ok"] is True


def test_webhook_sem_assinatura_e_recusado(cliente):
    resposta = cliente.post("/webhooks/zoom", json={"event": "recording.completed"})
    assert resposta.status_code == 401


def test_webhook_com_assinatura_errada_e_recusado(cliente):
    corpo = json.dumps({"event": "recording.completed"}).encode()
    resposta = cliente.post(
        "/webhooks/zoom",
        content=corpo,
        headers={"x-zm-signature": "v0=errado", "x-zm-request-timestamp": str(int(time.time()))},
    )
    assert resposta.status_code == 401


def test_desafio_de_validacao_da_url(cliente):
    resposta = enviar(
        cliente, {"event": "endpoint.url_validation", "payload": {"plainToken": "tok123"}}
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["plainToken"] == "tok123"
    assert corpo["encryptedToken"] == hmac.new(
        SEGREDO.encode(), b"tok123", hashlib.sha256
    ).hexdigest()


def test_evento_de_transcricao_registra_o_trabalho(cliente):
    payload = {
        "event": "recording.transcript_completed",
        "payload": {
            "object": {
                "uuid": "uuid-aula-1",
                "id": "812",
                "topic": "Mentoria Start - Aula 4",
                "start_time": "2026-03-17T13:00:00Z",
                "duration": 95,
            }
        },
    }
    assert enviar(cliente, payload).status_code == 200
    trabalho = cliente.app_ref.state.banco.obter("uuid-aula-1")
    assert trabalho is not None
    assert trabalho.titulo == "Mentoria Start - Aula 4"
    assert trabalho.status == db.PENDENTE


def test_evento_irrelevante_e_ignorado(cliente):
    resposta = enviar(cliente, {"event": "meeting.started", "payload": {"object": {}}})
    assert resposta.json() == {"ignorado": "meeting.started"}


def test_gravacao_ja_concluida_nao_e_reenfileirada(cliente):
    banco = cliente.app_ref.state.banco
    banco.registrar("uuid-pronta")
    banco.atualizar("uuid-pronta", status=db.CONCLUIDO)
    payload = {
        "event": "recording.completed",
        "payload": {"object": {"uuid": "uuid-pronta", "id": "1", "topic": "x", "duration": 90}},
    }
    assert enviar(cliente, payload).json() == {"ja_processado": "uuid-pronta"}


def test_admin_exige_chave(cliente):
    assert cliente.get("/admin/trabalhos").status_code == 401
    resposta = cliente.get("/admin/trabalhos", headers={"x-admin-key": "chave-admin"})
    assert resposta.status_code == 200
    assert "trabalhos" in resposta.json()
