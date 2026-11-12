"""
Versão com dados REAIS: Pesquisa Mensal de Comércio (PMC) do IBGE.

Baixa da API pública do IBGE (SIDRA, tabela 8880) o índice de volume de vendas
do comércio varejista brasileiro (base 2022 = 100), mensal desde 2000, e usa a
série para responder uma pergunta que o dataset sintético deste projeto só
supõe: o efeito de Black Friday/Natal é tão forte no varejo real quanto o
gerado em `gerar_dados.py`?

Nenhum número é inventado: tudo vem da execução deste script sobre os dados
devolvidos pela API no momento da execução.

Uso:
    python src/analise_ibge.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")  # não precisa de display gráfico para salvar PNGs

import matplotlib.pyplot as plt
import pandas as pd
import requests

from gerar_dados import _fator_sazonal

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_IBGE = BASE_DIR / "data" / "ibge_pmc.csv"
IMGS_DIR = BASE_DIR / "imgs"

# Tabela 8880: índice de receita nominal e de volume de vendas no varejo (2022 = 100).
# v/7169 = número-índice; v/7170 = número-índice com ajuste sazonal.
# c11046/56734 = índice de volume de vendas; n1/all = Brasil.
URL_PMC = "https://apisidra.ibge.gov.br/values/t/8880/n1/all/v/7169,7170/p/all/c11046/56734"
TIMEOUT = 60
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

plt.rcParams["figure.dpi"] = 110
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False


def baixar_pmc(sessao: Optional[requests.Session] = None) -> list[dict]:
    """Baixa os registros brutos (JSON) da API SIDRA."""
    sessao = sessao or requests.Session()
    resposta = sessao.get(URL_PMC, timeout=TIMEOUT)
    resposta.raise_for_status()
    resposta.encoding = "utf-8"
    return resposta.json()


def parse_pmc(registros: list[dict]) -> pd.DataFrame:
    """Converte o JSON da SIDRA em DataFrame: periodo, indice, indice_dessaz.

    O primeiro elemento da resposta é um cabeçalho descritivo e é ignorado.
    """
    linhas = []
    for r in registros[1:]:
        linhas.append(
            {
                "periodo": pd.to_datetime(r["D3C"], format="%Y%m"),
                "variavel": r["D2C"],
                "valor": float(r["V"]),
            }
        )
    if not linhas:
        raise ValueError("A resposta da API não trouxe dados.")
    tabela = pd.DataFrame(linhas).pivot(index="periodo", columns="variavel", values="valor")
    tabela = tabela.rename(columns={"7169": "indice", "7170": "indice_dessaz"})
    return tabela.reset_index().sort_values("periodo").reset_index(drop=True)


def fator_sazonal_mensal(df: pd.DataFrame, ano_inicial: int, ano_final: int) -> pd.Series:
    """Fator sazonal médio por mês do ano (índice 1..12), normalizado para média 1.

    Razão entre o índice original e o dessazonalizado em cada mês, média por mês
    no intervalo de anos pedido. Valor > 1 = mês tipicamente acima da média anual.
    """
    d = df.dropna(subset=["indice", "indice_dessaz"]).copy()
    d = d[(d["periodo"].dt.year >= ano_inicial) & (d["periodo"].dt.year <= ano_final)]
    if d.empty:
        raise ValueError("Sem dados no intervalo de anos pedido.")
    razao = (d["indice"] / d["indice_dessaz"]).groupby(d["periodo"].dt.month).mean()
    return razao / razao.mean()


def fator_sazonal_sintetico() -> pd.Series:
    """Multiplicador de demanda mensal usado em gerar_dados.py, normalizado para média 1."""
    bruto = pd.Series({m: _fator_sazonal(dt.date(2023, m, 1)) for m in range(1, 13)})
    return bruto / bruto.mean()


def efeito_fim_de_ano(fatores: pd.Series) -> float:
    """Média de nov/dez dividida pela média dos outros 10 meses."""
    fim = fatores.loc[[11, 12]].mean()
    resto = fatores.drop([11, 12]).mean()
    return float(fim / resto)


def variacao_anual(df: pd.DataFrame, ano: int) -> float:
    """Variação (%) da média do índice original em `ano` sobre a média de `ano - 1`."""
    medias = df.groupby(df["periodo"].dt.year)["indice"].mean()
    return float((medias[ano] / medias[ano - 1] - 1) * 100)


def resumo(df: pd.DataFrame, ano_inicial: int = 2014, ano_final: int = 2025) -> dict:
    ultimo = df.dropna(subset=["indice_dessaz"]).iloc[-1]
    dessaz = df.set_index("periodo")["indice_dessaz"]
    pico = dessaz.idxmax()
    real = fator_sazonal_mensal(df, ano_inicial, ano_final)
    sint = fator_sazonal_sintetico()
    return {
        "primeiro_mes": df["periodo"].iloc[0],
        "ultimo_mes": ultimo["periodo"],
        "meses": len(df),
        "indice_atual_dessaz": float(ultimo["indice_dessaz"]),
        "pico_dessaz": float(dessaz.max()),
        "pico_mes": pico,
        "queda_covid_pct": float((dessaz["2020-04-01"] / dessaz["2020-02-01"] - 1) * 100),
        "var_2023": variacao_anual(df, 2023),
        "var_2024": variacao_anual(df, 2024),
        "var_2025": variacao_anual(df, 2025),
        "fator_real": real,
        "fator_sintetico": sint,
        "efeito_real": efeito_fim_de_ano(real),
        "efeito_sintetico": efeito_fim_de_ano(sint),
        "ano_inicial": ano_inicial,
        "ano_final": ano_final,
    }


def grafico_serie(df: pd.DataFrame) -> Path:
    d = df[df["periodo"] >= "2012-01-01"]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(d["periodo"], d["indice"], color="#93c5fd", linewidth=1.4, label="Índice original")
    ax.plot(d["periodo"], d["indice_dessaz"], color="#2563eb", linewidth=2.2, label="Com ajuste sazonal")
    ax.axhline(100, color="#9ca3af", linewidth=1, linestyle="--")
    ax.set_title("Volume de vendas do varejo brasileiro — IBGE/PMC (2022 = 100)")
    ax.set_ylabel("Número-índice")
    ax.legend(frameon=False)
    fig.tight_layout()
    IMGS_DIR.mkdir(exist_ok=True)
    caminho = IMGS_DIR / "ibge_serie.png"
    fig.savefig(caminho)
    plt.close(fig)
    return caminho


def grafico_sazonalidade(real: pd.Series, sintetico: pd.Series, anos: tuple[int, int]) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    largura = 0.4
    x = range(12)
    ax.bar([i - largura / 2 for i in x], real.values, largura, color="#2563eb", label=f"Real (IBGE, {anos[0]}-{anos[1]})")
    ax.bar([i + largura / 2 for i in x], sintetico.values, largura, color="#f59e0b", label="Sintético (gerar_dados.py)")
    ax.axhline(1, color="#9ca3af", linewidth=1, linestyle="--")
    ax.set_xticks(list(x))
    ax.set_xticklabels(MESES)
    ax.set_ylabel("Fator sazonal (média anual = 1)")
    ax.set_title("Sazonalidade mensal: varejo real x dados sintéticos")
    ax.legend(frameon=False)
    fig.tight_layout()
    IMGS_DIR.mkdir(exist_ok=True)
    caminho = IMGS_DIR / "ibge_sazonalidade.png"
    fig.savefig(caminho)
    plt.close(fig)
    return caminho


def imprimir_resumo(r: dict) -> None:
    def mes(ts: pd.Timestamp) -> str:
        return f"{MESES[ts.month - 1].lower()}/{ts.year}"

    print("=" * 60)
    print("PMC/IBGE — volume de vendas do varejo (2022 = 100)")
    print("=" * 60)
    print(f"Período: {mes(r['primeiro_mes'])} a {mes(r['ultimo_mes'])} ({r['meses']} meses)")
    print(f"Índice atual (com ajuste sazonal): {r['indice_atual_dessaz']:.1f} em {mes(r['ultimo_mes'])}")
    print(f"Pico histórico (com ajuste sazonal): {r['pico_dessaz']:.1f} em {mes(r['pico_mes'])}")
    print(f"Queda na pandemia (fev -> abr/2020): {r['queda_covid_pct']:.1f}%")
    for ano in (2023, 2024, 2025):
        print(f"Variação da média anual em {ano}: {r['var_' + str(ano)]:+.1f}%")
    print()
    print(f"Fator sazonal por mês ({r['ano_inicial']}-{r['ano_final']}, média = 1):")
    print(f"{'mês':<5}{'real':>8}{'sintético':>12}")
    for m in range(1, 13):
        print(f"{MESES[m - 1]:<5}{r['fator_real'][m]:>8.3f}{r['fator_sintetico'][m]:>12.3f}")
    print()
    print(f"Efeito nov/dez sobre os demais meses — real: {r['efeito_real']:.2f}x | sintético: {r['efeito_sintetico']:.2f}x")


def main() -> None:
    print("Baixando série da API do IBGE (SIDRA, tabela 8880)...")
    df = parse_pmc(baixar_pmc())
    CSV_IBGE.parent.mkdir(exist_ok=True)
    df.to_csv(CSV_IBGE, index=False)
    print(f"{len(df)} meses salvos em {CSV_IBGE}")
    r = resumo(df)
    imprimir_resumo(r)
    grafico_serie(df)
    grafico_sazonalidade(r["fator_real"], r["fator_sintetico"], (r["ano_inicial"], r["ano_final"]))
    print("\nGráficos salvos em imgs/ibge_serie.png e imgs/ibge_sazonalidade.png")


if __name__ == "__main__":
    main()
