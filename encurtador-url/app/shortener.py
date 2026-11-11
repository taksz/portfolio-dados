"""
Geração de códigos curtos (base62) e validação de URLs.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlparse

ALFABETO = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
TAMANHO_PADRAO = 6


def gerar_codigo(tamanho: int = TAMANHO_PADRAO) -> str:
    """Gera um código aleatório em base62 (a-z, A-Z, 0-9) com `tamanho` caracteres.

    Com 6 caracteres em base62 há 62**6 ≈ 56,8 bilhões de combinações possíveis,
    o que torna colisões extremamente raras — mesmo assim, quem chama esta
    função deve checar unicidade no banco e, em caso de colisão, gerar outro.
    """
    return "".join(secrets.choice(ALFABETO) for _ in range(tamanho))


def validar_url(url: str) -> bool:
    """Valida se `url` é uma URL http(s) bem formada, com domínio."""
    try:
        resultado = urlparse(url)
    except ValueError:
        return False
    return resultado.scheme in ("http", "https") and bool(resultado.netloc)
