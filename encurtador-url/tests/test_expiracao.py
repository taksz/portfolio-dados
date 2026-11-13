"""Expiração e desativação de links: modelo (SQLite em memória) e API de ponta a ponta."""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import main, models


def agora() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    models.inicializar_schema(c)
    yield c
    c.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "teste.db")
    monkeypatch.delenv("ENCURTADOR_SENHA", raising=False)
    with TestClient(main.app) as c:
        yield c


def criar(client, **extra):
    return client.post("/api/shorten", json={"url": "https://exemplo.com", **extra}).json()


def cliques(client, codigo):
    return client.get(f"/api/analytics/{codigo}").json()["total_cliques"]


# ---------------------------------------------------------------- modelo
def test_link_novo_e_ativo_e_sem_expiracao(conn):
    codigo = models.criar_url_curta(conn, "https://exemplo.com")
    url = models.obter_url(conn, codigo)
    assert url["ativo"] == 1 and url["expira_em"] is None
    assert models.status_url(url) == "ativo"


def test_status_expirado_depende_da_data(conn):
    codigo = models.criar_url_curta(conn, "https://exemplo.com", agora() + timedelta(days=1))
    url = models.obter_url(conn, codigo)
    assert models.status_url(url) == "ativo"
    assert models.status_url(url, agora() + timedelta(days=2)) == "expirado"


def test_desativado_tem_prioridade_sobre_expirado(conn):
    codigo = models.criar_url_curta(conn, "https://exemplo.com", agora() - timedelta(days=1))
    models.definir_ativo(conn, codigo, False)
    assert models.status_url(models.obter_url(conn, codigo)) == "desativado"


def test_definir_ativo_liga_e_desliga(conn):
    codigo = models.criar_url_curta(conn, "https://exemplo.com")
    assert models.definir_ativo(conn, codigo, False) is True
    assert models.status_url(models.obter_url(conn, codigo)) == "desativado"
    assert models.definir_ativo(conn, codigo, True) is True
    assert models.status_url(models.obter_url(conn, codigo)) == "ativo"


def test_definir_ativo_e_expiracao_em_codigo_inexistente(conn):
    assert models.definir_ativo(conn, "naoexiste", False) is False
    assert models.definir_expiracao(conn, "naoexiste", agora()) is False


def test_definir_e_remover_expiracao(conn):
    codigo = models.criar_url_curta(conn, "https://exemplo.com")
    models.definir_expiracao(conn, codigo, agora() - timedelta(hours=1))
    assert models.status_url(models.obter_url(conn, codigo)) == "expirado"
    models.definir_expiracao(conn, codigo, None)
    assert models.status_url(models.obter_url(conn, codigo)) == "ativo"


def test_banco_antigo_sem_as_colunas_novas_e_migrado():
    antigo = sqlite3.connect(":memory:")
    antigo.row_factory = sqlite3.Row
    antigo.executescript(
        "CREATE TABLE urls (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE NOT NULL,"
        " url_original TEXT NOT NULL, criado_em TEXT NOT NULL);"
        "INSERT INTO urls (codigo, url_original, criado_em) VALUES ('velho1', 'https://x.com', '2025-01-01T00:00:00+00:00');"
    )
    models.inicializar_schema(antigo)
    url = models.obter_url(antigo, "velho1")
    assert url["ativo"] == 1 and url["expira_em"] is None
    assert models.status_url(url) == "ativo"
    models.inicializar_schema(antigo)  # rodar de novo não pode quebrar


def test_listagem_e_estatisticas_trazem_o_status(conn):
    codigo = models.criar_url_curta(conn, "https://exemplo.com", agora() - timedelta(days=1))
    item = models.listar_urls(conn)[0]
    assert item["status"] == "expirado" and item["ativo"] is True
    assert models.obter_estatisticas(conn, codigo)["status"] == "expirado"


# ------------------------------------------------------------------- API
def test_encurtar_com_expiracao_devolve_a_data(client):
    resp = criar(client, expira_em_dias=7)
    expira = datetime.fromisoformat(resp["expira_em"])
    assert timedelta(days=6, hours=23) < expira - agora() < timedelta(days=7, minutes=1)


def test_encurtar_sem_expiracao_nao_tem_data(client):
    assert criar(client)["expira_em"] is None


@pytest.mark.parametrize("dias", [0, -1, 99999])
def test_expiracao_invalida_e_recusada(client, dias):
    resp = client.post("/api/shorten", json={"url": "https://exemplo.com", "expira_em_dias": dias})
    assert resp.status_code == 422


def test_link_expirado_responde_410_e_nao_conta_clique(client):
    codigo = criar(client)["codigo"]
    conn = models.conectar(str(main.DB_PATH))
    models.definir_expiracao(conn, codigo, agora() - timedelta(minutes=1))
    conn.close()
    resp = client.get(f"/{codigo}", follow_redirects=False)
    assert resp.status_code == 410
    assert "expirou" in resp.text and "text/html" in resp.headers["content-type"]
    assert cliques(client, codigo) == 0


def test_desativar_bloqueia_o_redirecionamento_e_reativar_libera(client):
    codigo = criar(client)["codigo"]
    assert client.get(f"/{codigo}", follow_redirects=False).status_code == 302

    resp = client.patch(f"/api/urls/{codigo}", json={"ativo": False})
    assert resp.status_code == 200 and resp.json()["status"] == "desativado"
    bloqueado = client.get(f"/{codigo}", follow_redirects=False)
    assert bloqueado.status_code == 410 and "desativado" in bloqueado.text
    assert cliques(client, codigo) == 1  # só o clique de antes de desativar

    assert client.patch(f"/api/urls/{codigo}", json={"ativo": True}).json()["status"] == "ativo"
    assert client.get(f"/{codigo}", follow_redirects=False).status_code == 302


def test_estender_a_expiracao_reativa_um_link_expirado(client):
    codigo = criar(client, expira_em_dias=1)["codigo"]
    conn = models.conectar(str(main.DB_PATH))
    models.definir_expiracao(conn, codigo, agora() - timedelta(days=1))
    conn.close()
    assert client.get(f"/{codigo}", follow_redirects=False).status_code == 410
    resp = client.patch(f"/api/urls/{codigo}", json={"expira_em_dias": 30})
    assert resp.json()["status"] == "ativo"
    assert client.get(f"/{codigo}", follow_redirects=False).status_code == 302


def test_remover_a_expiracao(client):
    codigo = criar(client, expira_em_dias=1)["codigo"]
    resp = client.patch(f"/api/urls/{codigo}", json={"sem_expiracao": True})
    assert resp.json()["expira_em"] is None


def test_patch_em_codigo_inexistente(client):
    assert client.patch("/api/urls/naoexiste", json={"ativo": False}).status_code == 404


def test_patch_sem_nenhuma_mudanca_e_recusado(client):
    codigo = criar(client)["codigo"]
    assert client.patch(f"/api/urls/{codigo}", json={}).status_code == 422


def test_patch_nao_aceita_expiracao_e_remocao_juntas(client):
    codigo = criar(client)["codigo"]
    resp = client.patch(f"/api/urls/{codigo}", json={"expira_em_dias": 5, "sem_expiracao": True})
    assert resp.status_code == 422


def test_lista_de_urls_mostra_o_status(client):
    ativo = criar(client)["codigo"]
    desligado = criar(client)["codigo"]
    client.patch(f"/api/urls/{desligado}", json={"ativo": False})
    status = {u["codigo"]: u["status"] for u in client.get("/api/urls").json()}
    assert status == {ativo: "ativo", desligado: "desativado"}
