"""Cálculos do dashboard web (só pandas, sem Streamlit).

Ficam separados da interface (app.py) para poderem ser testados com pytest e
para que cada número do painel tenha uma função com nome claro. As regras
seguem as medidas DAX do Power BI (powerbi/medidas.dax), então os dois painéis
mostram os mesmos valores.
"""

from __future__ import annotations

import pandas as pd

MESES_ALTA_TEMPORADA = (11, 12)  # novembro e dezembro (Black Friday e Natal)
NOMES_MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Converte a data e cria as colunas auxiliares usadas nos filtros e gráficos."""
    df = df.copy()
    df["data"] = pd.to_datetime(df["data"])
    df["ano"] = df["data"].dt.year
    df["mes_num"] = df["data"].dt.month
    df["ano_mes"] = df["data"].dt.to_period("M").astype(str)
    return df


def filtrar(df: pd.DataFrame, anos=None, regioes=None, canais=None, categorias=None) -> pd.DataFrame:
    """Aplica os filtros da barra lateral. Lista vazia ou None = sem filtro naquela coluna."""
    mascara = pd.Series(True, index=df.index)
    for coluna, valores in [("ano", anos), ("regiao", regioes), ("canal", canais), ("categoria", categorias)]:
        if valores:
            mascara &= df[coluna].isin(valores)
    return df[mascara]


def crescimento_anual(df: pd.DataFrame) -> float | None:
    """Crescimento (%) da receita do último ano filtrado sobre o ano anterior.

    Igual à medida do Power BI: se o ano anterior não está nos dados filtrados
    (ex.: filtro só em 2023), não há com o que comparar e o resultado é None.
    """
    if df.empty:
        return None
    por_ano = df.groupby("ano")["receita"].sum()
    ultimo = por_ano.index.max()
    if ultimo - 1 not in por_ano.index or por_ano[ultimo - 1] == 0:
        return None
    return (por_ano[ultimo] / por_ano[ultimo - 1] - 1) * 100


def indicadores(df: pd.DataFrame) -> dict:
    """Cartões do topo: receita, número de vendas, ticket médio e crescimento."""
    vendas = len(df)
    receita = float(df["receita"].sum())
    return {
        "receita": receita,
        "vendas": vendas,
        "ticket_medio": receita / vendas if vendas else None,
        "crescimento_pct": crescimento_anual(df),
    }


def receita_mensal_por_ano(df: pd.DataFrame) -> pd.DataFrame:
    """Tabela mês do ano (linhas, Jan..Dez) x ano (colunas) com a receita."""
    tabela = df.pivot_table(index="mes_num", columns="ano", values="receita", aggfunc="sum")
    tabela = tabela.reindex(range(1, 13))
    tabela.index = NOMES_MESES
    return tabela


def receita_por(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Receita, número de vendas, ticket médio e % da receita agrupados por uma coluna."""
    tabela = df.groupby(coluna).agg(receita=("receita", "sum"), vendas=("receita", "size"))
    tabela["ticket_medio"] = tabela["receita"] / tabela["vendas"]
    total = tabela["receita"].sum()
    tabela["pct_receita"] = tabela["receita"] / total * 100 if total else 0.0
    return tabela.sort_values("receita", ascending=False)


def crescimento_por_categoria(df: pd.DataFrame) -> pd.Series:
    """Crescimento (%) de cada categoria do penúltimo para o último ano filtrado."""
    tabela = df.pivot_table(index="categoria", columns="ano", values="receita", aggfunc="sum")
    if tabela.shape[1] < 2:
        return pd.Series(dtype=float)
    anterior, ultimo = sorted(tabela.columns)[-2:]
    return ((tabela[ultimo] / tabela[anterior] - 1) * 100).sort_values(ascending=False)


def participacao_canal_por_ano(df: pd.DataFrame) -> pd.DataFrame:
    """Receita de cada canal por ano e o % do Online no total do ano."""
    tabela = df.pivot_table(index="ano", columns="canal", values="receita", aggfunc="sum").fillna(0)
    tabela["pct_online"] = tabela.get("Online", 0) / tabela.sum(axis=1) * 100
    return tabela


def efeito_alta_temporada(df: pd.DataFrame) -> float | None:
    """Receita média mensal de Nov/Dez dividida pela dos demais meses (ex.: 1,26x).

    Usa a média POR MÊS (soma / número de meses distintos), para que comparar
    2 meses com 10 meses seja justo.
    """
    alta = df[df["mes_num"].isin(MESES_ALTA_TEMPORADA)]
    resto = df[~df["mes_num"].isin(MESES_ALTA_TEMPORADA)]
    if alta.empty or resto.empty:
        return None
    media_alta = alta["receita"].sum() / alta["ano_mes"].nunique()
    media_resto = resto["receita"].sum() / resto["ano_mes"].nunique()
    return media_alta / media_resto if media_resto else None


def receita_media_por_mes_do_ano(df: pd.DataFrame) -> pd.Series:
    """Receita média de cada mês do ano (Jan..Dez), fazendo a média entre os anos."""
    por_mes_ano = df.groupby(["mes_num", "ano"])["receita"].sum()
    serie = por_mes_ano.groupby(level="mes_num").mean().reindex(range(1, 13))
    serie.index = NOMES_MESES
    return serie


def top_produtos(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Os n produtos com maior receita."""
    tabela = df.groupby(["produto", "categoria"]).agg(receita=("receita", "sum"), vendas=("receita", "size"))
    return tabela.sort_values("receita", ascending=False).head(n).reset_index()
