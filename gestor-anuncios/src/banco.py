"""Persistência em SQLite: veículos (pela placa), anúncios por plataforma e snapshots por coleta."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from modelos import AnuncioColetado, normalizar_placa

DB_PADRAO = Path(__file__).resolve().parent.parent / "anuncios.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS veiculos (
    placa            TEXT PRIMARY KEY,
    marca            TEXT NOT NULL,
    modelo           TEXT NOT NULL,
    versao           TEXT NOT NULL,
    ano              INTEGER NOT NULL,
    km               INTEGER NOT NULL,
    preco_referencia REAL
);
CREATE TABLE IF NOT EXISTS anuncios (
    plataforma   TEXT NOT NULL,
    anuncio_id   TEXT NOT NULL,
    placa        TEXT NOT NULL REFERENCES veiculos(placa),
    url          TEXT NOT NULL,
    publicado_em TEXT NOT NULL,
    PRIMARY KEY (plataforma, anuncio_id)
);
CREATE TABLE IF NOT EXISTS snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    plataforma    TEXT NOT NULL,
    anuncio_id    TEXT NOT NULL,
    preco         REAL NOT NULL,
    visualizacoes INTEGER NOT NULL,
    contatos      INTEGER NOT NULL,
    status        TEXT NOT NULL,   -- ativo | vendido | pausado | ausente
    coletado_em   TEXT NOT NULL,
    FOREIGN KEY (plataforma, anuncio_id) REFERENCES anuncios(plataforma, anuncio_id)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_anuncio ON snapshots(plataforma, anuncio_id, coletado_em);
CREATE INDEX IF NOT EXISTS idx_anuncios_placa ON anuncios(placa);
CREATE TABLE IF NOT EXISTS situacoes (
    placa         TEXT PRIMARY KEY REFERENCES veiculos(placa),
    situacao      TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
"""


def _iso(momento: datetime) -> str:
    return momento.isoformat(timespec="seconds")


