"""Orquestra uma execução completa: coletar -> salvar snapshot -> verificar alertas."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import alertas as mod_alertas
import banco
import scraper

log = logging.getLogger("rastreador")


def configurar_logs(arquivo: Path | str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(arquivo, encoding="utf-8"), logging.StreamHandler()],
        force=True,
    )


def executar_coleta(
    db: Path | str = banco.DB_PADRAO,
    paginas: int = 1,
    limite: Optional[float] = None,
    limites_por_produto: Optional[dict[str, float]] = None,
    arquivo_alertas: Path | str = mod_alertas.ARQUIVO_ALERTAS,
    sessao=None,
) -> dict:
    """Roda uma coleta. Erros de rede são logados e não derrubam o agendador."""
    log.info("Iniciando coleta (%d página(s))", paginas)
    try:
        produtos = scraper.coletar(paginas, sessao)
    except Exception as erro:  # rede fora do ar, HTTP 5xx, HTML inesperado...
        log.error("Falha na coleta: %s", erro)
        return {"produtos": 0, "alertas": 0, "erro": str(erro)}

    conn = banco.conectar(db)
    try:
        anteriores = {p.id: banco.preco_anterior(conn, p.id) for p in produtos}
        banco.salvar_snapshot(conn, produtos)
    finally:
        conn.close()

    novos = mod_alertas.verificar(produtos, limite, anteriores, limites_por_produto)
    mod_alertas.registrar(novos, arquivo_alertas)
    for a in novos:
        log.warning("ALERTA: %s", a.mensagem())
    log.info("Coleta concluída: %d produtos salvos, %d alerta(s)", len(produtos), len(novos))
    return {"produtos": len(produtos), "alertas": len(novos), "erro": None}
