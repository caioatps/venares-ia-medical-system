"""Leitura e validacao da configuracao (YAML) e do ambiente (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

RAIZ = Path(__file__).resolve().parents[2]


def _caminho(valor: str | os.PathLike[str]) -> Path:
    p = Path(valor)
    return p if p.is_absolute() else RAIZ / p


class ErroConfig(RuntimeError):
    """Configuracao ausente ou invalida."""


# ---------------------------------------------------------------------------
# Ambiente (segredos)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Ambiente:
    zoom_account_id: str
    zoom_client_id: str
    zoom_client_secret: str
    zoom_secret_token: str
    anthropic_api_key: str
    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    google_service_account_file: str
    google_delegar_para: str
    meta_whatsapp_token: str
    meta_whatsapp_phone_number_id: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str
    admin_api_key: str
    dir_trabalho: Path
    banco: Path

    @classmethod
    def do_ambiente(cls) -> "Ambiente":
        g = os.getenv
        return cls(
            zoom_account_id=g("ZOOM_ACCOUNT_ID", ""),
            zoom_client_id=g("ZOOM_CLIENT_ID", ""),
            zoom_client_secret=g("ZOOM_CLIENT_SECRET", ""),
            zoom_secret_token=g("ZOOM_SECRET_TOKEN", ""),
            anthropic_api_key=g("ANTHROPIC_API_KEY", ""),
            google_client_id=g("GOOGLE_CLIENT_ID", ""),
            google_client_secret=g("GOOGLE_CLIENT_SECRET", ""),
            google_refresh_token=g("GOOGLE_REFRESH_TOKEN", ""),
            google_service_account_file=g("GOOGLE_SERVICE_ACCOUNT_FILE", ""),
            google_delegar_para=g("GOOGLE_DELEGAR_PARA", ""),
            meta_whatsapp_token=g("META_WHATSAPP_TOKEN", ""),
            meta_whatsapp_phone_number_id=g("META_WHATSAPP_PHONE_NUMBER_ID", ""),
            twilio_account_sid=g("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=g("TWILIO_AUTH_TOKEN", ""),
            twilio_whatsapp_from=g("TWILIO_WHATSAPP_FROM", ""),
            admin_api_key=g("ADMIN_API_KEY", ""),
            dir_trabalho=_caminho(g("VENARES_DIR_TRABALHO", "trabalho")),
            banco=_caminho(g("VENARES_BANCO", "dados/venares.db")),
        )

    def exigir(self, *campos: str) -> None:
        faltando = [c for c in campos if not getattr(self, c, "")]
        if faltando:
            nomes = ", ".join(c.upper() for c in faltando)
            raise ErroConfig(f"Variaveis de ambiente ausentes: {nomes}")


# ---------------------------------------------------------------------------
# Config (YAML)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Mentoria:
    id: str
    nome: str
    palavras_chave: list[str]
    pasta_drive_id: str
    drive_compartilhado_id: str | None = None


@dataclass(frozen=True)
class Nomeacao:
    padrao: str = "Aula {numero:02d} - {data} - {mentoria}"
    formato_data: str = "%d-%m-%Y"
    regex_numero: str = r"(?i)aula\s*n?[.º]?\s*0*(\d{1,3})"
    numero_inicial: int = 1
    criar_subpasta_por_aula: bool = False
    sufixo_video: str = ""
    sufixo_resumo: str = " - Resumo"


@dataclass(frozen=True)
class ConfigZoom:
    espera_maxima_transcricao_min: int = 90
    intervalo_nova_tentativa_min: int = 5
    ignorar_titulos: list[str] = field(default_factory=list)
    duracao_minima_min: int = 15
    apagar_da_nuvem_apos_upload: bool = False


@dataclass(frozen=True)
class ConfigResumo:
    modelo: str = "claude-opus-5"
    effort: str = "high"
    max_tokens: int = 16000
    timeout_s: int = 1800
    limite_caracteres_chamada_unica: int = 500_000
    caracteres_por_bloco: int = 120_000
    instrucoes_extras: str = ""


@dataclass(frozen=True)
class ConfigPdf:
    template: str = "templates/resumo_aula.html"
    logo: str | None = None
    cor_primaria: str = "#0F4C5C"
    cor_secundaria: str = "#9A6A3A"
    rodape: str = ""

    @property
    def caminho_template(self) -> Path:
        return _caminho(self.template)

    @property
    def caminho_logo(self) -> Path | None:
        return _caminho(self.logo) if self.logo else None


@dataclass(frozen=True)
class ConfigWhatsapp:
    ativo: bool = True
    provedor: str = "meta"
    destinatarios: list[str] = field(default_factory=list)
    nome_template: str = ""
    idioma_template: str = "pt_BR"
    usar_texto_livre_se_sem_template: bool = False


@dataclass(frozen=True)
class ConfigNotificacao:
    whatsapp: ConfigWhatsapp = field(default_factory=ConfigWhatsapp)
    avisar_erros_para: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    fuso_horario: str
    idioma: str
    mentorias: list[Mentoria]
    mentoria_padrao: str | None
    nomeacao: Nomeacao
    zoom: ConfigZoom
    resumo: ConfigResumo
    pdf: ConfigPdf
    notificacao: ConfigNotificacao

    def mentoria_por_id(self, ident: str) -> Mentoria | None:
        return next((m for m in self.mentorias if m.id == ident), None)


def _sub(dados: dict[str, Any], chave: str) -> dict[str, Any]:
    valor = dados.get(chave) or {}
    if not isinstance(valor, dict):
        raise ErroConfig(f"A secao '{chave}' da configuracao deve ser um mapeamento.")
    return valor


def _construir(classe, dados: dict[str, Any], secao: str):
    """Instancia uma dataclass de configuracao apontando o erro de digitacao."""
    validos = {f.name for f in fields(classe)}
    desconhecidos = sorted(set(dados) - validos)
    if desconhecidos:
        raise ErroConfig(
            f"Opcao desconhecida em '{secao}': {', '.join(desconhecidos)}. "
            f"Validas: {', '.join(sorted(validos))}."
        )
    try:
        return classe(**dados)
    except TypeError as erro:
        raise ErroConfig(f"Secao '{secao}' invalida: {erro}") from erro


def carregar_config(caminho: str | os.PathLike[str] | None = None) -> Config:
    origem = _caminho(caminho or os.getenv("VENARES_CONFIG", "config/config.yaml"))
    if not origem.exists():
        raise ErroConfig(
            f"Arquivo de configuracao nao encontrado: {origem}. "
            "Copie config/config.example.yaml para config/config.yaml."
        )
    dados = yaml.safe_load(origem.read_text(encoding="utf-8")) or {}

    mentorias = []
    for bruto in dados.get("mentorias") or []:
        for obrigatorio in ("id", "nome", "pasta_drive_id"):
            if not bruto.get(obrigatorio):
                raise ErroConfig(
                    f"Mentoria {bruto.get('id') or '(sem id)'}: campo '{obrigatorio}' obrigatorio."
                )
        mentorias.append(
            Mentoria(
                id=str(bruto["id"]).strip().lower(),
                nome=str(bruto["nome"]).strip(),
                palavras_chave=[str(p) for p in (bruto.get("palavras_chave") or [])],
                pasta_drive_id=str(bruto["pasta_drive_id"]).strip(),
                drive_compartilhado_id=bruto.get("drive_compartilhado_id") or None,
            )
        )
    if not mentorias:
        raise ErroConfig("Nenhuma mentoria configurada em 'mentorias'.")

    padrao = dados.get("mentoria_padrao")
    padrao = str(padrao).strip().lower() if padrao else None
    if padrao and not any(m.id == padrao for m in mentorias):
        raise ErroConfig(f"mentoria_padrao '{padrao}' nao corresponde a nenhuma mentoria.")

    notif = _sub(dados, "notificacao")
    return Config(
        fuso_horario=str(dados.get("fuso_horario", "America/Sao_Paulo")),
        idioma=str(dados.get("idioma", "pt-BR")),
        mentorias=mentorias,
        mentoria_padrao=padrao,
        nomeacao=_construir(Nomeacao, _sub(dados, "nomeacao"), "nomeacao"),
        zoom=_construir(ConfigZoom, _sub(dados, "zoom"), "zoom"),
        resumo=_construir(ConfigResumo, _sub(dados, "resumo"), "resumo"),
        pdf=_construir(ConfigPdf, _sub(dados, "pdf"), "pdf"),
        notificacao=ConfigNotificacao(
            whatsapp=_construir(ConfigWhatsapp, notif.get("whatsapp") or {}, "notificacao.whatsapp"),
            avisar_erros_para=[str(n) for n in (notif.get("avisar_erros_para") or [])],
        ),
    )
