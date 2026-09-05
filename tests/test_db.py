import time

from venares_aulas import db
from venares_aulas.db import Banco


def test_registrar_e_idempotente(tmp_path):
    banco = Banco(tmp_path / "t.db")
    banco.registrar("uuid-1", titulo="Aula A", meeting_id="1")
    banco.registrar("uuid-1", titulo="Aula A", meeting_id="1")
    assert len(banco.listar()) == 1


def test_campos_novos_completam_o_registro(tmp_path):
    banco = Banco(tmp_path / "t.db")
    banco.registrar("uuid-1")
    banco.registrar("uuid-1", titulo="Aula A", inicio="2026-03-17T13:00:00Z")
    trabalho = banco.obter("uuid-1")
    assert trabalho.titulo == "Aula A"
    assert trabalho.inicio == "2026-03-17T13:00:00Z"


def test_concluido_nao_reprocessa(tmp_path):
    banco = Banco(tmp_path / "t.db")
    banco.registrar("uuid-1")
    assert not banco.ja_concluido("uuid-1")
    banco.atualizar("uuid-1", status=db.CONCLUIDO)
    assert banco.ja_concluido("uuid-1")


def test_reagendamento_mantem_pendente_no_futuro(tmp_path):
    banco = Banco(tmp_path / "t.db")
    banco.registrar("uuid-1")
    banco.marcar_erro("uuid-1", "transcricao ausente", reagendar_em_s=300)
    assert banco.obter("uuid-1").status == db.PENDENTE
    assert banco.pendentes_vencidos() == []

    banco.atualizar("uuid-1", proxima_tentativa=time.time() - 1)
    assert [t.uuid for t in banco.pendentes_vencidos()] == ["uuid-1"]


def test_erro_definitivo_sai_da_fila(tmp_path):
    banco = Banco(tmp_path / "t.db")
    banco.registrar("uuid-1")
    banco.marcar_erro("uuid-1", "sem jeito")
    assert banco.obter("uuid-1").status == db.ERRO
    assert banco.pendentes_vencidos() == []


def test_numeros_ja_usados_por_mentoria(tmp_path):
    banco = Banco(tmp_path / "t.db")
    for i, (uuid, mentoria, numero) in enumerate(
        [("a", "start", 1), ("b", "start", 2), ("c", "surgical", 1)]
    ):
        banco.registrar(uuid)
        banco.atualizar(uuid, mentoria=mentoria, numero_aula=numero)
    assert banco.numeros_ja_usados("start") == {1, 2}
    assert banco.numeros_ja_usados("surgical") == {1}


def test_extra_guarda_json(tmp_path):
    banco = Banco(tmp_path / "t.db")
    banco.registrar("uuid-1")
    banco.atualizar("uuid-1", extra={"link_video": "https://x", "n": 3})
    assert banco.obter("uuid-1").extra == {"link_video": "https://x", "n": 3}
