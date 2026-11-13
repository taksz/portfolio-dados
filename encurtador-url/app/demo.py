"""Popula o banco com links e cliques SIMULADOS, só para demonstrar o painel.

Quem acabou de clonar o projeto não tem nenhum clique, então o painel aparece
vazio. Este script cria 3 links (códigos `demo-*`) com cerca de 14 dias de
cliques gerados de forma pseudoaleatória (semente fixa), em navegadores,
sistemas e origens variados. Os dados NÃO são reais.

Uso:
    python -m app.demo            # adiciona os links de demonstração
    python -m app.demo --limpar   # remove só os links de demonstração
"""
from __future__ import annotations

import argparse
import hashlib
import random
from datetime import datetime, timedelta, timezone

from . import models
from .main import DB_PATH

LINKS = [
    ("demo-docs", "https://docs.python.org/3/tutorial/", 1.0),
    ("demo-portfolio", "https://github.com/taksz/portfolio-dados", 0.6),
    ("demo-dados", "https://pandas.pydata.org/docs/", 0.35),
    ("demo-expirado", "https://www.python.org/downloads/", 0.5),
    ("demo-desativado", "https://numpy.org/doc/stable/", 0.4),
]
# Estados de exemplo: expira_dias < 0 = já expirou há N dias; ativo 0 = desligado à mão.
EXTRAS = {
    "demo-docs": {"expira_dias": 20},
    "demo-expirado": {"expira_dias": -3},
    "demo-desativado": {"ativo": 0},
}
NAVEGADORES = [("Chrome", 6), ("Firefox", 2), ("Safari", 3), ("Edge", 2), ("Outro", 1)]
SISTEMAS = [("Windows", 5), ("Android", 4), ("macOS", 2), ("iOS", 3), ("Linux", 1)]
ORIGENS = [
    ("https://www.google.com/", 5),
    ("https://www.linkedin.com/", 4),
    ("https://github.com/", 3),
    ("https://t.co/", 1),
    (None, 3),  # acesso direto
]
DIAS = 14


def _sortear(rng: random.Random, opcoes):
    return rng.choices([o for o, _ in opcoes], weights=[p for _, p in opcoes])[0]


def limpar(conn) -> int:
    codigos = [c for c, _, _ in LINKS]
    marcas = ",".join("?" * len(codigos))
    ids = [r["id"] for r in conn.execute(f"SELECT id FROM urls WHERE codigo IN ({marcas})", codigos)]
    for url_id in ids:
        conn.execute("DELETE FROM cliques WHERE url_id = ?", (url_id,))
        conn.execute("DELETE FROM urls WHERE id = ?", (url_id,))
    conn.commit()
    return len(ids)


def popular(conn, semente: int = 7, agora: datetime | None = None) -> int:
    """Cria os links de demonstração (recriando-os se já existirem). Retorna o total de cliques."""
    limpar(conn)
    rng = random.Random(semente)
    agora = agora or datetime.now(timezone.utc)
    total = 0
    for codigo, destino, peso in LINKS:
        criado = agora - timedelta(days=DIAS)
        extra = EXTRAS.get(codigo, {})
        expira = agora + timedelta(days=extra["expira_dias"]) if "expira_dias" in extra else None
        cur = conn.execute(
            "INSERT INTO urls (codigo, url_original, criado_em, expira_em, ativo) VALUES (?, ?, ?, ?, ?)",
            (codigo, destino, criado.isoformat(), expira.isoformat() if expira else None, extra.get("ativo", 1)),
        )
        url_id = cur.lastrowid
        visitantes = [hashlib.sha256(f"{codigo}-{i}".encode()).hexdigest() for i in range(int(40 * peso) + 5)]
        for dia in range(DIAS):
            # pico no meio do período, com ruído
            base = 3 + 9 * (1 - abs(dia - DIAS * 0.6) / (DIAS * 0.6))
            n = max(0, int(rng.gauss(base * peso, 2)))
            for _ in range(n):
                momento = agora - timedelta(days=DIAS - 1 - dia, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
                if expira and momento > expira:
                    continue  # depois de expirar, o link não recebe mais cliques
                conn.execute(
                    "INSERT INTO cliques (url_id, clicado_em, referrer, navegador, sistema_operacional, ip_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        url_id,
                        min(momento, agora).isoformat(),
                        _sortear(rng, ORIGENS),
                        _sortear(rng, NAVEGADORES),
                        _sortear(rng, SISTEMAS),
                        rng.choice(visitantes),
                    ),
                )
                total += 1
    conn.commit()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limpar", action="store_true", help="remove os links de demonstração")
    args = parser.parse_args()

    conn = models.conectar(str(DB_PATH))
    models.inicializar_schema(conn)
    if args.limpar:
        print(f"{limpar(conn)} link(s) de demonstração removido(s).")
    else:
        total = popular(conn)
        print(f"{len(LINKS)} links e {total} cliques SIMULADOS gravados em {DB_PATH}.")
        print("Abra http://127.0.0.1:8000/ depois de subir o servidor (uvicorn app.main:app).")
    conn.close()


if __name__ == "__main__":
    main()
