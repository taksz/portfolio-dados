"""Tipos comuns: o anúncio como chega de uma plataforma e a normalização da placa."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

STATUS_VALIDOS = ("ativo", "vendido", "pausado")

# Formato antigo (ABC1234) e Mercosul (ABC1D23).
_PLACA = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")


def normalizar_placa(placa: Optional[str]) -> str:
    """Deixa a placa em maiúsculas, sem hífen nem espaços. Lança ValueError se for inválida."""
    texto = re.sub(r"[\s-]", "", placa or "").upper()
    if not _PLACA.match(texto):
        raise ValueError(f"placa inválida: {placa!r}")
    return texto


@dataclass
class AnuncioColetado:
    """Um anúncio de um veículo em uma plataforma, no momento da coleta.

    `visualizacoes` e `contatos` são acumulados desde a publicação (é o que as
    plataformas costumam mostrar); o sistema calcula a variação entre coletas.
    """

    plataforma: str
    anuncio_id: str
    placa: str
    marca: str
    modelo: str
    versao: str
    ano: int
    km: int
    preco: float
    preco_referencia: Optional[float]  # Tabela FIPE, quando a plataforma informa
    visualizacoes: int
    contatos: int
    status: str
    publicado_em: datetime
    url: str = ""

    def __post_init__(self) -> None:
        self.placa = normalizar_placa(self.placa)
        if self.status not in STATUS_VALIDOS:
            raise ValueError(f"status inválido: {self.status!r} (use {', '.join(STATUS_VALIDOS)})")
