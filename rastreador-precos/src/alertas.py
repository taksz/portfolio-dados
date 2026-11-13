"""Alertas de preço: avisa quando um produto fica abaixo do limite configurado."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from scraper import Produto

ARQUIVO_ALERTAS = Path(__file__).resolve().parent.parent / "alertas.log"


@dataclass(frozen=True)
class Alerta:
    produto_id: str
    nome: str
    preco: float
    limite: float
    preco_anterior: Optional[float]

    def mensagem(self) -> str:
        base = f"{self.nome} está por £{self.preco:.2f} (limite £{self.limite:.2f})"
        if self.preco_anterior is not None and self.preco_anterior > self.preco:
            base += f" — antes £{self.preco_anterior:.2f}"
        elif self.preco_anterior is not None and self.preco_anterior < self.preco:
            base += f" — subiu de £{self.preco_anterior:.2f}, mas continua abaixo do limite"
        return base


def carregar_limites(caminho: Path | str) -> dict[str, float]:
    """Lê um JSON {"produto_id": limite} com limites individuais por produto."""
    with open(caminho, encoding="utf-8") as f:
        return {k: float(v) for k, v in json.load(f).items()}


def verificar(
    produtos: Iterable[Produto],
    limite_padrao: Optional[float],
    precos_anteriores: Optional[dict[str, Optional[float]]] = None,
    limites_por_produto: Optional[dict[str, float]] = None,
) -> list[Alerta]:
    """Um alerta para cada produto disponível com preço estritamente abaixo do limite."""
    precos_anteriores = precos_anteriores or {}
    limites_por_produto = limites_por_produto or {}
    alertas = []
    for p in produtos:
        limite = limites_por_produto.get(p.id, limite_padrao)
        if limite is None or not p.disponivel:
            continue
        if p.preco < limite:
            alertas.append(Alerta(p.id, p.nome, p.preco, limite, precos_anteriores.get(p.id)))
    return alertas


def registrar(alertas: Iterable[Alerta], arquivo: Path | str = ARQUIVO_ALERTAS, agora: Optional[datetime] = None) -> int:
    """Acrescenta os alertas ao arquivo de alertas. Retorna quantos foram escritos."""
    momento = (agora or datetime.now()).isoformat(timespec="seconds")
    linhas = [f"{momento} | ALERTA | {a.produto_id} | {a.mensagem()}\n" for a in alertas]
    if linhas:
        with open(arquivo, "a", encoding="utf-8") as f:
            f.writelines(linhas)
    return len(linhas)
