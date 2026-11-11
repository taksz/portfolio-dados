"""
Análise exploratória dos dados de vendas com pandas + matplotlib.

Lê data/vendas.csv, calcula métricas de negócio e salva os gráficos em
imgs/. Também imprime um resumo no terminal, que é a fonte dos números
citados no relatorio.md deste projeto (nenhum número é inventado — todos
vêm da execução deste script sobre os dados gerados por gerar_dados.py).

Uso:
    python src/analise.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # não precisa de display gráfico para salvar PNGs

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "vendas.csv"
IMGS_DIR = BASE_DIR / "imgs"

plt.rcParams["figure.dpi"] = 110
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False


def carregar_dados() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, parse_dates=["data"])
    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.to_period("M").astype(str)
    return df


def grafico_receita_mensal(df: pd.DataFrame) -> None:
    receita_mensal = df.groupby("mes")["receita"].sum()

    fig, ax = plt.subplots(figsize=(10, 4.5))
    receita_mensal.plot(ax=ax, marker="o", linewidth=2, color="#2563eb")
    ax.set_title("Receita mensal (2023-2024)")
    ax.set_xlabel("Mês")
    ax.set_ylabel("Receita (R$)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}k"))
    ax.tick_params(axis="x", rotation=90)
    fig.tight_layout()
    fig.savefig(IMGS_DIR / "receita_mensal.png")
    plt.close(fig)


def grafico_receita_por_categoria(df: pd.DataFrame) -> None:
    receita_cat = df.groupby("categoria")["receita"].sum().sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    receita_cat.plot(kind="barh", ax=ax, color="#059669")
    ax.set_title("Receita total por categoria")
    ax.set_xlabel("Receita (R$)")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}k"))
    fig.tight_layout()
    fig.savefig(IMGS_DIR / "receita_por_categoria.png")
    plt.close(fig)


def grafico_receita_por_regiao(df: pd.DataFrame) -> None:
    receita_regiao = df.groupby("regiao")["receita"].sum().sort_values(ascending=False)

    fig, ax = plt.subplots(figsize=(7, 5))
    cores = ["#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed"]
    ax.pie(
        receita_regiao.values,
        labels=receita_regiao.index,
        autopct="%1.1f%%",
        colors=cores,
        startangle=90,
    )
    ax.set_title("Participação de cada região na receita total")
    fig.tight_layout()
    fig.savefig(IMGS_DIR / "receita_por_regiao.png")
    plt.close(fig)


def grafico_canal_por_ano(df: pd.DataFrame) -> None:
    pivot = df.groupby(["ano", "canal"])["receita"].sum().unstack("canal")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    pivot.plot(kind="bar", ax=ax, color=["#2563eb", "#9ca3af"])
    ax.set_title("Receita por canal de venda, por ano")
    ax.set_xlabel("Ano")
    ax.set_ylabel("Receita (R$)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}k"))
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(IMGS_DIR / "receita_por_canal.png")
    plt.close(fig)


def calcular_metricas(df: pd.DataFrame) -> dict:
    """Calcula as métricas de negócio usadas no resumo e no relatório.

    Mantida separada de `imprimir_resumo` para poder ser testada com
    pytest sem depender de captura de stdout.
    """
    receita_total = df["receita"].sum()
    receita_por_ano = df.groupby("ano")["receita"].sum()

    anos = sorted(receita_por_ano.index)
    crescimento_yoy = None
    if len(anos) >= 2 and receita_por_ano[anos[0]] > 0:
        crescimento_yoy = (receita_por_ano[anos[-1]] / receita_por_ano[anos[0]] - 1) * 100

    receita_cat = df.groupby("categoria")["receita"].sum().sort_values(ascending=False)
    receita_regiao = df.groupby("regiao")["receita"].sum().sort_values(ascending=False)

    alta_temporada = df[df["data"].dt.month.isin([11, 12])]
    resto = df[~df["data"].dt.month.isin([11, 12])]
    meses_alta = alta_temporada["mes"].nunique() or 1
    meses_resto = resto["mes"].nunique() or 1
    media_mensal_alta = alta_temporada["receita"].sum() / meses_alta
    media_mensal_resto = resto["receita"].sum() / meses_resto if resto["receita"].sum() else 0

    ultimo_ano = anos[-1]
    canal_ultimo_ano = df[df["ano"] == ultimo_ano].groupby("canal")["receita"].sum()
    pct_online_ultimo_ano = (
        canal_ultimo_ano.get("Online", 0) / canal_ultimo_ano.sum() * 100
        if canal_ultimo_ano.sum() else None
    )

    return {
        "total_vendas": len(df),
        "receita_total": receita_total,
        "receita_por_ano": receita_por_ano.to_dict(),
        "crescimento_yoy_pct": crescimento_yoy,
        "categoria_top": receita_cat.index[0],
        "categoria_top_pct": receita_cat.iloc[0] / receita_total * 100 if receita_total else None,
        "regiao_top": receita_regiao.index[0],
        "regiao_top_receita": receita_regiao.iloc[0],
        "media_mensal_alta_temporada": media_mensal_alta,
        "media_mensal_resto": media_mensal_resto,
        "pct_online_ultimo_ano": pct_online_ultimo_ano,
    }


def imprimir_resumo(df: pd.DataFrame) -> None:
    m = calcular_metricas(df)
    anos = sorted(m["receita_por_ano"].keys())

    print("=" * 60)
    print("RESUMO DA ANÁLISE")
    print("=" * 60)
    print(f"Total de vendas: {m['total_vendas']}")
    print(f"Receita total: R$ {m['receita_total']:,.2f}")
    for ano in anos:
        print(f"Receita {ano}: R$ {m['receita_por_ano'][ano]:,.2f}")
    if m["crescimento_yoy_pct"] is not None:
        print(f"Crescimento {anos[0]} -> {anos[-1]}: {m['crescimento_yoy_pct']:.1f}%")
    print(f"Categoria líder: {m['categoria_top']} ({m['categoria_top_pct']:.1f}% da receita total)")
    print(f"Região líder: {m['regiao_top']} (R$ {m['regiao_top_receita']:,.2f})")
    print(
        f"Receita média mensal em Nov/Dez: R$ {m['media_mensal_alta_temporada']:,.2f} "
        f"vs. R$ {m['media_mensal_resto']:,.2f} nos demais meses "
        f"({m['media_mensal_alta_temporada'] / m['media_mensal_resto']:.2f}x maior)"
    )
    if m["pct_online_ultimo_ano"] is not None:
        print(f"Participação do canal Online na receita de {anos[-1]}: {m['pct_online_ultimo_ano']:.1f}%")


def main() -> None:
    IMGS_DIR.mkdir(exist_ok=True)
    df = carregar_dados()

    grafico_receita_mensal(df)
    grafico_receita_por_categoria(df)
    grafico_receita_por_regiao(df)
    grafico_canal_por_ano(df)
    imprimir_resumo(df)

    print(f"\nGráficos salvos em {IMGS_DIR}/")


if __name__ == "__main__":
    main()
