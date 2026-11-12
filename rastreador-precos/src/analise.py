"""Análise do histórico: resumo estatístico e gráfico da evolução de preço de um produto."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import matplotlib

matplotlib.use("Agg")  # backend sem janela: funciona em servidor/cron
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from datetime import datetime


def resumir(pontos: Sequence[tuple[str, float]]) -> dict:
    """Resumo de uma série [(data_iso, preco), ...] já ordenada por data.

    Maior queda = maior redução de preço entre duas coletas consecutivas.
    """
    if not pontos:
        raise ValueError("Histórico vazio")
    datas = [p[0] for p in pontos]
    precos = [p[1] for p in pontos]

    i_min = precos.index(min(precos))
    i_max = precos.index(max(precos))

    maior_queda = {"valor": 0.0, "percentual": 0.0, "de": None, "para": None, "em": None}
    for i in range(1, len(precos)):
        queda = precos[i - 1] - precos[i]
        if queda > maior_queda["valor"]:
            maior_queda = {
                "valor": round(queda, 2),
                "percentual": round(queda / precos[i - 1] * 100, 1),
                "de": precos[i - 1],
                "para": precos[i],
                "em": datas[i],
            }

    return {
        "coletas": len(pontos),
        "primeira_coleta": datas[0],
        "ultima_coleta": datas[-1],
        "preco_inicial": precos[0],
        "preco_atual": precos[-1],
        "variacao_total": round(precos[-1] - precos[0], 2),
        "menor_preco": precos[i_min],
        "menor_preco_em": datas[i_min],
        "maior_preco": precos[i_max],
        "maior_preco_em": datas[i_max],
        "preco_medio": round(sum(precos) / len(precos), 2),
        "maior_queda": maior_queda,
    }


def formatar_resumo(nome: str, r: dict) -> str:
    q = r["maior_queda"]
    queda = (
        f"-£{q['valor']:.2f} ({q['percentual']}%) — de £{q['de']:.2f} para £{q['para']:.2f} em {q['em']}"
        if q["em"]
        else "nenhuma queda registrada"
    )
    return "\n".join(
        [
            f"Produto: {nome}",
            f"Coletas: {r['coletas']} ({r['primeira_coleta']} → {r['ultima_coleta']})",
            f"Preço atual: £{r['preco_atual']:.2f} (inicial £{r['preco_inicial']:.2f}, variação {r['variacao_total']:+.2f})",
            f"Menor preço visto: £{r['menor_preco']:.2f} em {r['menor_preco_em']}",
            f"Maior preço visto: £{r['maior_preco']:.2f} em {r['maior_preco_em']}",
            f"Preço médio: £{r['preco_medio']:.2f}",
            f"Maior queda: {queda}",
        ]
    )


def gerar_grafico(
    nome: str,
    pontos: Sequence[tuple[str, float]],
    saida: Path | str,
    limite: Optional[float] = None,
) -> Path:
    """Salva um PNG com a evolução do preço (e a linha do limite de alerta, se houver)."""
    datas = [datetime.fromisoformat(d) for d, _ in pontos]
    precos = [p for _, p in pontos]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(datas, precos, marker="o", color="#1f77b4", linewidth=2, label="Preço")
    if limite is not None:
        ax.axhline(limite, color="#d62728", linestyle="--", label=f"Limite de alerta (£{limite:.2f})")
    ax.set_title(f"Evolução de preço — {nome}")
    ax.set_ylabel("Preço (£)")
    ax.grid(alpha=0.3)
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
    fig.autofmt_xdate()
    fig.tight_layout()
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(saida, dpi=130)
    plt.close(fig)
    return saida
