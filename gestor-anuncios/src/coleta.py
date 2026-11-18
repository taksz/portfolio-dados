"""Orquestra uma execução: coletar cada plataforma -> salvar snapshot -> avaliar -> alertar."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

import alertas as mod_alertas
import banco
import regras
from adaptadores import AdaptadorPlataforma

log = logging.getLogger("gestor")


def configurar_logs(arquivo: Optional[Path | str] = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if arquivo:
        handlers.append(logging.FileHandler(arquivo, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
                        handlers=handlers, force=True)


def descricao(veiculo) -> str:
    return f"{veiculo['marca']} {veiculo['modelo']} {veiculo['versao']} {veiculo['ano']}"


def executar(
    adaptadores: Sequence[AdaptadorPlataforma],
    conn: sqlite3.Connection,
    arquivo_alertas: Path | str = mod_alertas.ARQUIVO_ALERTAS,
    agora: Optional[datetime] = None,
    cfg: regras.Config = regras.Config(),
) -> dict:
    """Roda uma coleta. A falha de uma plataforma é logada e não impede as outras."""
    agora = agora or datetime.now().replace(microsecond=0)
    log.info("Iniciando coleta em %d plataforma(s)", len(adaptadores))
    total, erros = 0, 0
    for adaptador in adaptadores:
        try:
            anuncios = adaptador.coletar(agora)
            conhecidos = banco.contar_anuncios_ativos(conn, adaptador.nome)
            if not anuncios and conhecidos:
                # Lista vazia com anúncios ativos no banco costuma ser falha da plataforma,
                # não a loja tirando tudo do ar: não marca tudo como ausente.
                raise RuntimeError(f"nenhum anúncio retornado, mas havia {conhecidos} ativo(s); resposta ignorada")
            total += banco.salvar_coleta(conn, adaptador.nome, anuncios, agora)
        except Exception as erro:  # API fora do ar, resposta inesperada...
            erros += 1
            log.error("Falha ao coletar %s: %s", adaptador.nome, erro)

    if adaptadores and erros == len(adaptadores):
        # Sem nenhum dado novo, reavaliar só faria a janela "envelhecer" e gerar alertas falsos.
        log.error("Nenhuma plataforma respondeu; situações mantidas até a próxima coleta")
        return {"anuncios": 0, "veiculos": 0, "alertas": 0, "erros": erros}

    veiculos = {v["placa"]: v for v in banco.listar_veiculos(conn)}
    salvas = banco.situacoes_salvas(conn)
    mudancas, novos = {}, []
    diagnosticos = regras.avaliar_todos(conn, agora, cfg)
    for d in diagnosticos:
        if salvas.get(d.placa) == d.situacao:
            continue
        mudancas[d.placa] = d.situacao
        if d.situacao in mod_alertas.SITUACOES_ALERTA:
            texto = mod_alertas.mensagem(d, descricao(veiculos[d.placa]))
            novos.append((d.placa, texto))
            log.warning("ALERTA: %s (%s)", texto, d.placa)
    banco.salvar_situacoes(conn, mudancas, agora)
    mod_alertas.registrar(novos, arquivo_alertas, agora)
    log.info("Coleta concluída: %d anúncio(s), %d veículo(s), %d alerta(s), %d erro(s)",
             total, len(diagnosticos), len(novos), erros)
    return {"anuncios": total, "veiculos": len(diagnosticos), "alertas": len(novos), "erros": erros}
