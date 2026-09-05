"""Aviso por WhatsApp para o responsavel de TI.

Dois provedores:

* "meta"   - WhatsApp Cloud API (graph.facebook.com). Fora da janela de 24h
             so passa mensagem de template aprovado, por isso o template e o
             caminho padrao aqui.
* "twilio" - API do Twilio para WhatsApp.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from ..config import Ambiente, ConfigWhatsapp
from ..logging_setup import log

_LOG = log(__name__)
VERSAO_GRAPH = "v21.0"


class ErroNotificacao(RuntimeError):
    pass


@dataclass(frozen=True)
class AvisoAula:
    mentoria: str
    numero: int
    data: str
    titulo: str
    link_video: str
    link_resumo: str
    link_pasta: str = ""

    def parametros_template(self) -> list[str]:
        # Ordem documentada em config.yaml: {{1}}..{{5}}
        return [
            self.mentoria,
            f"{self.numero:02d}",
            self.data,
            self.link_video or "-",
            self.link_resumo or "-",
        ]

    def texto(self) -> str:
        linhas = [
            "Nova aula pronta para publicacao na plataforma.",
            "",
            f"Mentoria: {self.mentoria}",
            f"Aula: {self.numero:02d}",
            f"Data: {self.data}",
            f"Titulo: {self.titulo}",
            "",
            f"Video: {self.link_video or '-'}",
            f"Resumo (PDF): {self.link_resumo or '-'}",
        ]
        if self.link_pasta:
            linhas.append(f"Pasta: {self.link_pasta}")
        return "\n".join(linhas)


def normalizar_numero(numero: str) -> str:
    """Somente digitos, como a API da Meta espera (com DDI)."""
    return re.sub(r"\D", "", numero)


class NotificadorWhatsapp:
    def __init__(self, config: ConfigWhatsapp, ambiente: Ambiente) -> None:
        self._config = config
        self._ambiente = ambiente

    # -- API publica --------------------------------------------------------
    def avisar_aula(self, aviso: AvisoAula) -> list[str]:
        return self._enviar_para_todos(
            self._config.destinatarios, aviso.texto(), aviso.parametros_template()
        )

    def avisar_erro(self, destinatarios: list[str], titulo: str, mensagem: str) -> list[str]:
        texto = f"Falha na automacao de aulas.\n\nReuniao: {titulo}\n\n{mensagem}"[:900]
        # Erro nunca usa template - vai como texto livre e pode nao entregar
        # fora da janela de 24h; por isso tambem fica registrado no log.
        _LOG.error("AVISO DE ERRO: %s", texto.replace("\n", " | "))
        return self._enviar_para_todos(destinatarios, texto, None, forcar_texto=True)

    # -- interno ------------------------------------------------------------
    def _enviar_para_todos(
        self,
        destinatarios: list[str],
        texto: str,
        parametros: list[str] | None,
        *,
        forcar_texto: bool = False,
    ) -> list[str]:
        if not self._config.ativo:
            _LOG.info("Notificacao por WhatsApp desativada; mensagem nao enviada.")
            return []
        enviados: list[str] = []
        for destino in destinatarios:
            if not destino.strip():
                continue
            try:
                if self._config.provedor == "twilio":
                    ident = self._enviar_twilio(destino, texto)
                else:
                    ident = self._enviar_meta(destino, texto, parametros, forcar_texto)
                enviados.append(ident)
                _LOG.info("WhatsApp enviado para %s (id %s)", destino, ident)
            except Exception as erro:  # nao derruba o pipeline por causa do aviso
                _LOG.exception("Falha ao avisar %s no WhatsApp: %s", destino, erro)
        return enviados

    def _enviar_meta(
        self,
        destino: str,
        texto: str,
        parametros: list[str] | None,
        forcar_texto: bool,
    ) -> str:
        amb = self._ambiente
        amb.exigir("meta_whatsapp_token", "meta_whatsapp_phone_number_id")
        url = (
            f"https://graph.facebook.com/{VERSAO_GRAPH}/"
            f"{amb.meta_whatsapp_phone_number_id}/messages"
        )
        usar_template = (
            not forcar_texto and bool(self._config.nome_template) and parametros is not None
        )
        if usar_template:
            corpo = {
                "messaging_product": "whatsapp",
                "to": normalizar_numero(destino),
                "type": "template",
                "template": {
                    "name": self._config.nome_template,
                    "language": {"code": self._config.idioma_template},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": p} for p in parametros or []
                            ],
                        }
                    ],
                },
            }
        elif forcar_texto or self._config.usar_texto_livre_se_sem_template:
            corpo = {
                "messaging_product": "whatsapp",
                "to": normalizar_numero(destino),
                "type": "text",
                "text": {"preview_url": True, "body": texto[:4000]},
            }
        else:
            raise ErroNotificacao(
                "Nenhum template configurado e o texto livre esta desativado "
                "(notificacao.whatsapp.usar_texto_livre_se_sem_template)."
            )

        resposta = requests.post(
            url,
            json=corpo,
            headers={"Authorization": f"Bearer {amb.meta_whatsapp_token}"},
            timeout=30,
        )
        if resposta.status_code >= 300:
            raise ErroNotificacao(
                f"WhatsApp Cloud API respondeu {resposta.status_code}: {resposta.text[:400]}"
            )
        dados = resposta.json()
        return (dados.get("messages") or [{}])[0].get("id", "")

    def _enviar_twilio(self, destino: str, texto: str) -> str:
        amb = self._ambiente
        amb.exigir("twilio_account_sid", "twilio_auth_token", "twilio_whatsapp_from")
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{amb.twilio_account_sid}/Messages.json"
        )
        destino_formatado = destino if destino.startswith("whatsapp:") else f"whatsapp:{destino}"
        resposta = requests.post(
            url,
            data={
                "From": amb.twilio_whatsapp_from,
                "To": destino_formatado,
                "Body": texto[:1500],
            },
            auth=(amb.twilio_account_sid, amb.twilio_auth_token),
            timeout=30,
        )
        if resposta.status_code >= 300:
            raise ErroNotificacao(
                f"Twilio respondeu {resposta.status_code}: {resposta.text[:400]}"
            )
        return resposta.json().get("sid", "")
