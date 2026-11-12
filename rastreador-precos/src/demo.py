"""Gera um histórico SIMULADO (apenas para demonstrar gráfico/resumo).

O books.toscrape.com é um site estático: os preços nunca mudam. Para mostrar como
a análise se comporta quando há variação, este módulo cria um banco SEPARADO
(demo.db) com 10 snapshots semanais derivados dos preços reais coletados,
aplicando variações pseudoaleatórias com semente fixa. Os dados são simulados
e NÃO devem ser confundidos com o histórico real (precos.db).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import banco
from scraper import Produto


def gerar_historico_simulado(
    base: list[Produto], destino: Path | str, snapshots: int = 10, semente: int = 42, inicio: datetime | None = None
) -> int:
    rng = random.Random(semente)
    inicio = inicio or datetime(2026, 9, 1, 12, 0, 0)
    conn = banco.conectar(destino)
    atuais = {p.id: p.preco for p in base}
    try:
        for i in range(snapshots):
            produtos = []
            for p in base:
                if i > 0:
                    fator = 1 + rng.choice([0, 0, 0, -0.15, -0.08, 0.05, 0.10])
                    atuais[p.id] = round(max(1.0, atuais[p.id] * fator), 2)
                produtos.append(Produto(p.id, p.nome, atuais[p.id], p.disponivel, p.url))
            banco.salvar_snapshot(conn, produtos, inicio + timedelta(weeks=i))
    finally:
        conn.close()
    return snapshots * len(base)
