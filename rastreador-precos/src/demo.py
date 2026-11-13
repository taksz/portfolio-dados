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

import alertas
import banco
import scraper
from scraper import Produto

# Os 20 produtos reais da 1ª página do catálogo, salvos em HTML (usados também pelos testes).
CATALOGO_OFFLINE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "catalogo_pagina1.html"


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


def base_offline() -> list[Produto]:
    """Produtos reais do catálogo lidos do HTML salvo: funciona sem internet."""
    produtos, _ = scraper.parse_catalogo(CATALOGO_OFFLINE.read_text(encoding="utf-8"))
    return produtos


def preparar_demonstracao(db: Path | str, arquivo_alertas: Path | str, limite: float | None = None) -> bool:
    """Cria histórico SIMULADO (e alertas de exemplo) se o banco estiver vazio.

    Serve para uma hospedagem pública abrir sempre com dados, já que o disco do plano
    grátis é apagado a cada reinício. Devolve True se criou, False se já havia dados.
    """
    conn = banco.conectar(db)
    try:
        vazio = not banco.listar_produtos(conn)
    finally:
        conn.close()
    if not vazio:
        return False

    gerar_historico_simulado(base_offline(), db)

    if limite is not None:
        conn = banco.conectar(db)
        try:
            produtos, anteriores = [], {}
            for p in banco.listar_com_resumo(conn):
                historico = banco.historico(conn, p["id"])
                anteriores[p["id"]] = historico[-2]["preco"] if len(historico) > 1 else None
                produtos.append(Produto(p["id"], p["nome"], p["preco"], bool(p["disponivel"]), ""))
        finally:
            conn.close()
        alertas.registrar(alertas.verificar(produtos, limite, anteriores), arquivo_alertas)
    return True
