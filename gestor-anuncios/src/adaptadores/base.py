"""Interface que toda plataforma de anúncios precisa implementar."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from modelos import AnuncioColetado


class AdaptadorPlataforma(ABC):
    """Coleta os anúncios de uma plataforma (marketplace, portal de classificados...).

    Para plugar uma plataforma real, crie uma subclasse com um `nome` e implemente
    `coletar`, convertendo o que a plataforma devolve (API, exportação CSV etc.)
    em `AnuncioColetado`. O resto do sistema (banco, regras, painel) não muda.
    """

    nome: str = ""

    @abstractmethod
    def coletar(self, agora: datetime) -> list[AnuncioColetado]:
        """Devolve os anúncios da loja nesta plataforma no momento `agora`."""
