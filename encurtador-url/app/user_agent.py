"""
Parser simples (baseado em regex) de User-Agent, para classificar cliques
por navegador e sistema operacional sem depender de bibliotecas externas.

É uma heurística, não um parser completo de todos os User-Agents que
existem no mundo — cobre os casos mais comuns (Chrome, Firefox, Safari,
Edge, Windows, macOS, Linux, Android, iOS). Navegadores/SOs não
reconhecidos caem em "Outro".
"""

from __future__ import annotations

import re

_NAVEGADORES = [
    ("Edge", re.compile(r"Edg/")),
    ("Chrome", re.compile(r"Chrome/")),
    ("Firefox", re.compile(r"Firefox/")),
    ("Safari", re.compile(r"Version/.*Safari/")),
    ("Opera", re.compile(r"OPR/")),
]

_SISTEMAS = [
    ("Android", re.compile(r"Android")),
    ("iOS", re.compile(r"iPhone|iPad|iPod")),
    ("Windows", re.compile(r"Windows")),
    ("macOS", re.compile(r"Macintosh|Mac OS X")),
    ("Linux", re.compile(r"Linux")),
]


def identificar_navegador(user_agent: str) -> str:
    if not user_agent:
        return "Outro"
    for nome, padrao in _NAVEGADORES:
        if padrao.search(user_agent):
            return nome
    return "Outro"


def identificar_sistema_operacional(user_agent: str) -> str:
    if not user_agent:
        return "Outro"
    for nome, padrao in _SISTEMAS:
        if padrao.search(user_agent):
            return nome
    return "Outro"
