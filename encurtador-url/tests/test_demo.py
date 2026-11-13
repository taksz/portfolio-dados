from datetime import datetime, timezone

from app import demo, models


def conn_temporaria(tmp_path):
    conn = models.conectar(str(tmp_path / "demo.db"))
    models.inicializar_schema(conn)
    return conn


def test_popular_cria_links_e_cliques(tmp_path):
    conn = conn_temporaria(tmp_path)
    total = demo.popular(conn, agora=datetime(2026, 1, 15, tzinfo=timezone.utc))
    assert total > 50
    urls = models.listar_urls(conn)
    assert {u["codigo"] for u in urls} == {"demo-docs", "demo-portfolio", "demo-dados", "demo-expirado", "demo-desativado"}
    assert sum(u["total_cliques"] for u in urls) == total


def test_estatisticas_dos_links_demo_tem_varios_dias(tmp_path):
    conn = conn_temporaria(tmp_path)
    demo.popular(conn, agora=datetime(2026, 1, 15, tzinfo=timezone.utc))
    stats = models.obter_estatisticas(conn, "demo-docs")
    assert len(stats["cliques_por_dia"]) >= 10
    assert stats["visitantes_unicos_aprox"] > 1
    assert len(stats["navegadores"]) > 1


def test_popular_e_deterministico(tmp_path):
    agora = datetime(2026, 1, 15, tzinfo=timezone.utc)
    a = demo.popular(conn_temporaria(tmp_path), agora=agora)
    b = demo.popular(models.conectar(str(tmp_path / "demo.db")), agora=agora)
    assert a == b


def test_limpar_remove_so_links_demo(tmp_path):
    conn = conn_temporaria(tmp_path)
    models.criar_url_curta(conn, "https://exemplo.com")
    demo.popular(conn)
    assert demo.limpar(conn) == 5
    assert [u["url_original"] for u in models.listar_urls(conn)] == ["https://exemplo.com"]
