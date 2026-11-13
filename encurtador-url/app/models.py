"""
Camada de acesso a dados: cria o schema SQLite e expõe funções para
criar URLs curtas, resolvê-las e registrar/consultar cliques (analytics).

Cada função recebe a conexão sqlite3 explicitamente (em vez de depender
de um estado global), o que facilita testar com um banco em memória.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .shortener import gerar_codigo
from .user_agent import identificar_navegador, identificar_sistema_operacional

SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    url_original TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    expira_em TEXT,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cliques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id INTEGER NOT NULL REFERENCES urls(id),
    clicado_em TEXT NOT NULL,
    referrer TEXT,
    navegador TEXT,
    sistema_operacional TEXT,
    ip_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_cliques_url_id ON cliques(url_id);
"""


def conectar(caminho_db: str) -> sqlite3.Connection:
    conn = sqlite3.connect(caminho_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def inicializar_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrar_urls(conn)
    conn.commit()


def _migrar_urls(conn: sqlite3.Connection) -> None:
    """Bancos criados antes da expiração/desativação não têm as colunas novas: acrescenta."""
    colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(urls)").fetchall()}
    if "expira_em" not in colunas:
        conn.execute("ALTER TABLE urls ADD COLUMN expira_em TEXT")
    if "ativo" not in colunas:
        conn.execute("ALTER TABLE urls ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1")


def status_url(url, agora: Optional[datetime] = None) -> str:
    """'ativo', 'desativado' (desligado à mão) ou 'expirado' (passou da data de expiração).

    Desativado tem prioridade: um link desligado fica desligado mesmo antes de expirar.
    """
    if not url["ativo"]:
        return "desativado"
    if url["expira_em"]:
        agora = agora or datetime.now(timezone.utc)
        if datetime.fromisoformat(url["expira_em"]) <= agora:
            return "expirado"
    return "ativo"


def definir_ativo(conn: sqlite3.Connection, codigo: str, ativo: bool) -> bool:
    """Liga ou desliga um link. Devolve False se o código não existe."""
    cur = conn.execute("UPDATE urls SET ativo = ? WHERE codigo = ?", (1 if ativo else 0, codigo))
    conn.commit()
    return cur.rowcount > 0


def definir_expiracao(conn: sqlite3.Connection, codigo: str, expira_em: Optional[datetime]) -> bool:
    """Muda a data de expiração (None = nunca expira). Devolve False se o código não existe."""
    valor = expira_em.isoformat() if expira_em else None
    cur = conn.execute("UPDATE urls SET expira_em = ? WHERE codigo = ?", (valor, codigo))
    conn.commit()
    return cur.rowcount > 0


def hash_ip(ip: str) -> str:
    """Hash do IP (SHA-256) — nunca guardamos o IP em texto puro.

    O hash permite estimar 'visitantes únicos' sem armazenar um dado
    pessoal diretamente identificável.
    """
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def criar_url_curta(conn: sqlite3.Connection, url_original: str, expira_em: Optional[datetime] = None) -> str:
    """Cria uma URL curta para `url_original` e retorna o código gerado.

    `expira_em` (opcional) é o momento a partir do qual o link deixa de funcionar.

    Gera um código e tenta inserir; em caso de colisão (código já
    existente — extremamente raro com 6 caracteres em base62), tenta
    novamente com um novo código.
    """
    for _ in range(5):
        codigo = gerar_codigo()
        try:
            conn.execute(
                "INSERT INTO urls (codigo, url_original, criado_em, expira_em) VALUES (?, ?, ?, ?)",
                (codigo, url_original, datetime.now(timezone.utc).isoformat(), expira_em.isoformat() if expira_em else None),
            )
            conn.commit()
            return codigo
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("Não foi possível gerar um código único após várias tentativas.")


def obter_url(conn: sqlite3.Connection, codigo: str) -> Optional[sqlite3.Row]:
    cur = conn.execute("SELECT * FROM urls WHERE codigo = ?", (codigo,))
    return cur.fetchone()


def registrar_clique(
    conn: sqlite3.Connection,
    url_id: int,
    referrer: Optional[str],
    user_agent: Optional[str],
    ip: Optional[str],
) -> None:
    conn.execute(
        """INSERT INTO cliques (url_id, clicado_em, referrer, navegador, sistema_operacional, ip_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            url_id,
            datetime.now(timezone.utc).isoformat(),
            referrer,
            identificar_navegador(user_agent or ""),
            identificar_sistema_operacional(user_agent or ""),
            hash_ip(ip) if ip else None,
        ),
    )
    conn.commit()


def obter_estatisticas(conn: sqlite3.Connection, codigo: str) -> Optional[Dict]:
    url = obter_url(conn, codigo)
    if url is None:
        return None

    total_cliques = conn.execute(
        "SELECT COUNT(*) AS n FROM cliques WHERE url_id = ?", (url["id"],)
    ).fetchone()["n"]

    visitantes_unicos = conn.execute(
        "SELECT COUNT(DISTINCT ip_hash) AS n FROM cliques WHERE url_id = ? AND ip_hash IS NOT NULL",
        (url["id"],),
    ).fetchone()["n"]

    cliques_por_dia = conn.execute(
        """SELECT substr(clicado_em, 1, 10) AS dia, COUNT(*) AS cliques
           FROM cliques WHERE url_id = ? GROUP BY dia ORDER BY dia""",
        (url["id"],),
    ).fetchall()

    navegadores = conn.execute(
        """SELECT navegador, COUNT(*) AS cliques FROM cliques
           WHERE url_id = ? GROUP BY navegador ORDER BY cliques DESC""",
        (url["id"],),
    ).fetchall()

    sistemas = conn.execute(
        """SELECT sistema_operacional, COUNT(*) AS cliques FROM cliques
           WHERE url_id = ? GROUP BY sistema_operacional ORDER BY cliques DESC""",
        (url["id"],),
    ).fetchall()

    referrers = conn.execute(
        """SELECT COALESCE(NULLIF(referrer, ''), '(direto)') AS referrer, COUNT(*) AS cliques
           FROM cliques WHERE url_id = ? GROUP BY referrer ORDER BY cliques DESC LIMIT 10""",
        (url["id"],),
    ).fetchall()

    return {
        "codigo": url["codigo"],
        "url_original": url["url_original"],
        "criado_em": url["criado_em"],
        "expira_em": url["expira_em"],
        "ativo": bool(url["ativo"]),
        "status": status_url(url),
        "total_cliques": total_cliques,
        "visitantes_unicos_aprox": visitantes_unicos,
        "cliques_por_dia": [dict(r) for r in cliques_por_dia],
        "navegadores": [dict(r) for r in navegadores],
        "sistemas_operacionais": [dict(r) for r in sistemas],
        "top_referrers": [dict(r) for r in referrers],
    }


def listar_urls(conn: sqlite3.Connection) -> List[Dict]:
    urls = conn.execute("SELECT * FROM urls ORDER BY id DESC").fetchall()
    resultado = []
    for u in urls:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM cliques WHERE url_id = ?", (u["id"],)
        ).fetchone()["n"]
        resultado.append({**dict(u), "ativo": bool(u["ativo"]), "status": status_url(u), "total_cliques": total})
    return resultado
