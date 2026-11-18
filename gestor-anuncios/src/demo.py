"""Gera um histórico SIMULADO de coletas semanais com o adaptador de demonstração.

Os veículos, as placas, as plataformas e os números são fictícios (veja
`adaptadores/demo.py`). Serve para mostrar o painel e as regras funcionando sem
depender de nenhuma plataforma real.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import banco
import coleta
from adaptadores import criar_adaptadores_demo
from adaptadores.demo import INICIO_PADRAO

DB_DEMO = Path(__file__).resolve().parent.parent / "demo.db"
ALERTAS_DEMO = Path(__file__).resolve().parent.parent / "alertas-demo.log"


def gerar(
    db: Path | str = DB_DEMO, arquivo_alertas: Path | str = ALERTAS_DEMO, semanas: int = 8, semente: int = 42,
    inicio: datetime = INICIO_PADRAO,
) -> int:
    """Roda `semanas` coletas simuladas, uma por semana a partir de `inicio`. Devolve quantas fez."""
    adaptadores = criar_adaptadores_demo(semente, inicio)
    conn = banco.conectar(db)
    try:
        for i in range(semanas):
            coleta.executar(adaptadores, conn, arquivo_alertas, inicio + timedelta(weeks=i))
    finally:
        conn.close()
    return semanas


def tem_dados(db: Path | str) -> bool:
    conn = banco.conectar(db)
    try:
        return bool(banco.listar_veiculos(conn))
    finally:
        conn.close()


def preparar_se_vazio(db: Path | str = DB_DEMO, arquivo_alertas: Path | str = ALERTAS_DEMO) -> bool:
    """Cria o histórico simulado só se o banco estiver vazio (útil para hospedagem de demonstração)."""
    if tem_dados(db):
        return False
    gerar(db, arquivo_alertas)
    return True
