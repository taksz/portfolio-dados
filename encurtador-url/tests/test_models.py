import sqlite3

import pytest

from app import models


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    models.inicializar_schema(connection)
    yield connection
    connection.close()


def test_criar_url_curta_retorna_codigo(conn):
    codigo = models.criar_url_curta(conn, "https://exemplo.com")
    assert len(codigo) == 6


def test_obter_url_existente(conn):
    codigo = models.criar_url_curta(conn, "https://exemplo.com/pagina")
    url = models.obter_url(conn, codigo)
    assert url["url_original"] == "https://exemplo.com/pagina"


def test_obter_url_inexistente(conn):
    assert models.obter_url(conn, "naoexiste") is None


def test_hash_ip_e_deterministico_e_nao_reversivel(conn):
    h1 = models.hash_ip("192.168.0.1")
    h2 = models.hash_ip("192.168.0.1")
    assert h1 == h2
    assert h1 != "192.168.0.1"
    assert len(h1) == 64  # sha256 em hexadecimal


def test_registrar_clique_e_contabilizado_nas_estatisticas(conn):
    codigo = models.criar_url_curta(conn, "https://exemplo.com")
    url = models.obter_url(conn, codigo)

    models.registrar_clique(conn, url["id"], referrer="https://google.com", user_agent="Chrome/119.0.0.0", ip="1.1.1.1")
    models.registrar_clique(conn, url["id"], referrer=None, user_agent="Firefox/119.0", ip="2.2.2.2")

    stats = models.obter_estatisticas(conn, codigo)
    assert stats["total_cliques"] == 2
    assert stats["visitantes_unicos_aprox"] == 2


def test_estatisticas_de_codigo_inexistente(conn):
    assert models.obter_estatisticas(conn, "naoexiste") is None


def test_visitantes_unicos_nao_duplica_mesmo_ip(conn):
    codigo = models.criar_url_curta(conn, "https://exemplo.com")
    url = models.obter_url(conn, codigo)

    models.registrar_clique(conn, url["id"], referrer=None, user_agent="Chrome/119.0.0.0", ip="1.1.1.1")
    models.registrar_clique(conn, url["id"], referrer=None, user_agent="Chrome/119.0.0.0", ip="1.1.1.1")

    stats = models.obter_estatisticas(conn, codigo)
    assert stats["total_cliques"] == 2       # 2 cliques
    assert stats["visitantes_unicos_aprox"] == 1  # mas do mesmo IP


def test_listar_urls_inclui_total_de_cliques(conn):
    codigo = models.criar_url_curta(conn, "https://exemplo.com")
    url = models.obter_url(conn, codigo)
    models.registrar_clique(conn, url["id"], referrer=None, user_agent="Chrome", ip="1.1.1.1")

    urls = models.listar_urls(conn)
    assert len(urls) == 1
    assert urls[0]["total_cliques"] == 1
