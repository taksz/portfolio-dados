"""
Carrega data/vendas.csv em um banco SQLite (data/vendas.db), na tabela
`vendas`, para que as consultas em sql/consultas.sql possam ser executadas
com qualquer cliente SQL (ou com o módulo sqlite3 do próprio Python).

Uso:
    python src/carregar_sqlite.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "vendas.csv"
DB_PATH = BASE_DIR / "data" / "vendas.db"


def main() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(
            f"{CSV_PATH} não encontrado. Rode primeiro: python src/gerar_dados.py"
        )

    df = pd.read_csv(CSV_PATH, parse_dates=["data"])

    conn = sqlite3.connect(DB_PATH)
    try:
        df.to_sql("vendas", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vendas_data ON vendas(data);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vendas_categoria ON vendas(categoria);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vendas_regiao ON vendas(regiao);")
        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM vendas;").fetchone()[0]
        print(f"Tabela 'vendas' criada em {DB_PATH} com {total} registros.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
