"""Publicação: modo somente leitura, /healthz e demonstração offline (sem internet)."""
import json
import threading
import urllib.error
import urllib.request

import pytest
import responses

import banco
import cli
import demo
import web


def get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def post(url, dados):
    req = urllib.request.Request(url, data=json.dumps(dados).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@pytest.fixture
def servidor_publico(tmp_path):
    """Servidor como na hospedagem: demonstração offline + somente leitura."""
    db, log = tmp_path / "pub.db", tmp_path / "alertas.log"
    with responses.RequestsMock():  # qualquer requisição de rede levantaria erro
        assert demo.preparar_demonstracao(db, log, 25.0) is True
    srv = web.criar_servidor(db, log, porta=0, limite=25.0, somente_leitura=True, demo=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", db, log
    srv.shutdown()
    srv.server_close()


# --------------------------------------------------------------- demonstração
def test_base_offline_traz_os_20_produtos_reais():
    base = demo.base_offline()
    assert len(base) == 20
    assert base[0].nome == "A Light in the Attic" and base[0].preco == 51.77


def test_preparar_demonstracao_funciona_sem_internet(tmp_path):
    db = tmp_path / "d.db"
    with responses.RequestsMock():  # nenhuma requisição mockada: se tentasse a rede, falharia
        assert demo.preparar_demonstracao(db, tmp_path / "a.log") is True
    conn = banco.conectar(db)
    assert conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == 20
    assert conn.execute("SELECT COUNT(*) FROM historico_precos").fetchone()[0] == 200  # 10 coletas x 20 produtos


def test_demonstracao_cria_alertas_de_exemplo_quando_ha_limite(tmp_path):
    log = tmp_path / "alertas.log"
    demo.preparar_demonstracao(tmp_path / "d.db", log, 25.0)
    linhas = log.read_text(encoding="utf-8").splitlines()
    assert linhas and all(" | ALERTA | " in linha for linha in linhas)


def test_demonstracao_sem_limite_nao_cria_alertas(tmp_path):
    log = tmp_path / "alertas.log"
    demo.preparar_demonstracao(tmp_path / "d.db", log)
    assert not log.exists()


def test_demonstracao_nao_mexe_em_banco_com_dados(tmp_path):
    db, log = tmp_path / "d.db", tmp_path / "a.log"
    assert demo.preparar_demonstracao(db, log, 25.0) is True
    antes = log.read_text(encoding="utf-8")
    assert demo.preparar_demonstracao(db, log, 25.0) is False
    conn = banco.conectar(db)
    assert conn.execute("SELECT COUNT(*) FROM historico_precos").fetchone()[0] == 200
    assert log.read_text(encoding="utf-8") == antes  # sem alertas duplicados


# ------------------------------------------------------ servidor somente leitura
def test_healthz_e_publico(servidor_publico):
    url, _, _ = servidor_publico
    status, corpo = get(url + "/healthz")
    assert status == 200 and json.loads(corpo) == {"status": "ok"}


def test_config_informa_os_modos(servidor_publico):
    url, _, _ = servidor_publico
    cfg = json.loads(get(url + "/api/config")[1])
    assert cfg["somente_leitura"] is True and cfg["demo"] is True and cfg["limite"] == 25.0


def test_coleta_e_recusada_em_modo_somente_leitura(servidor_publico):
    url, db, _ = servidor_publico
    conn = banco.conectar(db)
    antes = conn.execute("SELECT COUNT(*) FROM historico_precos").fetchone()[0]
    conn.close()
    with responses.RequestsMock():  # se tentasse coletar, a rede levantaria erro
        status, resp = post(url + "/api/coletar", {"limite": 20})
    assert status == 403 and "somente leitura" in resp["erro"]
    conn = banco.conectar(db)
    assert conn.execute("SELECT COUNT(*) FROM historico_precos").fetchone()[0] == antes


def test_leitura_continua_funcionando(servidor_publico):
    url, _, _ = servidor_publico
    produtos = json.loads(get(url + "/api/produtos")[1])
    assert len(produtos) == 20 and all(p["coletas"] == 10 for p in produtos)
    detalhe = json.loads(get(url + "/api/produto/" + produtos[0]["id"])[1])
    assert len(detalhe["pontos"]) == 10
    assert get(url + "/")[0] == 200
    assert len(json.loads(get(url + "/api/alertas")[1])) > 0


def test_servidor_normal_continua_aceitando_coleta(tmp_path):
    """Sem as opções novas, nada muda: a coleta segue habilitada."""
    srv = web.criar_servidor(tmp_path / "n.db", tmp_path / "a.log", porta=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        assert json.loads(get(url + "/api/config")[1])["somente_leitura"] is False
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "https://books.toscrape.com/catalogue/page-1.html", status=500)
            status, _ = post(url + "/api/coletar", {})
        assert status == 502  # tentou coletar (e a rede mockada falhou), em vez de recusar com 403
    finally:
        srv.shutdown()
        srv.server_close()


# ------------------------------------------------------------------------- CLI
def test_cli_servir_tem_as_opcoes_novas():
    a = cli.montar_parser().parse_args(["servir", "--somente-leitura", "--demo", "--porta", "10000", "--host", "0.0.0.0"])
    assert a.somente_leitura is True and a.demo is True and a.porta == 10000 and a.host == "0.0.0.0"


def test_cli_servir_por_padrao_nao_e_somente_leitura():
    a = cli.montar_parser().parse_args(["servir"])
    assert a.somente_leitura is False and a.demo is False
