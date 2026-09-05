"""Linha de comando: operar e depurar o agente sem depender do webhook."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from . import db
from .config import Ambiente, ErroConfig, carregar_config
from .db import Banco
from .logging_setup import configurar_logging, log
from .nomeacao import (
    ErroClassificacao,
    classificar_mentoria,
    montar_nomes,
    proximo_numero,
)
from .pipeline import Pipeline

_LOG = log(__name__)


def _pipeline() -> Pipeline:
    config = carregar_config()
    ambiente = Ambiente.do_ambiente()
    return Pipeline(config, ambiente, banco=Banco(ambiente.banco))


# ---------------------------------------------------------------------------
# comandos
# ---------------------------------------------------------------------------
def cmd_servir(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "venares_aulas.api:obter_app",
        factory=True,
        host=args.host,
        port=args.porta,
        log_config=None,
    )
    return 0


def cmd_processar(args: argparse.Namespace) -> int:
    pipeline = _pipeline()
    resultado = pipeline.processar_com_retentativa(args.uuid, forcar=args.forcar)
    if resultado is None:
        print("Nada concluido nesta execucao (veja o log: ignorada, reagendada ou erro).")
        return 1
    print(
        f"OK: {resultado.mentoria} - aula {resultado.numero:02d} "
        f"({resultado.data_aula.strftime('%d/%m/%Y')})\n"
        f"  video : {resultado.link_video}\n"
        f"  resumo: {resultado.link_resumo}"
    )
    return 0


def cmd_pendentes(args: argparse.Namespace) -> int:
    pipeline = _pipeline()
    total = pipeline.processar_pendentes(limite=args.limite)
    print(f"{total} trabalho(s) pendente(s) processado(s).")
    return 0


def cmd_varrer(args: argparse.Namespace) -> int:
    """Rede de seguranca: procura gravacoes recentes que nunca foram processadas."""
    pipeline = _pipeline()
    de = (datetime.now() - timedelta(days=args.dias)).strftime("%Y-%m-%d")
    novos = 0
    for gravacao in pipeline.zoom.gravacoes_recentes(args.usuario, de=de):
        existente = pipeline.banco.obter(gravacao.uuid)
        if existente and existente.status in (db.CONCLUIDO, db.IGNORADO):
            continue
        print(f"-> {gravacao.inicio[:10]}  {gravacao.titulo}")
        if not args.simular:
            pipeline.processar_com_retentativa(gravacao.uuid)
        novos += 1
    print(f"{novos} gravacao(oes) pendente(s) encontradas nos ultimos {args.dias} dias.")
    return 0


def cmd_listar(args: argparse.Namespace) -> int:
    banco = Banco(Ambiente.do_ambiente().banco)
    itens = banco.listar(status=args.status, limite=args.limite)
    if not itens:
        print("Nenhum trabalho registrado.")
        return 0
    largura = max(len(t.titulo or "") for t in itens)
    for t in itens:
        numero = f"aula {t.numero_aula:02d}" if t.numero_aula else "-"
        print(
            f"{t.status:<11} {(t.titulo or ''):<{largura}}  {numero:<8} "
            f"{t.mentoria or '-':<10} {t.uuid}"
        )
        if t.erro and args.status != db.CONCLUIDO:
            print(f"            erro: {t.erro[:160]}")
    return 0


def cmd_verificar(args: argparse.Namespace) -> int:
    """Confere a configuracao antes de colocar em producao."""
    falhas = 0
    try:
        config = carregar_config()
    except ErroConfig as erro:
        print(f"[X] configuracao: {erro}")
        return 1
    ambiente = Ambiente.do_ambiente()
    print(f"[ok] configuracao lida ({len(config.mentorias)} mentoria(s))")

    from .transcricao.glossario import Glossario

    glossario = Glossario.carregar()
    print(
        f"[ok] glossario: {len(glossario.termos)} termo(s), "
        f"{len(glossario.abreviacoes)} sigla(s), "
        f"{len(glossario.remover_frases)} filtro(s) de ruido"
    )

    template = config.pdf.caminho_template
    if template.exists():
        print(f"[ok] template do PDF: {template}")
    else:
        print(f"[X] template do PDF nao encontrado: {template}")
        falhas += 1

    # Zoom
    try:
        from .zoom.auth import TokenZoom

        TokenZoom(ambiente).obter()
        print("[ok] Zoom: token obtido")
    except Exception as erro:  # noqa: BLE001
        print(f"[X] Zoom: {erro}")
        falhas += 1

    # Drive: cada pasta precisa existir e ser acessivel
    try:
        from .drive.cliente import ClienteDrive

        drive = ClienteDrive(ambiente)
        for mentoria in config.mentorias:
            pasta = drive.verificar_pasta(
                mentoria.pasta_drive_id,
                drive_compartilhado_id=mentoria.drive_compartilhado_id,
            )
            nomes = drive.nomes_na_pasta(
                mentoria.pasta_drive_id,
                drive_compartilhado_id=mentoria.drive_compartilhado_id,
                recursivo=config.nomeacao.criar_subpasta_por_aula,
            )
            proximo = proximo_numero(nomes, config.nomeacao)
            print(
                f"[ok] Drive/{mentoria.id}: pasta '{pasta.nome}' "
                f"({len(nomes)} item(ns)) -> proxima aula sera a {proximo:02d}"
            )
    except Exception as erro:  # noqa: BLE001
        print(f"[X] Google Drive: {erro}")
        falhas += 1

    # Anthropic
    if ambiente.anthropic_api_key:
        print("[ok] ANTHROPIC_API_KEY presente")
    else:
        print("[!] ANTHROPIC_API_KEY vazia - o SDK vai tentar outras credenciais")

    # WhatsApp
    zap = config.notificacao.whatsapp
    if not zap.ativo:
        print("[!] notificacao por WhatsApp desativada")
    elif zap.provedor == "meta" and not ambiente.meta_whatsapp_token:
        print("[X] WhatsApp (meta): META_WHATSAPP_TOKEN ausente")
        falhas += 1
    elif zap.provedor == "twilio" and not ambiente.twilio_account_sid:
        print("[X] WhatsApp (twilio): TWILIO_ACCOUNT_SID ausente")
        falhas += 1
    else:
        print(f"[ok] WhatsApp via {zap.provedor} para {len(zap.destinatarios)} destinatario(s)")

    print()
    print("Tudo certo." if falhas == 0 else f"{falhas} problema(s) a resolver.")
    return 1 if falhas else 0


def cmd_classificar(args: argparse.Namespace) -> int:
    """Testa a regra Start x Surgical em um titulo de reuniao."""
    config = carregar_config()
    try:
        mentoria = classificar_mentoria(args.titulo, config)
    except ErroClassificacao as erro:
        print(f"[X] {erro}")
        return 1
    nomes = montar_nomes(
        numero=args.numero,
        data_aula=datetime.now(),
        mentoria=mentoria,
        titulo_zoom=args.titulo,
        nomeacao=config.nomeacao,
    )
    print(f"mentoria : {mentoria.nome} ({mentoria.id})")
    print(f"pasta    : {mentoria.pasta_drive_id}")
    print(f"video    : {nomes.video}")
    print(f"resumo   : {nomes.resumo}")
    return 0


def cmd_resumir_arquivo(args: argparse.Namespace) -> int:
    """Gera o PDF a partir de um .vtt local - util para ajustar o modelo."""
    from .pdf.render import gerar_pdf, renderizar_html
    from .resumo.gerador import GeradorResumo
    from .transcricao.glossario import Glossario, aplicar_glossario
    from .transcricao.vtt import carregar_transcricao

    config = carregar_config()
    ambiente = Ambiente.do_ambiente()
    glossario = Glossario.carregar()

    caminho = Path(args.arquivo)
    transcricao = aplicar_glossario(
        carregar_transcricao(caminho.read_text(encoding="utf-8", errors="replace")),
        glossario,
    )
    if not transcricao.turnos:
        print("[X] Nao consegui ler nenhuma fala do arquivo.")
        return 1

    mentoria = classificar_mentoria(args.titulo, config)
    data_aula = datetime.strptime(args.data, "%d/%m/%Y") if args.data else datetime.now()
    duracao = int(transcricao.duracao_s // 60) or 60

    resumo = GeradorResumo(
        config.resumo, api_key=ambiente.anthropic_api_key or None
    ).gerar(
        transcricao,
        titulo_zoom=args.titulo,
        mentoria=mentoria.nome,
        data_aula=data_aula.strftime("%d/%m/%Y"),
        duracao_min=duracao,
        glossario=glossario,
    )
    nomes = montar_nomes(
        numero=args.numero,
        data_aula=data_aula,
        mentoria=mentoria,
        titulo_zoom=args.titulo,
        nomeacao=config.nomeacao,
    )
    html = renderizar_html(
        resumo=resumo,
        config_pdf=config.pdf,
        glossario=glossario,
        nomes=nomes,
        mentoria=mentoria.nome,
        titulo_zoom=args.titulo,
        data_aula=data_aula,
        duracao_min=duracao,
        palavras=transcricao.total_palavras,
    )
    destino = Path(args.saida or nomes.resumo)
    gerar_pdf(html, destino)
    print(f"PDF gerado em {destino}")
    return 0


# ---------------------------------------------------------------------------
def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="venares-aulas",
        description="Automacao Zoom -> resumo em PDF -> Google Drive das mentorias.",
    )
    parser.add_argument("--log", default=None, help="Nivel de log (DEBUG, INFO, WARNING).")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("servir", help="Sobe o servidor de webhook.")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--porta", type=int, default=8080)
    p.set_defaults(func=cmd_servir)

    p = sub.add_parser("processar", help="Processa uma gravacao pelo UUID do Zoom.")
    p.add_argument("uuid")
    p.add_argument("--forcar", action="store_true", help="Reprocessa mesmo se ja concluida.")
    p.set_defaults(func=cmd_processar)

    p = sub.add_parser("pendentes", help="Roda os trabalhos aguardando nova tentativa.")
    p.add_argument("--limite", type=int, default=10)
    p.set_defaults(func=cmd_pendentes)

    p = sub.add_parser("varrer", help="Procura gravacoes recentes ainda nao processadas.")
    p.add_argument("--dias", type=int, default=7)
    p.add_argument("--usuario", default="me", help="E-mail ou ID do host no Zoom.")
    p.add_argument("--simular", action="store_true", help="So lista, nao processa.")
    p.set_defaults(func=cmd_varrer)

    p = sub.add_parser("listar", help="Mostra o historico de trabalhos.")
    p.add_argument("--status", default=None, choices=[db.PENDENTE, db.CONCLUIDO, db.ERRO, db.IGNORADO])
    p.add_argument("--limite", type=int, default=30)
    p.set_defaults(func=cmd_listar)

    p = sub.add_parser("verificar", help="Confere credenciais, pastas e numeracao.")
    p.set_defaults(func=cmd_verificar)

    p = sub.add_parser("classificar", help="Testa a deteccao de mentoria em um titulo.")
    p.add_argument("titulo")
    p.add_argument("--numero", type=int, default=1)
    p.set_defaults(func=cmd_classificar)

    p = sub.add_parser("resumir-arquivo", help="Gera o PDF a partir de um .vtt local.")
    p.add_argument("arquivo")
    p.add_argument("--titulo", required=True, help="Titulo da reuniao (define a mentoria).")
    p.add_argument("--data", default=None, help="Data da aula em dd/mm/aaaa.")
    p.add_argument("--numero", type=int, default=1)
    p.add_argument("--saida", default=None)
    p.set_defaults(func=cmd_resumir_arquivo)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    configurar_logging(args.log)
    try:
        return args.func(args)
    except ErroConfig as erro:
        print(f"Erro de configuracao: {erro}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
