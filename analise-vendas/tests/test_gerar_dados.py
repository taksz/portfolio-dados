import pytest
import numpy as np
import pandas as pd

from gerar_dados import CATALOGO, DATA_FIM, DATA_INICIO, _fator_sazonal, gerar_vendas


def test_reprodutibilidade_com_mesma_seed():
    df1 = gerar_vendas(np.random.default_rng(42))
    df2 = gerar_vendas(np.random.default_rng(42))
    pd.testing.assert_frame_equal(df1, df2)


def test_seeds_diferentes_geram_dados_diferentes():
    df1 = gerar_vendas(np.random.default_rng(1))
    df2 = gerar_vendas(np.random.default_rng(2))
    assert not df1["receita"].equals(df2["receita"])


def test_colunas_esperadas():
    df = gerar_vendas(np.random.default_rng(42))
    esperadas = {
        "id_venda", "data", "categoria", "produto",
        "quantidade", "preco_unitario", "receita", "regiao", "canal",
    }
    assert esperadas.issubset(df.columns)


def test_datas_dentro_do_periodo():
    df = gerar_vendas(np.random.default_rng(42))
    datas = pd.to_datetime(df["data"])
    assert datas.min().date() >= DATA_INICIO
    assert datas.max().date() <= DATA_FIM


def test_categorias_e_produtos_validos():
    df = gerar_vendas(np.random.default_rng(42))
    assert set(df["categoria"].unique()).issubset(set(CATALOGO.keys()))
    for categoria, grupo in df.groupby("categoria"):
        produtos_validos = set(CATALOGO[categoria][0])
        assert set(grupo["produto"].unique()).issubset(produtos_validos)


def test_receita_e_sempre_positiva_e_consistente():
    df = gerar_vendas(np.random.default_rng(42))
    assert (df["receita"] > 0).all()
    # receita deve ser preço unitário * quantidade (com arredondamento)
    esperado = (df["preco_unitario"] * df["quantidade"]).round(2)
    pd.testing.assert_series_equal(df["receita"], esperado, check_names=False)


def test_quantidade_em_faixa_valida():
    df = gerar_vendas(np.random.default_rng(42))
    assert df["quantidade"].isin([1, 2, 3]).all()


def test_fator_sazonal_alto_temporada_maior():
    import datetime as dt
    assert _fator_sazonal(dt.date(2023, 11, 15)) > _fator_sazonal(dt.date(2023, 6, 15))
    assert _fator_sazonal(dt.date(2023, 12, 15)) > _fator_sazonal(dt.date(2023, 6, 15))


def test_fatores_sazonais_calibrados_com_o_ibge():
    from gerar_dados import FATOR_SAZONAL_MES

    assert sorted(FATOR_SAZONAL_MES) == list(range(1, 13))
    assert sum(FATOR_SAZONAL_MES.values()) / 12 == pytest.approx(1.0, abs=0.005)
    assert max(FATOR_SAZONAL_MES, key=FATOR_SAZONAL_MES.get) == 12  # dezembro é o mês mais forte
    assert min(FATOR_SAZONAL_MES, key=FATOR_SAZONAL_MES.get) == 2   # fevereiro é o mais fraco
    assert FATOR_SAZONAL_MES[12] > FATOR_SAZONAL_MES[11]
