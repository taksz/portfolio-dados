"""
Prepara os dados de vendas para o Power BI em modelo estrela.

Lê data/vendas.csv e grava em data/powerbi/ uma tabela fato e quatro dimensões:

    fato_vendas      uma linha por venda, com chaves para as dimensões
    dim_calendario   uma linha por dia do período (inclui flag de alta temporada)
    dim_produto      produto e categoria
    dim_regiao       região
    dim_canal        canal de venda

Modelo estrela (em vez de importar o CSV "achatado") deixa as medidas DAX mais
simples e permite usar funções de inteligência de tempo (comparar com o ano
anterior), que exigem uma tabela de calendário contínua.

Uso:
    python src/exportar_powerbi.py                  # CSV no formato brasileiro (; e vírgula)
    python src/exportar_powerbi.py --formato us     # CSV no formato americano (, e ponto)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "vendas.csv"
SAIDA_DIR = BASE_DIR / "data" / "powerbi"

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]
COLUNAS = {"id_venda", "data", "categoria", "produto", "quantidade",
           "preco_unitario", "receita", "regiao", "canal"}


def _dimensao(valores: pd.Series, nome_id: str, nome: str) -> pd.DataFrame:
    """Dimensão simples: valores únicos ordenados, com chave numérica a partir de 1."""
    unicos = sorted(valores.unique())
    return pd.DataFrame({nome_id: range(1, len(unicos) + 1), nome: unicos})


def construir_calendario(inicio: pd.Timestamp, fim: pd.Timestamp) -> pd.DataFrame:
    """Calendário contínuo (um dia por linha) do primeiro ao último dia informado."""
    datas = pd.date_range(inicio, fim, freq="D")
    cal = pd.DataFrame({"data": datas})
    cal["ano"] = cal["data"].dt.year
    cal["trimestre"] = "T" + cal["data"].dt.quarter.astype(str)
    cal["mes_num"] = cal["data"].dt.month
    cal["mes_nome"] = cal["mes_num"].map(lambda m: MESES[m - 1])
    cal["ano_mes"] = cal["data"].dt.strftime("%Y-%m")
    cal["dia_semana_num"] = cal["data"].dt.day_of_week + 1  # 1 = segunda
    cal["dia_semana"] = cal["data"].dt.day_of_week.map(lambda d: DIAS[d])
    cal["alta_temporada"] = cal["mes_num"].map(lambda m: "Sim" if m in (11, 12) else "Não")
    return cal


def construir_modelo(vendas: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Devolve {nome_da_tabela: DataFrame} do modelo estrela a partir das vendas."""
    faltando = COLUNAS - set(vendas.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes em vendas.csv: {sorted(faltando)}")

    vendas = vendas.copy()
    vendas["data"] = pd.to_datetime(vendas["data"])

    dim_produto = (
        vendas[["produto", "categoria"]].drop_duplicates().sort_values(["categoria", "produto"]).reset_index(drop=True)
    )
    dim_produto.insert(0, "id_produto", range(1, len(dim_produto) + 1))
    dim_regiao = _dimensao(vendas["regiao"], "id_regiao", "regiao")
    dim_canal = _dimensao(vendas["canal"], "id_canal", "canal")
    dim_calendario = construir_calendario(vendas["data"].min(), vendas["data"].max())

    fato = (
        vendas.merge(dim_produto, on=["produto", "categoria"], how="left")
        .merge(dim_regiao, on="regiao", how="left")
        .merge(dim_canal, on="canal", how="left")
    )[["id_venda", "data", "id_produto", "id_regiao", "id_canal", "quantidade", "preco_unitario", "receita"]]

    return {
        "fato_vendas": fato.sort_values("id_venda").reset_index(drop=True),
        "dim_calendario": dim_calendario,
        "dim_produto": dim_produto,
        "dim_regiao": dim_regiao,
        "dim_canal": dim_canal,
    }


def gravar_modelo(modelo: dict[str, pd.DataFrame], destino: Path, formato: str = "ptbr") -> list[Path]:
    """Grava cada tabela em CSV. `ptbr` usa ';' e vírgula decimal; `us` usa ',' e ponto."""
    if formato not in ("ptbr", "us"):
        raise ValueError("formato deve ser 'ptbr' ou 'us'")
    sep, decimal = (";", ",") if formato == "ptbr" else (",", ".")
    destino.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for nome, tabela in modelo.items():
        t = tabela.copy()
        for col in t.select_dtypes(include="datetime64[ns]").columns:
            t[col] = t[col].dt.strftime("%Y-%m-%d")
        caminho = destino / f"{nome}.csv"
        # utf-8-sig: o Power BI reconhece os acentos sem ajuste manual de codificação
        t.to_csv(caminho, index=False, sep=sep, decimal=decimal, encoding="utf-8-sig")
        caminhos.append(caminho)
    return caminhos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--formato", choices=["ptbr", "us"], default="ptbr",
                        help="ptbr: ';' e vírgula decimal (padrão) | us: ',' e ponto decimal")
    args = parser.parse_args()

    modelo = construir_modelo(pd.read_csv(CSV_PATH))
    caminhos = gravar_modelo(modelo, SAIDA_DIR, args.formato)
    print(f"Modelo estrela gravado em {SAIDA_DIR} (formato {args.formato}):")
    for nome, caminho in zip(modelo, caminhos):
        print(f"  {caminho.name:<20} {len(modelo[nome]):>6} linhas")


if __name__ == "__main__":
    main()
