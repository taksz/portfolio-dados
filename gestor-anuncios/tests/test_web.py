import shutil

import pytest
from fastapi.testclient import TestClient

import demo
import web
from adaptadores import criar_adaptadores_demo
from regras import SITUACOES


@pytest.fixture(scope="module")
def base_demo(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("demo")
    demo.gerar(pasta / "demo.db", pasta / "alertas.log")
    return pasta


@pytest.fixture
def arquivos(base_demo, tmp_path):
    """Cópia do banco demo por teste (a coleta altera o banco)."""
    shutil.copy(base_demo / "demo.db", tmp_path / "demo.db")
    shutil.copy(base_demo / "alertas.log", tmp_path / "alertas.log")
    return tmp_path / "demo.db", tmp_path / "alertas.log"


@pytest.fixture
def cliente(arquivos):
    db, arq = arquivos
    return TestClient(web.criar_app(db, arq, criar_adaptadores_demo(), demo=True))


def test_healthz(cliente):
    assert cliente.get("/healthz").json() == {"status": "ok"}


def test_pagina_inicial_serve_html(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert cliente.get("/static/app.js").status_code == 200


def test_resumo_conta_todo_o_estoque(cliente):
    r = cliente.get("/api/resumo").json()
    assert r["total"] == 40
    assert sum(r["por_situacao"].values()) == 40
    assert set(r["por_situacao"]) == set(SITUACOES)
    assert r["remover"] == 4
    assert r["ultima_coleta"] == "2026-10-20T09:00:00"
    assert r["demo"] is True and r["somente_leitura"] is False
    assert r["plataformas"] == ["AutoFeira", "CarroJá", "Vitrine Motors"]
    assert r["valor_parado"] > 0
    assert r["rotulos"]["nao_converte"] == "Atrai mas não converte"


def test_contagem_do_placar_bate_com_o_filtro(cliente):
    contagem = cliente.get("/api/resumo").json()["por_filtro"]
    for situacao in ("parado", "nao_converte", "preco_alto", "vendido"):
        filtrados = cliente.get("/api/veiculos", params={"situacao": situacao}).json()["veiculos"]
        assert contagem[situacao] == len(filtrados)


def test_lista_veiculos_com_diagnostico(cliente):
    veiculos = cliente.get("/api/veiculos").json()["veiculos"]
    assert len(veiculos) == 40
    v = veiculos[0]
    assert v["situacao"] == "vendido"  # mais urgente primeiro
    for campo in ("placa", "marca", "modelo", "ano", "km", "preco_atual", "referencia", "sugestao", "rotulo",
                  "plataformas", "sinais", "dias_anunciado", "contatos_janela", "remover_de", "motivo"):
        assert campo in v


def test_filtro_por_situacao_inclui_sinais(cliente):
    parados = cliente.get("/api/veiculos", params={"situacao": "parado"}).json()["veiculos"]
    assert parados
    assert all(v["situacao"] == "parado" or "parado" in v["sinais"] for v in parados)
    assert any(v["situacao"] != "parado" for v in parados)


def test_filtro_por_plataforma_e_marca(cliente):
    todos = cliente.get("/api/veiculos").json()["veiculos"]
    so_af = cliente.get("/api/veiculos", params={"plataforma": "AutoFeira"}).json()["veiculos"]
    assert 0 < len(so_af) < len(todos)
    assert all("AutoFeira" in v["plataformas"] for v in so_af)
    fiat = cliente.get("/api/veiculos", params={"marca": "Fiat"}).json()["veiculos"]
    assert fiat and all(v["marca"] == "Fiat" for v in fiat)


def test_busca_por_modelo_ou_placa(cliente):
    corolla = cliente.get("/api/veiculos", params={"q": "corolla"}).json()["veiculos"]
    assert len(corolla) == 2
    placa = corolla[0]["placa"]
    com_hifen = f"{placa[:3]}-{placa[3:]}".lower()
    achados = cliente.get("/api/veiculos", params={"q": com_hifen}).json()["veiculos"]
    assert [v["placa"] for v in achados] == [placa]


def test_filtros_combinados_sem_resultado(cliente):
    r = cliente.get("/api/veiculos", params={"marca": "Fiat", "q": "corolla"}).json()
    assert r["veiculos"] == []


def test_detalhe_com_historico(cliente):
    placa = cliente.get("/api/veiculos").json()["veiculos"][0]["placa"]
    r = cliente.get(f"/api/veiculos/{placa[:3]}-{placa[3:].lower()}")
    assert r.status_code == 200
    dados = r.json()
    assert dados["veiculo"]["placa"] == placa
    assert len(dados["historico"]) == 8
    ponto = dados["historico"][-1]
    assert set(ponto) == {"coletado_em", "precos", "visitas", "contatos"}
    assert {a["status"] for a in dados["anuncios"]} >= {"vendido"}


def test_detalhe_inexistente_404(cliente):
    assert cliente.get("/api/veiculos/ZZZ9Z99").status_code == 404
    assert cliente.get("/api/veiculos/nao-e-placa").status_code == 404


def test_coletar_agora(cliente):
    r = cliente.post("/api/coletar")
    assert r.status_code == 200
    assert r.json()["veiculos"] == 40
    assert cliente.get("/api/resumo").json()["ultima_coleta"] != "2026-10-20T09:00:00"


def test_coletar_bloqueado_em_somente_leitura(arquivos):
    db, arq = arquivos
    c = TestClient(web.criar_app(db, arq, criar_adaptadores_demo(), somente_leitura=True))
    assert c.post("/api/coletar").status_code == 403
    assert c.get("/api/resumo").json()["somente_leitura"] is True


def test_coletar_sem_adaptadores_e_bloqueado(arquivos):
    db, arq = arquivos
    assert TestClient(web.criar_app(db, arq)).post("/api/coletar").status_code == 403


def test_alertas_recentes_com_limite(cliente):
    alertas = cliente.get("/api/alertas", params={"limite": 3}).json()["alertas"]
    assert len(alertas) == 3
    assert alertas[0]["quando"] >= alertas[-1]["quando"]


def test_banco_vazio_nao_quebra(tmp_path):
    c = TestClient(web.criar_app(tmp_path / "vazio.db", tmp_path / "a.log"))
    assert c.get("/api/resumo").json()["total"] == 0
    assert c.get("/api/veiculos").json()["veiculos"] == []
    assert c.get("/api/alertas").json()["alertas"] == []
