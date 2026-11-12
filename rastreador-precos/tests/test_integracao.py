"""Testes ponta a ponta (coleta -> banco -> alerta -> CLI), sem internet: HTTP mockado."""
import pytest
import responses

import agendador
import banco
import cli
import coleta

PAGINA_1 = "https://books.toscrape.com/catalogue/page-1.html"


@pytest.fixture
def site(html_pagina1):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, PAGINA_1, body=html_pagina1, status=200)
        yield rsps


def test_coleta_salva_e_gera_alerta(site, tmp_path):
    db, log_alertas = tmp_path / "t.db", tmp_path / "alertas.log"
    r = coleta.executar_coleta(db, paginas=1, limite=20.0, arquivo_alertas=log_alertas)
    assert r == {"produtos": 20, "alertas": r["alertas"], "erro": None}
    assert r["alertas"] > 0
    assert len(log_alertas.read_text(encoding="utf-8").splitlines()) == r["alertas"]
    conn = banco.conectar(db)
    assert conn.execute("SELECT COUNT(*) FROM historico_precos").fetchone()[0] == 20


def test_duas_coletas_formam_historico(html_pagina1, tmp_path):
    db = tmp_path / "t.db"
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, PAGINA_1, body=html_pagina1, status=200)
        rsps.add(responses.GET, PAGINA_1, body=html_pagina1, status=200)
        coleta.executar_coleta(db, arquivo_alertas=tmp_path / "a.log")
        coleta.executar_coleta(db, arquivo_alertas=tmp_path / "a.log")
    conn = banco.conectar(db)
    assert len(banco.historico(conn, "a-light-in-the-attic_1000")) == 2


def test_falha_de_rede_nao_levanta_excecao(tmp_path):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, PAGINA_1, status=500)
        r = coleta.executar_coleta(tmp_path / "t.db", arquivo_alertas=tmp_path / "a.log")
    assert r["produtos"] == 0 and r["erro"]


def test_agendador_executa_n_vezes():
    chamadas = []
    # dormir falso: avança o relógio real o mínimo necessário para o job vencer
    import time

    feitas = agendador.rodar(lambda: chamadas.append(1), intervalo_segundos=0.2, execucoes=3, dormir=lambda s: time.sleep(0.25))
    assert feitas == 3 and len(chamadas) == 3


def test_cli_fluxo_completo(site, tmp_path, capsys):
    db = str(tmp_path / "t.db")
    base = ["--db", db]
    assert cli.main(["coletar", *base, "--limite", "15", "--alertas", str(tmp_path / "a.log"), "--log", str(tmp_path / "r.log")]) == 0
    assert cli.main(["listar", *base, "--limite", "3"]) == 0
    assert "A Light in the Attic" in capsys.readouterr().out
    png = tmp_path / "g.png"
    assert cli.main(["analisar", "light in the attic", *base, "--grafico", str(png)]) == 0
    assert png.exists()
    assert "Preço atual: £51.77" in capsys.readouterr().out


def test_cli_produto_inexistente(tmp_path, capsys):
    assert cli.main(["analisar", "nada", "--db", str(tmp_path / "t.db")]) == 1
