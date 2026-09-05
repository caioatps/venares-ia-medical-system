import time

from venares_aulas.zoom.webhook import (
    EVENTO_TRANSCRICAO_PRONTA,
    ler_evento,
    resposta_validacao_url,
    verificar_assinatura,
)
import hashlib
import hmac

SEGREDO = "segredo-de-teste"


def assinar(corpo: bytes, timestamp: str) -> str:
    mensagem = f"v0:{timestamp}:{corpo.decode()}"
    return "v0=" + hmac.new(SEGREDO.encode(), mensagem.encode(), hashlib.sha256).hexdigest()


def test_assinatura_valida():
    corpo = b'{"event":"recording.completed"}'
    ts = str(int(time.time()))
    assert verificar_assinatura(SEGREDO, corpo, assinar(corpo, ts), ts)


def test_assinatura_invalida():
    corpo = b'{"event":"recording.completed"}'
    ts = str(int(time.time()))
    assert not verificar_assinatura(SEGREDO, corpo, "v0=abc", ts)


def test_corpo_alterado_invalida_assinatura():
    ts = str(int(time.time()))
    assinatura = assinar(b'{"event":"a"}', ts)
    assert not verificar_assinatura(SEGREDO, b'{"event":"b"}', assinatura, ts)


def test_requisicao_antiga_e_recusada():
    corpo = b"{}"
    ts = str(int(time.time()) - 3600)
    assert not verificar_assinatura(SEGREDO, corpo, assinar(corpo, ts), ts)


def test_faltando_cabecalho():
    assert not verificar_assinatura(SEGREDO, b"{}", None, None)
    assert not verificar_assinatura("", b"{}", "v0=x", "123")


def test_desafio_de_validacao_da_url():
    payload = {"event": "endpoint.url_validation", "payload": {"plainToken": "abc123"}}
    resposta = resposta_validacao_url(SEGREDO, payload)
    assert resposta["plainToken"] == "abc123"
    esperado = hmac.new(SEGREDO.encode(), b"abc123", hashlib.sha256).hexdigest()
    assert resposta["encryptedToken"] == esperado


def test_le_evento_de_transcricao():
    payload = {
        "event": EVENTO_TRANSCRICAO_PRONTA,
        "payload": {
            "object": {
                "uuid": "abc/def==",
                "id": "8123456789",
                "topic": "Mentoria Start - Aula 4",
                "start_time": "2026-03-17T13:00:00Z",
                "duration": 92,
            }
        },
    }
    evento = ler_evento(payload)
    assert evento.tratado and evento.tem_transcricao
    assert evento.uuid == "abc/def=="
    assert evento.titulo == "Mentoria Start - Aula 4"
    assert evento.duracao_min == 92


def test_evento_irrelevante_nao_e_tratado():
    assert not ler_evento({"event": "meeting.started", "payload": {}}).tratado
