"""Renderizacao do resumo em PDF (Jinja2 -> HTML -> WeasyPrint)."""

from __future__ import annotations

import base64
import mimetypes
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import ConfigPdf
from ..logging_setup import log
from ..nomeacao import NomesArquivos
from ..resumo.modelos import ResumoAula
from ..transcricao.glossario import Glossario

_LOG = log(__name__)

_MESES = [
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def data_por_extenso(data: datetime) -> str:
    return f"{data.day} de {_MESES[data.month - 1]} de {data.year}"


def duracao_por_extenso(minutos: int) -> str:
    if minutos <= 0:
        return "-"
    horas, resto = divmod(int(minutos), 60)
    if horas and resto:
        return f"{horas}h{resto:02d}min"
    if horas:
        return f"{horas}h"
    return f"{resto}min"


def _imagem_embutida(caminho: Path | None) -> str | None:
    """Converte o logotipo em data URI - o WeasyPrint nao busca na rede."""
    if not caminho or not caminho.exists():
        return None
    tipo = mimetypes.guess_type(caminho.name)[0] or "image/png"
    dados = base64.b64encode(caminho.read_bytes()).decode("ascii")
    return f"data:{tipo};base64,{dados}"


def montar_glossario_final(
    resumo: ResumoAula, glossario: Glossario
) -> list[tuple[str, str]]:
    """Une o glossario que o modelo extraiu com as definicoes oficiais.

    A definicao do arquivo de configuracao sempre vence a do modelo.
    """
    saida: dict[str, str] = {}
    for termo in resumo.termos_glossario:
        if termo.termo.strip():
            saida[termo.termo.strip()] = termo.definicao.strip()
    for nome, definicao in glossario.definicoes(list(saida.keys())):
        saida[nome] = definicao
    # Siglas oficiais citadas no texto do resumo entram mesmo se o modelo
    # nao as tiver listado.
    corpo = " ".join(
        [resumo.resumo_executivo, *resumo.pontos_chave, *resumo.condutas_praticas]
    )
    for sigla, expansao in glossario.abreviacoes.items():
        citada = re.search(rf"\b{re.escape(sigla)}\b", corpo)
        if citada and sigla not in saida:
            saida[sigla] = expansao
    return sorted(saida.items(), key=lambda item: item[0].lower())


def renderizar_html(
    *,
    resumo: ResumoAula,
    config_pdf: ConfigPdf,
    glossario: Glossario,
    nomes: NomesArquivos,
    mentoria: str,
    titulo_zoom: str,
    data_aula: datetime,
    duracao_min: int,
    palavras: int,
) -> str:
    template_path = config_pdf.caminho_template
    ambiente = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = ambiente.get_template(template_path.name)
    return template.render(
        resumo=resumo,
        nomes=nomes,
        numero=nomes.numero,
        mentoria=mentoria,
        titulo_zoom=titulo_zoom,
        data_extenso=data_por_extenso(data_aula),
        duracao_texto=duracao_por_extenso(duracao_min),
        professores=glossario.professores(),
        glossario_final=montar_glossario_final(resumo, glossario),
        logo_uri=_imagem_embutida(config_pdf.caminho_logo),
        cor_primaria=config_pdf.cor_primaria,
        cor_secundaria=config_pdf.cor_secundaria,
        rodape=config_pdf.rodape,
        gerado_em=datetime.now().strftime("%d/%m/%Y as %H:%M"),
        palavras=palavras,
    )


def gerar_pdf(html: str, destino: Path, *, base_url: str | None = None) -> Path:
    from weasyprint import HTML  # import tardio: carrega bibliotecas nativas

    destino.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=base_url or str(Path.cwd())).write_pdf(str(destino))
    _LOG.info("PDF gerado: %s (%.1f KB)", destino.name, destino.stat().st_size / 1024)
    return destino