def conectar(caminho: Path | str = DB_PADRAO) -> sqlite3.Connection:
    conn = sqlite3.connect(caminho, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def salvar_coleta(
    conn: sqlite3.Connection, plataforma: str, anuncios: Iterable[AnuncioColetado], coletado_em: datetime
) -> int:
    """Grava o snapshot de uma plataforma. Anúncios dela que já existiam e não vieram ficam `ausente`."""
    momento = _iso(coletado_em)
    vistos = set()
    with conn:
        for a in anuncios:
            conn.execute(
                "INSERT INTO veiculos (placa, marca, modelo, versao, ano, km, preco_referencia) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(placa) DO UPDATE SET marca = excluded.marca, "
                "modelo = excluded.modelo, versao = excluded.versao, ano = excluded.ano, km = excluded.km, "
                "preco_referencia = COALESCE(excluded.preco_referencia, veiculos.preco_referencia)",
                (a.placa, a.marca, a.modelo, a.versao, a.ano, a.km, a.preco_referencia),
            )
            conn.execute(
                "INSERT INTO anuncios (plataforma, anuncio_id, placa, url, publicado_em) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(plataforma, anuncio_id) DO UPDATE SET placa = excluded.placa, url = excluded.url, "
                "publicado_em = excluded.publicado_em",
                (plataforma, a.anuncio_id, a.placa, a.url, _iso(a.publicado_em)),
            )
            conn.execute(
                "INSERT INTO snapshots (plataforma, anuncio_id, preco, visualizacoes, contatos, status, coletado_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (plataforma, a.anuncio_id, a.preco, a.visualizacoes, a.contatos, a.status, momento),
            )
            vistos.add(a.anuncio_id)

        # Anúncios conhecidos desta plataforma que não vieram nesta coleta.
        for linha in conn.execute("SELECT anuncio_id FROM anuncios WHERE plataforma = ?", (plataforma,)).fetchall():
            if linha["anuncio_id"] in vistos:
                continue
            ultimo = conn.execute(
                "SELECT preco, visualizacoes, contatos, status FROM snapshots WHERE plataforma = ? AND anuncio_id = ? "
                "ORDER BY coletado_em DESC, id DESC LIMIT 1",
                (plataforma, linha["anuncio_id"]),
            ).fetchone()
            if ultimo is None or ultimo["status"] == "vendido":
                continue  # vendido continua vendido; não vira "ausente"
            conn.execute(
                "INSERT INTO snapshots (plataforma, anuncio_id, preco, visualizacoes, contatos, status, coletado_em) "
                "VALUES (?, ?, ?, ?, ?, 'ausente', ?)",
                (plataforma, linha["anuncio_id"], ultimo["preco"], ultimo["visualizacoes"], ultimo["contatos"], momento),
            )
    return len(vistos)


def contar_anuncios_ativos(conn: sqlite3.Connection, plataforma: str) -> int:
    """Quantos anúncios da plataforma estavam ativos na última vez em que foram vistos."""
    linha = conn.execute(
        "SELECT COUNT(*) AS n FROM snapshots s WHERE s.plataforma = ? AND s.status = 'ativo' AND s.id = ("
        " SELECT s2.id FROM snapshots s2 WHERE s2.plataforma = s.plataforma AND s2.anuncio_id = s.anuncio_id"
        " ORDER BY s2.coletado_em DESC, s2.id DESC LIMIT 1)",
        (plataforma,),
    ).fetchone()
    return linha["n"]


def _placa_ou_none(placa: str) -> Optional[str]:
    try:
        return normalizar_placa(placa)
    except ValueError:
        return None


def listar_veiculos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM veiculos ORDER BY marca, modelo, ano, placa").fetchall()


def buscar_veiculo(conn: sqlite3.Connection, placa: str) -> Optional[sqlite3.Row]:
    normalizada = _placa_ou_none(placa)
    if normalizada is None:
        return None
    return conn.execute("SELECT * FROM veiculos WHERE placa = ?", (normalizada,)).fetchone()


def anuncios_do_veiculo(conn: sqlite3.Connection, placa: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM anuncios WHERE placa = ? ORDER BY plataforma", (_placa_ou_none(placa),)
    ).fetchall()


def snapshots_do_veiculo(conn: sqlite3.Connection, placa: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT s.* FROM snapshots s JOIN anuncios a ON a.plataforma = s.plataforma AND a.anuncio_id = s.anuncio_id "
        "WHERE a.placa = ? ORDER BY s.coletado_em, s.id",
        (_placa_ou_none(placa),),
    ).fetchall()


def todos_snapshots(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Todos os snapshots com a placa do veículo (para avaliar o estoque inteiro de uma vez)."""
    return conn.execute(
        "SELECT s.*, a.placa FROM snapshots s JOIN anuncios a ON a.plataforma = s.plataforma "
        "AND a.anuncio_id = s.anuncio_id ORDER BY s.coletado_em, s.id"
    ).fetchall()


def todos_anuncios(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM anuncios ORDER BY placa, plataforma").fetchall()


def ultima_coleta(conn: sqlite3.Connection) -> Optional[str]:
    linha = conn.execute("SELECT MAX(coletado_em) AS m FROM snapshots").fetchone()
    return linha["m"]


def situacao_salva(conn: sqlite3.Connection, placa: str) -> Optional[str]:
    linha = conn.execute("SELECT situacao FROM situacoes WHERE placa = ?", (placa,)).fetchone()
    return linha["situacao"] if linha else None


def situacoes_salvas(conn: sqlite3.Connection) -> dict[str, str]:
    return {r["placa"]: r["situacao"] for r in conn.execute("SELECT placa, situacao FROM situacoes")}


def salvar_situacoes(conn: sqlite3.Connection, situacoes: dict[str, str], quando: datetime) -> None:
    """Grava várias situações numa única transação (uma por coleta, não uma por veículo)."""
    with conn:
        conn.executemany(
            "INSERT INTO situacoes (placa, situacao, atualizado_em) VALUES (?, ?, ?) "
            "ON CONFLICT(placa) DO UPDATE SET situacao = excluded.situacao, atualizado_em = excluded.atualizado_em",
            [(placa, situacao, _iso(quando)) for placa, situacao in situacoes.items()],
        )


def salvar_situacao(conn: sqlite3.Connection, placa: str, situacao: str, quando: datetime) -> None:
    salvar_situacoes(conn, {placa: situacao}, quando)
