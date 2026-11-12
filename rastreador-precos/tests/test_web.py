"""Testes do painel web: servidor real em porta livre; chamadas locais com urllib.

O site books.toscrape.com é mockado (responses) só no teste de coleta; urllib não é
interceptado pelo `responses`, então as chamadas ao servidor local passam normalmente.
"""
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime

import pytest
import responses

import banco
import web
from scraper import Produto

PAGINA_1 = "https://books.toscrape.com/catalogue/page-1.html"


def produto(id="livro_1", preco=10.0):
    return Produto(id, f"Livro {id}", preco, True, f"https://x/{id}/index.html")


@pytest.fixture
def servidor(tmp_path):
    db = tmp_path / "t.db"
    conn = banco.conectar(db)
    banco.salvar_snapshot(conn, [produto("a", 20.0), produto("b", 30.0)], datetime(2026, 1, 1, 10))
    banco.salvar_snapshot(conn, [produto("a", 14.0), produto("b", 30.0)], datetime(2026, 1, 2, 10))
    conn.close()
    arquivo_alertas = tmp_path / "alertas.log"
    arquivo_alertas.write_text(
        "2026-01-02T10:00:00 | ALERTA | a | Livro a está por £14.00 (limite £15.00) — antes £20.00\n"
        "linha quebrada sem separadores\n",
        encoding="utf-8",
    )
    srv = web.criar_servidor(db, arquivo_alertas, porta=0, limite=15.0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()


def post(url, dados):
    req = urllib.request.Request(url, data=json.dumps(dados).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_pagina_inicial_e_estaticos(servidor):
    status, tipo, corpo = get(servidor + "/")
    assert status == 200 and "text/html" in tipo and "Rastreador de preços" in corpo.decode()
    assert get(servidor + "/static/style.css")[1].startswith("text/css")
    assert "javascript" in get(servidor + "/static/app.js")[1]


def test_nao_serve_arquivos_fora_da_pasta_static(servidor):
    assert get(servidor + "/static/../web.py")[0] == 404
    assert get(servidor + "/static/%2e%2e/web.py")[0] == 404


def test_config(servidor):
    assert json.loads(get(servidor + "/api/config")[2]) == {"limite": 15.0, "paginas": 1}


def test_lista_de_produtos_com_resumo(servidor):
    itens = {p["id"]: p for p in json.loads(get(servidor + "/api/produtos")[2])}
    assert itens["a"]["preco"] == 14.0 and itens["a"]["preco_inicial"] == 20.0
    assert itens["a"]["coletas"] == 2 and itens["a"]["menor_preco"] == 14.0
    assert itens["b"]["preco"] == itens["b"]["preco_inicial"] == 30.0


def test_detalhe_do_produto(servidor):
    d = json.loads(get(servidor + "/api/produto/a")[2])
    assert d["nome"] == "Livro a" and [p["preco"] for p in d["pontos"]] == [20.0, 14.0]
    assert d["resumo"]["menor_preco"] == 14.0 and d["resumo"]["maior_queda"]["valor"] == 6.0


def test_produto_inexistente(servidor):
    status, tipo, corpo = get(servidor + "/api/produto/nao-existe")
    assert status == 404 and "erro" in json.loads(corpo)


def test_alertas_ignora_linhas_quebradas(servidor):
    itens = json.loads(get(servidor + "/api/alertas")[2])
    assert len(itens) == 1 and itens[0]["produto_id"] == "a" and "£14.00" in itens[0]["mensagem"]


def test_alertas_sem_arquivo(tmp_path):
    assert web.ler_alertas(tmp_path / "nao-existe.log") == []


def test_rota_inexistente(servidor):
    assert get(servidor + "/api/qualquer")[0] == 404


@responses.activate
def test_coletar_agora_grava_e_alerta(servidor, html_pagina1):
    responses.add(responses.GET, PAGINA_1, body=html_pagina1, status=200)
    status, resp = post(servidor + "/api/coletar", {"limite": 20})
    assert status == 200 and resp["produtos"] == 20 and resp["alertas"] == 3 and resp["erro"] is None
    produtos = json.loads(get(servidor + "/api/produtos")[2])
    assert len(produtos) == 22  # 2 do fixture do teste + 20 coletados
    assert len(json.loads(get(servidor + "/api/alertas")[2])) >= 3


@responses.activate
def test_coletar_agora_falha_de_rede_devolve_502(servidor):
    responses.add(responses.GET, PAGINA_1, status=500)
    status, resp = post(servidor + "/api/coletar", {})
    assert status == 502 and resp["erro"]


def test_coletar_agora_parametros_invalidos(servidor):
    status, resp = post(servidor + "/api/coletar", {"limite": "abc"})
    assert status == 422 and "erro" in resp
