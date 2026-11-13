import json
from datetime import datetime

import alertas
from scraper import Produto


def p(id, preco, disponivel=True):
    return Produto(id, f"Livro {id}", preco, disponivel, "https://x/")


def test_alerta_quando_abaixo_do_limite():
    r = alertas.verificar([p("a", 9.99), p("b", 25.0)], limite_padrao=10.0)
    assert [a.produto_id for a in r] == ["a"]


def test_preco_igual_ao_limite_nao_alerta():
    assert alertas.verificar([p("a", 10.0)], limite_padrao=10.0) == []


def test_sem_limite_nao_alerta():
    assert alertas.verificar([p("a", 1.0)], limite_padrao=None) == []


def test_produto_indisponivel_nao_alerta():
    assert alertas.verificar([p("a", 1.0, disponivel=False)], limite_padrao=10.0) == []


def test_limite_por_produto_tem_prioridade():
    r = alertas.verificar([p("a", 15.0), p("b", 15.0)], 10.0, limites_por_produto={"a": 20.0})
    assert [a.produto_id for a in r] == ["a"]


def test_mensagem_mostra_preco_anterior():
    r = alertas.verificar([p("a", 8.0)], 10.0, {"a": 12.5})
    assert "£8.00" in r[0].mensagem() and "antes £12.50" in r[0].mensagem()


def test_registrar_escreve_no_arquivo(tmp_path):
    arquivo = tmp_path / "alertas.log"
    r = alertas.verificar([p("a", 8.0)], 10.0)
    assert alertas.registrar(r, arquivo, datetime(2026, 1, 1, 9, 30)) == 1
    alertas.registrar(r, arquivo)  # acrescenta, não sobrescreve
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 2
    assert linhas[0].startswith("2026-01-01T09:30:00 | ALERTA | a |")


def test_registrar_sem_alertas_nao_cria_arquivo(tmp_path):
    arquivo = tmp_path / "alertas.log"
    assert alertas.registrar([], arquivo) == 0
    assert not arquivo.exists()


def test_carregar_limites(tmp_path):
    f = tmp_path / "limites.json"
    f.write_text(json.dumps({"a": "12.5", "b": 7}), encoding="utf-8")
    assert alertas.carregar_limites(f) == {"a": 12.5, "b": 7.0}


def test_mensagem_quando_o_preco_subiu_mas_continua_abaixo_do_limite():
    r = alertas.verificar([p("a", 9.0)], 10.0, {"a": 7.5})
    msg = r[0].mensagem()
    assert "subiu de £7.50" in msg and "continua abaixo do limite" in msg and "antes" not in msg


def test_mensagem_sem_mudanca_de_preco_nao_cita_o_anterior():
    msg = alertas.verificar([p("a", 8.0)], 10.0, {"a": 8.0})[0].mensagem()
    assert "antes" not in msg and "subiu" not in msg
