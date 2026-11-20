"""Testes das métricas do dashboard web (dashboard/metricas.py)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "dashboard"))

import metricas  # noqa: E402
from analise import calcular_metricas  # noqa: E402  (src/ entra no path pelo conftest.py)
from gerar_dados import SEED, gerar_vendas  # noqa: E402


def df_exemplo() -> pd.DataFrame:
    dados = [
        ("2023-06-01", "Eletrônicos", "Smartphone", "Sudeste", "Online", 1000.0),
        ("2023-11-15", "Eletrônicos", "Smartphone", "Sudeste", "Online", 3000.0),
        ("2023-12-10", "Moda", "Boné", "Sul", "Loja Física", 500.0),
        ("2024-06-01", "Eletrônicos", "Carregador", "Sudeste", "Online", 1200.0),
        ("2024-11-20", "Moda", "Boné", "Sul", "Online", 800.0),
    ]
    colunas = ["data", "categoria", "produto", "regiao", "canal", "receita"]
    return metricas.preparar(pd.DataFrame(dados, columns=colunas))


@pytest.fixture(scope="module")
def base_real() -> pd.DataFrame:
    """A mesma base do projeto, gerada em memória (sem gravar arquivo)."""
    return metricas.preparar(gerar_vendas(np.random.default_rng(SEED)))


def test_indicadores_basicos():
    ind = metricas.indicadores(df_exemplo())
    assert ind["vendas"] == 5
    assert ind["receita"] == 6500
    assert ind["ticket_medio"] == 1300
    assert ind["crescimento_pct"] == pytest.approx((2000 / 4500 - 1) * 100)


def test_filtro_lista_vazia_nao_filtra():
    df = df_exemplo()
    assert len(metricas.filtrar(df, anos=[], regioes=None)) == 5
    assert len(metricas.filtrar(df, anos=[2024], canais=["Online"])) == 2


def test_crescimento_sem_ano_anterior_e_none():
    so_2023 = metricas.filtrar(df_exemplo(), anos=[2023])
    assert metricas.crescimento_anual(so_2023) is None


def test_base_vazia_nao_quebra():
    vazio = metricas.filtrar(df_exemplo(), regioes=["Norte"])
    ind = metricas.indicadores(vazio)
    assert ind["vendas"] == 0 and ind["ticket_medio"] is None and ind["crescimento_pct"] is None
    assert metricas.efeito_alta_temporada(vazio) is None


def test_efeito_alta_temporada_usa_media_por_mes():
    # Nov/Dez: (3000 + 500 + 800) em 3 meses distintos; demais: (1000 + 1200) em 2 meses
    esperado = (4300 / 3) / (2200 / 2)
    assert metricas.efeito_alta_temporada(df_exemplo()) == pytest.approx(esperado)


def test_receita_mensal_por_ano_tem_12_meses():
    tabela = metricas.receita_mensal_por_ano(df_exemplo())
    assert list(tabela.index) == metricas.NOMES_MESES
    assert tabela.loc["Nov", 2023] == 3000


def test_bate_com_a_analise_e_com_o_power_bi(base_real):
    """Os números do painel web precisam ser os mesmos do relatório e do Power BI."""
    ind = metricas.indicadores(base_real)
    referencia = calcular_metricas(base_real.assign(mes=base_real["ano_mes"]))

    assert ind["vendas"] == 6655
    assert ind["receita"] == pytest.approx(4_429_491.93, abs=0.01)
    assert ind["ticket_medio"] == pytest.approx(665.59, abs=0.01)
    assert ind["crescimento_pct"] == pytest.approx(referencia["crescimento_yoy_pct"])
    assert metricas.efeito_alta_temporada(base_real) == pytest.approx(
        referencia["media_mensal_alta_temporada"] / referencia["media_mensal_resto"])
    assert metricas.receita_por(base_real, "categoria").index[0] == "Eletrônicos"
    assert metricas.participacao_canal_por_ano(base_real).loc[2024, "pct_online"] == pytest.approx(62.64, abs=0.01)
