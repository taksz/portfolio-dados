import pandas as pd

from analise import calcular_metricas


def df_exemplo() -> pd.DataFrame:
    dados = [
        # ano, mes, categoria, regiao, canal, receita
        ("2023-06-01", "Eletrônicos", "Sudeste", "Online", 1000.0),
        ("2023-11-15", "Eletrônicos", "Sudeste", "Online", 3000.0),
        ("2023-12-10", "Moda", "Sul", "Loja Física", 500.0),
        ("2024-06-01", "Eletrônicos", "Sudeste", "Online", 1200.0),
        ("2024-11-20", "Moda", "Sul", "Online", 800.0),
    ]
    df = pd.DataFrame(dados, columns=["data", "categoria", "regiao", "canal", "receita"])
    df["data"] = pd.to_datetime(df["data"])
    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.to_period("M").astype(str)
    return df


def test_total_vendas_e_receita_total():
    m = calcular_metricas(df_exemplo())
    assert m["total_vendas"] == 5
    assert m["receita_total"] == 1000 + 3000 + 500 + 1200 + 800


def test_categoria_top():
    m = calcular_metricas(df_exemplo())
    assert m["categoria_top"] == "Eletrônicos"


def test_regiao_top():
    m = calcular_metricas(df_exemplo())
    assert m["regiao_top"] == "Sudeste"


def test_crescimento_yoy():
    m = calcular_metricas(df_exemplo())
    receita_2023 = 1000 + 3000 + 500
    receita_2024 = 1200 + 800
    esperado = (receita_2024 / receita_2023 - 1) * 100
    assert m["crescimento_yoy_pct"] == esperado


def test_alta_temporada_maior_que_resto():
    m = calcular_metricas(df_exemplo())
    assert m["media_mensal_alta_temporada"] > 0
    # As vendas de alta temporada caem em 3 meses-calendário distintos:
    # 2023-11, 2023-12 e 2024-11, somando 3000 + 500 + 800 = 4300.
    assert m["media_mensal_alta_temporada"] == (3000 + 500 + 800) / 3
