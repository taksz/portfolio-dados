from datetime import datetime

import banco
from scraper import Produto


def produto(preco=10.0, id="livro_1", disponivel=True):
    return Produto(id, "Livro " + id, preco, disponivel, f"https://x/{id}/index.html")


def test_snapshot_cria_historico(tmp_path):
    conn = banco.conectar(tmp_path / "t.db")
    banco.salvar_snapshot(conn, [produto(10.0)], datetime(2026, 1, 1, 10))
    banco.salvar_snapshot(conn, [produto(8.5)], datetime(2026, 1, 2, 10))
    h = banco.historico(conn, "livro_1")
    assert [r["preco"] for r in h] == [10.0, 8.5]
    assert h[0]["coletado_em"] == "2026-01-01T10:00:00"


def test_produto_nao_duplica_e_atualiza_nome(tmp_path):
    conn = banco.conectar(tmp_path / "t.db")
    banco.salvar_snapshot(conn, [produto()])
    banco.salvar_snapshot(conn, [Produto("livro_1", "Novo Nome", 9.0, True, "https://x/")])
    assert conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == 1
    assert conn.execute("SELECT nome FROM produtos").fetchone()[0] == "Novo Nome"


def test_preco_anterior(tmp_path):
    conn = banco.conectar(tmp_path / "t.db")
    assert banco.preco_anterior(conn, "livro_1") is None
    banco.salvar_snapshot(conn, [produto(10.0)], datetime(2026, 1, 1))
    banco.salvar_snapshot(conn, [produto(7.0)], datetime(2026, 1, 2))
    assert banco.preco_anterior(conn, "livro_1") == 7.0


def test_buscar_produto_por_id_e_por_nome(tmp_path):
    conn = banco.conectar(tmp_path / "t.db")
    banco.salvar_snapshot(conn, [produto(id="abc_1")])
    assert banco.buscar_produto(conn, "abc_1")["id"] == "abc_1"
    assert banco.buscar_produto(conn, "LIVRO abc")["id"] == "abc_1"
    assert banco.buscar_produto(conn, "inexistente") is None


def test_listar_produtos_traz_ultimo_preco(tmp_path):
    conn = banco.conectar(tmp_path / "t.db")
    banco.salvar_snapshot(conn, [produto(10.0)], datetime(2026, 1, 1))
    banco.salvar_snapshot(conn, [produto(6.0)], datetime(2026, 1, 2))
    linhas = banco.listar_produtos(conn)
    assert len(linhas) == 1 and linhas[0]["preco"] == 6.0
