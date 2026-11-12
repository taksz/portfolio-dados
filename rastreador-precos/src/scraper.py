"""Coleta de produtos do site books.toscrape.com (site público para prática de scraping)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/catalogue/"
PRIMEIRA_PAGINA = BASE_URL + "page-1.html"
USER_AGENT = "rastreador-precos/1.0 (projeto de estudo)"
TIMEOUT = 15


@dataclass(frozen=True)
class Produto:
    id: str  # slug único na URL, ex.: "a-light-in-the-attic_1000"
    nome: str
    preco: float
    disponivel: bool
    url: str


def converter_preco(texto: str) -> float:
    """Converte '£51.77' (ou 'Â£51.77', se a codificação vier errada) em 51.77."""
    encontrado = re.search(r"(\d+(?:\.\d+)?)", texto)
    if not encontrado:
        raise ValueError(f"Preço inválido: {texto!r}")
    return float(encontrado.group(1))


def parse_catalogo(html: str, url_pagina: str = PRIMEIRA_PAGINA) -> tuple[list[Produto], Optional[str]]:
    """Extrai os produtos de uma página de catálogo e a URL da próxima página (ou None)."""
    soup = BeautifulSoup(html, "html.parser")
    produtos: list[Produto] = []
    for artigo in soup.select("article.product_pod"):
        link = artigo.select_one("h3 a")
        preco = artigo.select_one("p.price_color")
        estoque = artigo.select_one("p.availability")
        if link is None or preco is None:
            continue
        url = urljoin(url_pagina, link["href"])
        produto_id = url.rstrip("/").split("/")[-2]
        disponivel = estoque is not None and "in stock" in estoque.get_text().lower()
        produtos.append(
            Produto(
                id=produto_id,
                nome=link.get("title", link.get_text(strip=True)),
                preco=converter_preco(preco.get_text()),
                disponivel=disponivel,
                url=url,
            )
        )
    proxima = soup.select_one("li.next a")
    return produtos, (urljoin(url_pagina, proxima["href"]) if proxima else None)


def coletar(max_paginas: int = 1, sessao: Optional[requests.Session] = None) -> list[Produto]:
    """Percorre até `max_paginas` páginas do catálogo e devolve todos os produtos."""
    sessao = sessao or requests.Session()
    sessao.headers.setdefault("User-Agent", USER_AGENT)
    produtos: list[Produto] = []
    url: Optional[str] = PRIMEIRA_PAGINA
    for _ in range(max_paginas):
        if url is None:
            break
        resposta = sessao.get(url, timeout=TIMEOUT)
        resposta.raise_for_status()
        resposta.encoding = "utf-8"
        pagina, url = parse_catalogo(resposta.text, url)
        produtos.extend(pagina)
    return produtos
