"""Log de alertas: uma linha por mudança de situação que pede atenção."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from regras import ROTULOS, Diagnostico

ARQUIVO_ALERTAS = Path(__file__).resolve().parent.parent / "alertas.log"

# Situações que geram alerta quando um veículo entra nelas.
SITUACOES_ALERTA = {"vendido", "fora_do_ar", "parado", "nao_converte", "preco_alto", "divergente"}


def mensagem(diag: Diagnostico, descricao: str = "") -> str:
    """Ex.: 'Hyundai HB20 Comfort 1.0 2019: Parado — 41 dias anunciado... Sugestão: R$ 61.900.'"""
    prefixo = f"{descricao}: " if descricao else ""
    return f"{prefixo}{ROTULOS[diag.situacao]} — {diag.motivo}"


def registrar(linhas: Iterable[tuple[str, str]], arquivo: Path | str, quando: datetime) -> int:
    """Acrescenta linhas `data | ALERTA | placa | mensagem` ao arquivo. Devolve quantas gravou."""
    momento = quando.isoformat(timespec="seconds")
    linhas = list(linhas)
    if linhas:
        with open(arquivo, "a", encoding="utf-8") as f:
            for placa, texto in linhas:
                f.write(f"{momento} | ALERTA | {placa} | {texto}\n")
    return len(linhas)


def ler(arquivo: Path | str, limite: int = 50) -> list[dict]:
    """Últimos alertas, do mais recente para o mais antigo."""
    caminho = Path(arquivo)
    if not caminho.exists():
        return []
    alertas = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        partes = linha.split(" | ", 3)
        if len(partes) == 4:
            alertas.append({"quando": partes[0], "placa": partes[2], "mensagem": partes[3]})
    return alertas[::-1][:limite]
