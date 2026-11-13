"""Autenticação simples (HTTP Basic) ligada pela variável ENCURTADOR_SENHA."""
import pytest
from fastapi.testclient import TestClient

from app import main

SENHA = "segredo-de-teste"
LOGIN = ("admin", SENHA)

# rotas que devem ficar atrás da senha: (método, caminho, corpo)
PROTEGIDAS = [
    ("GET", "/", None),
    ("GET", "/api/urls", None),
    ("POST", "/api/shorten", {"url": "https://exemplo.com"}),
    ("GET", "/api/analytics/{codigo}", None),
    ("GET", "/dashboard/{codigo}", None),
    ("PATCH", "/api/urls/{codigo}", {"ativo": False}),
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "teste.db")
    monkeypatch.delenv("ENCURTADOR_SENHA", raising=False)
    monkeypatch.delenv("ENCURTADOR_USUARIO", raising=False)
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def protegido(client, monkeypatch):
    """Cliente com um link já criado e a senha ligada."""
    codigo = client.post("/api/shorten", json={"url": "https://exemplo.com"}).json()["codigo"]
    monkeypatch.setenv("ENCURTADOR_SENHA", SENHA)
    return client, codigo


def chamar(client, metodo, caminho, corpo, codigo, **kwargs):
    return client.request(metodo, caminho.format(codigo=codigo), json=corpo, follow_redirects=False, **kwargs)


def test_sem_senha_configurada_tudo_fica_aberto(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/urls").status_code == 200


@pytest.mark.parametrize("metodo,caminho,corpo", PROTEGIDAS)
def test_sem_credenciais_pede_login(protegido, metodo, caminho, corpo):
    client, codigo = protegido
    resp = chamar(client, metodo, caminho, corpo, codigo)
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].startswith("Basic")


@pytest.mark.parametrize("metodo,caminho,corpo", PROTEGIDAS)
def test_senha_errada_e_recusada(protegido, metodo, caminho, corpo):
    client, codigo = protegido
    assert chamar(client, metodo, caminho, corpo, codigo, auth=("admin", "errada")).status_code == 401


@pytest.mark.parametrize("metodo,caminho,corpo", PROTEGIDAS)
def test_credenciais_corretas_liberam(protegido, metodo, caminho, corpo):
    client, codigo = protegido
    assert chamar(client, metodo, caminho, corpo, codigo, auth=LOGIN).status_code == 200


def test_usuario_errado_com_senha_certa_e_recusado(protegido):
    client, _ = protegido
    assert client.get("/api/urls", auth=("outro", SENHA)).status_code == 401


def test_usuario_pode_ser_trocado_pela_variavel(protegido, monkeypatch):
    client, _ = protegido
    monkeypatch.setenv("ENCURTADOR_USUARIO", "arthur")
    assert client.get("/api/urls", auth=("admin", SENHA)).status_code == 401
    assert client.get("/api/urls", auth=("arthur", SENHA)).status_code == 200


def test_links_curtos_continuam_publicos(protegido):
    client, codigo = protegido
    resp = client.get(f"/{codigo}", follow_redirects=False)
    assert resp.status_code == 302 and resp.headers["location"] == "https://exemplo.com"


def test_arquivos_estaticos_continuam_publicos(protegido):
    client, _ = protegido
    assert client.get("/static/style.css").status_code == 200


def test_clique_em_link_publico_aparece_no_painel_protegido(protegido):
    client, codigo = protegido
    client.get(f"/{codigo}", follow_redirects=False)
    stats = client.get(f"/api/analytics/{codigo}", auth=LOGIN).json()
    assert stats["total_cliques"] == 1


def test_senha_vazia_equivale_a_sem_senha(client, monkeypatch):
    monkeypatch.setenv("ENCURTADOR_SENHA", "")
    assert client.get("/api/urls").status_code == 200


def test_verificacao_de_saude_e_publica_mesmo_com_senha(protegido):
    """A hospedagem (Render) chama /healthz sem credenciais: ele não pode pedir login."""
    client, _ = protegido
    resp = client.get("/healthz")
    assert resp.status_code == 200 and resp.json() == {"status": "ok"}


def test_verificacao_de_saude_sem_senha(client):
    assert client.get("/healthz").json() == {"status": "ok"}
