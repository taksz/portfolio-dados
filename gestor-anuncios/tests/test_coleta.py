import time
from datetime import datetime, timedelta

import agendador
import alertas
import banco
import coleta
from adaptadores import AdaptadorPlataforma, criar_adaptadores_demo
from modelos import AnuncioColetado

INICIO = datetime(2026, 9, 1, 9, 0, 0)


class Fixo(AdaptadorPlataforma):
    """Plataforma de teste que devolve o que mandarmos."""

    def __init__(self, nome="Teste"):
        self.nome = nome
        self.status = "ativo"
        self.contatos = 0

    def coletar(self, agora):
        return [AnuncioColetado(
            plataforma=self.nome, anuncio_id="t1", placa="TST1A23", marca="Fiat", modelo="Argo", versao="Drive",
            ano=2021, km=60000, preco=64900.0, preco_referencia=64900.0, visualizacoes=10, contatos=self.contatos,
            status=self.status, publicado_em=INICIO - timedelta(days=60),
        )]


class Quebrado(AdaptadorPlataforma):
    nome = "Fora do Ar"

    def coletar(self, agora):
        raise ConnectionError("plataforma indisponível")


def test_primeira_coleta_demo_salva_e_gera_alertas(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    arq = tmp_path / "alertas.log"
    r = coleta.executar(criar_adaptadores_demo(), conn, arq, INICIO + timedelta(weeks=5))
    assert r["veiculos"] > 30 and r["anuncios"] >= r["veiculos"]
    assert r["erros"] == 0
    assert r["alertas"] > 0
    assert len(arq.read_text(encoding="utf-8").splitlines()) == r["alertas"]


def test_repetir_coleta_sem_mudanca_nao_duplica_alerta(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    arq = tmp_path / "alertas.log"
    plataforma = Fixo()
    assert coleta.executar([plataforma], conn, arq, INICIO)["alertas"] == 1  # parado
    assert coleta.executar([plataforma], conn, arq, INICIO + timedelta(days=1))["alertas"] == 0
    assert len(alertas.ler(arq)) == 1


def test_mudanca_de_situacao_gera_novo_alerta(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    arq = tmp_path / "alertas.log"
    plataforma = Fixo()
    coleta.executar([plataforma], conn, arq, INICIO)
    plataforma.status = "vendido"
    r = coleta.executar([plataforma], conn, arq, INICIO + timedelta(days=7))
    assert r["alertas"] == 1
    ultimo = alertas.ler(arq)[0]
    assert ultimo["placa"] == "TST1A23"
    assert "Vendido" in ultimo["mensagem"]
    assert banco.situacao_salva(conn, "TST1A23") == "vendido"


def test_mudanca_para_situacao_boa_atualiza_sem_alertar(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    arq = tmp_path / "alertas.log"
    plataforma = Fixo()
    coleta.executar([plataforma], conn, arq, INICIO)
    plataforma.contatos = 10
    assert coleta.executar([plataforma], conn, arq, INICIO + timedelta(days=7))["alertas"] == 0
    assert banco.situacao_salva(conn, "TST1A23") == "bem"


def test_falha_de_uma_plataforma_nao_derruba_as_outras(tmp_path, caplog):
    conn = banco.conectar(tmp_path / "g.db")
    r = coleta.executar([Quebrado(), Fixo()], conn, tmp_path / "a.log", INICIO)
    assert r["erros"] == 1
    assert r["anuncios"] == 1
    assert "plataforma indisponível" in caplog.text


class Vazio(AdaptadorPlataforma):
    nome = "Teste"

    def coletar(self, agora):
        return []


def test_resposta_vazia_de_plataforma_com_anuncios_conhecidos_e_tratada_como_falha(tmp_path, caplog):
    conn = banco.conectar(tmp_path / "g.db")
    arq = tmp_path / "a.log"
    coleta.executar([Fixo()], conn, arq, INICIO)
    r = coleta.executar([Vazio()], conn, arq, INICIO + timedelta(days=7))
    assert r["erros"] == 1
    assert [s["status"] for s in banco.snapshots_do_veiculo(conn, "TST1A23")] == ["ativo"]
    assert "nenhum anúncio" in caplog.text


def test_todas_as_plataformas_falhando_nao_reavalia_nem_alerta(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    arq = tmp_path / "a.log"
    plataforma = Fixo()
    plataforma.contatos = 10
    coleta.executar([plataforma], conn, arq, INICIO - timedelta(days=7))
    plataforma.contatos = 30
    coleta.executar([plataforma], conn, arq, INICIO)
    assert banco.situacao_salva(conn, "TST1A23") == "bem"
    r = coleta.executar([Quebrado()], conn, arq, INICIO + timedelta(days=20))
    assert r == {"anuncios": 0, "veiculos": 0, "alertas": 0, "erros": 1}
    assert banco.situacao_salva(conn, "TST1A23") == "bem"


def test_ler_alertas_sem_arquivo(tmp_path):
    assert alertas.ler(tmp_path / "nao-existe.log") == []


def test_ler_alertas_mais_recentes_primeiro_com_limite(tmp_path):
    arq = tmp_path / "a.log"
    alertas.registrar([("AAA1A11", "primeiro")], arq, INICIO)
    alertas.registrar([("BBB2B22", "segundo"), ("CCC3C33", "terceiro")], arq, INICIO + timedelta(days=1))
    lidos = alertas.ler(arq, limite=2)
    assert [a["mensagem"] for a in lidos] == ["terceiro", "segundo"]
    assert lidos[0]["quando"] == "2026-09-02T09:00:00"


def test_agendador_executa_n_vezes():
    chamadas = []
    feitas = agendador.rodar(lambda: chamadas.append(1), intervalo_segundos=0.2, execucoes=3,
                             dormir=lambda s: time.sleep(0.25))
    assert feitas == 3 and len(chamadas) == 3


def test_agendador_sobrevive_a_erro_na_tarefa():
    chamadas = []

    def tarefa():
        chamadas.append(1)
        if len(chamadas) == 1:
            raise RuntimeError("falhou")

    assert agendador.rodar(tarefa, intervalo_segundos=0.2, execucoes=2, dormir=lambda s: time.sleep(0.25)) == 2
