"""Persistência em SQLite: produtos e histórico de preços (um snapshot por coleta)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from scraper import Produto

DB_PADRAO = Path(__file__).resolve().parent.parent / "precos.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS produtos (
    id   TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    url  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS historico_precos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id  TEXT NOT NULL REFERENCES produtos(id),
    preco       REAL NOT NULL,
    disponivel  INTEGER NOT NULL,
    coletado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_historico_produto ON historico_precos(produto_id, coletado_em);
"""


def conectar(caminho: Path | str = DB_PADRAO) -> sqlite3.Connection:
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def preco_anterior(conn: sqlite3.Connection, produto_id: str) -> Optional[float]:
    """Último preço registrado do produto (None se nunca foi coletado)."""
    linha = conn.execute(
        "SELECT preco FROM historico_precos WHERE produto_id = ? ORDER BY coletado_em DESC, id DESC LIMIT 1",
        (produto_id,),
    ).fetchone()
    return linha["preco"] if linha else None


def salvar_snapshot(conn: sqlite3.Connection, produtos: Iterable[Produto], coletado_em: Optional[datetime] = None) -> int:
    """Registra um snapshot de preços. Retorna quantos produtos foram gravados."""
    momento = (coletado_em or datetime.now()).isoformat(timespec="seconds")
    total = 0
    with conn:
        for p in produtos:
            conn.execute(
                "INSERT INTO produtos (id, nome, url) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET nome = excluded.nome, url = excluded.url",
                (p.id, p.nome, p.url),
            )
            conn.execute(
                "INSERT INTO historico_precos (produto_id, preco, disponivel, coletado_em) VALUES (?, ?, ?, ?)",
                (p.id, p.preco, int(p.disponivel), momento),
            )
            total += 1
    return total


def historico(conn: sqlite3.Connection, produto_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT preco, disponivel, coletado_em FROM historico_precos WHERE produto_id = ? ORDER BY coletado_em, id",
        (produto_id,),
    ).fetchall()


def buscar_produto(conn: sqlite3.Connection, termo: str) -> Optional[sqlite3.Row]:
    """Encontra um produto pelo id exato ou por parte do nome (case-insensitive)."""
    linha = conn.execute("SELECT * FROM produtos WHERE id = ?", (termo,)).fetchone()
    if linha:
        return linha
    return conn.execute(
        "SELECT * FROM produtos WHERE nome LIKE ? ORDER BY nome LIMIT 1", (f"%{termo}%",)
    ).fetchone()


def listar_produtos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Cada produto com o último preço registrado."""
    return conn.execute(
        """
        SELECT p.id, p.nome, h.preco, h.disponivel, h.coletado_em
        FROM produtos p
        JOIN historico_precos h ON h.id = (
            SELECT id FROM historico_precos WHERE produto_id = p.id ORDER BY coletado_em DESC, id DESC LIMIT 1
        )
        ORDER BY p.nome
        """
    ).fetchall()
