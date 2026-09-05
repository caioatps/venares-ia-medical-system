"""Garante que os arquivos de exemplo carregam e que erros de digitacao aparecem."""

import time

import pytest

from venares_aulas import db
from venares_aulas.config import RAIZ, ErroConfig, carregar_config
from venares_aulas.db import Banco
from venares_aulas.transcricao.glossario import Glossario


def test_config_de_exemplo_carrega():
    config = carregar_config(RAIZ / "config" / "config.example.yaml")
    assert {m.id for m in config.mentorias} == {"start", "surgical"}
    assert config.fuso_horario == "America/Sao_Paulo"
    assert config.nomeacao.padrao.startswith("Aula {numero")
    assert config.notificacao.whatsapp.provedor == "meta"
    assert config.resumo.modelo == "claude-opus-5"


def test_glossario_de_exemplo_carrega():
    glossario = Glossario.carregar(RAIZ / "config" / "glossario.example.yaml")
    assert any(t.correto == "GnRH" for t in glossario.termos)
    assert glossario.abreviacoes["TRH"].startswith("Terapia")
    texto, _ = glossario.aplicar("dose em micro gramas de extradiol")
    assert texto == "dose em mcg de estradiol"


def test_padrao_do_exemplo_e_legivel_pelo_proprio_regex():
    """O nome que o sistema gera precisa casar com o regex que ele usa para ler."""
    from datetime import datetime

    from venares_aulas.nomeacao import montar_nomes, proximo_numero

    config = carregar_config(RAIZ / "config" / "config.example.yaml")
    nomes = montar_nomes(
        numero=3,
        data_aula=datetime(2026, 3, 17),
        mentoria=config.mentorias[0],
        titulo_zoom="x",
        nomeacao=config.nomeacao,
    )
    assert proximo_numero([nomes.video, nomes.resumo], config.nomeacao) == 4


def test_arquivo_inexistente_da_erro_util(tmp_path):
    with pytest.raises(ErroConfig, match="config.example.yaml"):
        carregar_config(tmp_path / "nao_existe.yaml")


def test_opcao_desconhecida_e_apontada(tmp_path):
    arquivo = tmp_path / "c.yaml"
    arquivo.write_text(
        "mentorias:\n"
        "  - id: start\n"
        "    nome: Start\n"
        "    pasta_drive_id: abc\n"
        "nomeacao:\n"
        "  padrao_do_nome: errado\n",
        encoding="utf-8",
    )
    with pytest.raises(ErroConfig, match="padrao_do_nome"):
        carregar_config(arquivo)


def test_mentoria_sem_pasta_e_recusada(tmp_path):
    arquivo = tmp_path / "c.yaml"
    arquivo.write_text("mentorias:\n  - id: start\n    nome: Start\n", encoding="utf-8")
    with pytest.raises(ErroConfig, match="pasta_drive_id"):
        carregar_config(arquivo)


def test_mentoria_padrao_inexistente_e_recusada(tmp_path):
    arquivo = tmp_path / "c.yaml"
    arquivo.write_text(
        "mentorias:\n  - id: start\n    nome: Start\n    pasta_drive_id: abc\n"
        "mentoria_padrao: outra\n",
        encoding="utf-8",
    )
    with pytest.raises(ErroConfig, match="mentoria_padrao"):
        carregar_config(arquivo)


# --- reserva de numeros ----------------------------------------------------
def test_numero_de_falha_antiga_e_liberado(tmp_path):
    banco = Banco(tmp_path / "t.db")
    banco.registrar("antigo")
    banco.atualizar("antigo", mentoria="start", numero_aula=4, status=db.ERRO)
    # Envelhece o registro para fora da janela de "em andamento".
    banco.atualizar("antigo", atualizado_em=time.time() - 7200)
    assert banco.numeros_ja_usados("start") == set()


def test_numero_concluido_fica_reservado_para_sempre(tmp_path):
    banco = Banco(tmp_path / "t.db")
    banco.registrar("ok")
    banco.atualizar("ok", mentoria="start", numero_aula=4, status=db.CONCLUIDO)
    banco.atualizar("ok", atualizado_em=time.time() - 7200)
    assert banco.numeros_ja_usados("start") == {4}


def test_numero_em_andamento_fica_reservado(tmp_path):
    banco = Banco(tmp_path / "t.db")
    banco.registrar("agora")
    banco.atualizar("agora", mentoria="start", numero_aula=5)
    assert banco.numeros_ja_usados("start") == {5}
