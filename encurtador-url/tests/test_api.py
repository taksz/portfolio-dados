import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "teste.db")
    with TestClient(main.app) as c:
        yield c


def test_encurtar_url_valida(client):
    resp = client.post("/api/shorten", json={"url": "https://exemplo.com/pagina"})
    assert resp.status_code == 200
    dados = resp.json()
    assert len(dados["codigo"]) == 6
    assert dados["url_original"] == "https://exemplo.com/pagina"
    assert dados["codigo"] in dados["url_curta"]


def test_encurtar_url_invalida(client):
    resp = client.post("/api/shorten", json={"url": "não-e-uma-url"})
    assert resp.status_code == 422


def test_redirecionamento_funciona(client):
    codigo = client.post("/api/shorten", json={"url": "https://exemplo.com/destino"}).json()["codigo"]

    resp = client.get(f"/{codigo}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://exemplo.com/destino"


def test_redirecionamento_codigo_inexistente(client):
    resp = client.get("/naoexiste", follow_redirects=False)
    assert resp.status_code == 404


def test_clique_e_registrado_no_analytics(client):
    codigo = client.post("/api/shorten", json={"url": "https://exemplo.com"}).json()["codigo"]

    client.get(f"/{codigo}", follow_redirects=False, headers={"User-Agent": "Chrome/119.0.0.0"})
    client.get(f"/{codigo}", follow_redirects=False, headers={"User-Agent": "Firefox/119.0"})

    stats = client.get(f"/api/analytics/{codigo}").json()
    assert stats["total_cliques"] == 2
    navegadores = {n["navegador"] for n in stats["navegadores"]}
    assert navegadores == {"Chrome", "Firefox"}


def test_analytics_codigo_inexistente(client):
    resp = client.get("/api/analytics/naoexiste")
    assert resp.status_code == 404


def test_listar_urls(client):
    client.post("/api/shorten", json={"url": "https://a.com"})
    client.post("/api/shorten", json={"url": "https://b.com"})

    resp = client.get("/api/urls")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_dashboard_existe_para_codigo_valido(client):
    codigo = client.post("/api/shorten", json={"url": "https://exemplo.com"}).json()["codigo"]
    resp = client.get(f"/dashboard/{codigo}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_dashboard_404_para_codigo_invalido(client):
    resp = client.get("/dashboard/naoexiste")
    assert resp.status_code == 404
