"""
Gera um dataset sintético, porém realista, de vendas de um e-commerce
fictício ao longo de 2 anos (2023 e 2024). Os dados são gerados com uma
semente fixa (seed), então rodar este script sempre produz exatamente
o mesmo arquivo — importante para que a análise seja reprodutível.

Por que dados sintéticos? Para um projeto de portfólio público, gerar os
próprios dados (em vez de baixar um dataset real de terceiros) evita
problemas de licença/privacidade. A sazonalidade mensal (Black Friday, Natal)
é calibrada com dados reais do IBGE (veja FATOR_SAZONAL_MES).

Uso:
    python src/gerar_dados.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
DATA_INICIO = dt.date(2023, 1, 1)
DATA_FIM = dt.date(2024, 12, 31)

# categoria -> (produtos, faixa de preço unitário em R$)
CATALOGO = {
    "Eletrônicos": (["Fone de Ouvido", "Smartphone", "Carregador", "Smartwatch"], (50, 3500)),
    "Moda": (["Camiseta", "Tênis", "Jaqueta", "Boné"], (30, 450)),
    "Casa": (["Panela", "Luminária", "Cortina", "Tapete"], (25, 600)),
    "Livros": (["Romance", "Técnico", "Infantil", "Quadrinho"], (20, 150)),
    "Esporte": (["Bola", "Bicicleta", "Tapete de Yoga", "Halteres"], (15, 2200)),
}

REGIOES = ["Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte"]
# pesos aproximados de participação populacional/econômica das regiões
PESOS_REGIOES = [0.45, 0.18, 0.22, 0.09, 0.06]

CANAIS = ["Online", "Loja Física"]

# Fator sazonal médio por mês (média anual = 1), calculado pela razão entre o índice de
# volume de vendas do varejo brasileiro e o mesmo índice com ajuste sazonal, média de
# 2014 a 2025. Fonte: IBGE, Pesquisa Mensal de Comércio (SIDRA, tabela 8880), obtido
# com `python src/analise_ibge.py`. Os valores ficam fixos aqui para a geração dos dados
# continuar offline e reprodutível; rode a análise do IBGE para conferir ou atualizar.
FATOR_SAZONAL_MES = {
    1: 0.971, 2: 0.900, 3: 0.979, 4: 0.952, 5: 0.987, 6: 0.957,
    7: 0.987, 8: 0.994, 9: 0.958, 10: 1.003, 11: 1.054, 12: 1.257,
}


def _fator_sazonal(data: dt.date) -> float:
    """Multiplicador de demanda por mês, calibrado com a sazonalidade REAL do varejo.

    Veja FATOR_SAZONAL_MES: dezembro é o mês mais forte, novembro vem em seguida e
    fevereiro é o mais fraco. Antes da recalibração este valor era escolhido à mão
    (novembro 2,2; dezembro 1,8; janeiro/fevereiro 0,75), o que exagerava o efeito.
    """
    return FATOR_SAZONAL_MES[data.month]


def _fator_crescimento(data: dt.date) -> float:
    """Leve tendência de crescimento ano a ano (2024 vende mais que 2023)."""
    dias_desde_inicio = (data - DATA_INICIO).days
    total_dias = (DATA_FIM - DATA_INICIO).days
    return 1.0 + 0.3 * (dias_desde_inicio / total_dias)


def gerar_vendas(rng: np.random.Generator) -> pd.DataFrame:
    linhas = []
    id_venda = 1
    data_atual = DATA_INICIO

    while data_atual <= DATA_FIM:
        fator = _fator_sazonal(data_atual) * _fator_crescimento(data_atual)
        # número-base de vendas no dia, variando com o fator sazonal/crescimento
        n_vendas_dia = rng.poisson(lam=8 * fator)

        for _ in range(n_vendas_dia):
            categoria = rng.choice(list(CATALOGO.keys()))
            produtos, (preco_min, preco_max) = CATALOGO[categoria]
            produto = rng.choice(produtos)

            # distribuição log-normal truncada para preços (mais realista que uniforme)
            preco_unitario = float(
                np.clip(rng.lognormal(mean=np.log((preco_min + preco_max) / 3), sigma=0.5),
                        preco_min, preco_max)
            )
            preco_unitario = round(preco_unitario, 2)

            quantidade = int(rng.choice([1, 1, 1, 2, 2, 3], p=[0.45, 0.2, 0.15, 0.1, 0.05, 0.05]))
            regiao = rng.choice(REGIOES, p=PESOS_REGIOES)

            # canal online cresce de participação ao longo do tempo
            prop_online = 0.5 + 0.2 * ((data_atual - DATA_INICIO).days / (DATA_FIM - DATA_INICIO).days)
            canal = rng.choice(CANAIS, p=[prop_online, 1 - prop_online])

            receita = round(preco_unitario * quantidade, 2)

            linhas.append({
                "id_venda": id_venda,
                "data": data_atual.isoformat(),
                "categoria": categoria,
                "produto": produto,
                "quantidade": quantidade,
                "preco_unitario": preco_unitario,
                "receita": receita,
                "regiao": regiao,
                "canal": canal,
            })
            id_venda += 1

        data_atual += dt.timedelta(days=1)

    return pd.DataFrame(linhas)


def main() -> None:
    rng = np.random.default_rng(SEED)
    df = gerar_vendas(rng)

    saida_dir = Path(__file__).resolve().parent.parent / "data"
    saida_dir.mkdir(exist_ok=True)
    caminho_saida = saida_dir / "vendas.csv"
    df.to_csv(caminho_saida, index=False, encoding="utf-8")

    print(f"{len(df)} registros de venda gerados em {caminho_saida}")
    print(f"Período: {df['data'].min()} a {df['data'].max()}")
    print(f"Receita total: R$ {df['receita'].sum():,.2f}")


if __name__ == "__main__":
    main()
