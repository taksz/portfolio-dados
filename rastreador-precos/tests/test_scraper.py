import pytest
import requests
import responses

import scraper
from scraper import Produto, converter_preco, parse_catalogo

PAGINA_1 = "https://books.toscrape.com/catalogue/page-1.html"
PAGINA_2 = "https://books.toscrape.com/catalogue/page-2.html"


def test_converter_preco():
    assert converter_preco("£51.77") == 51.77
    assert converter_preco("Â£13.99") == 13.99  # codificação quebrada não pode quebrar o parser
    assert converter_preco("£10") == 10.0


def test_converter_preco_invalido():
    with pytest.raises(ValueError):
        converter_preco("grátis")


def test_parse_pagina1_extrai_20_produtos(html_pagina1):
    produtos, proxima = parse_catalogo(html_pagina1, PAGINA_1)
    assert len(produtos) == 20
    assert proxima == PAGINA_2


def test_parse_primeiro_produto(html_pagina1):
    primeiro = parse_catalogo(html_pagina1, PAGINA_1)[0][0]
    assert primeiro == Produto(
        id="a-light-in-the-attic_1000",
        nome="A Light in the Attic",
        preco=51.77,
        disponivel=True,
        url="https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
    )


def test_parse_ultima_pagina_nao_tem_proxima(html_pagina50):
    produtos, proxima = parse_catalogo(html_pagina50, "https://books.toscrape.com/catalogue/page-50.html")
    assert len(produtos) == 20
    assert proxima is None


def test_parse_detecta_indisponivel():
    html = """
    <article class="product_pod">
      <h3><a href="livro_1/index.html" title="Livro Esgotado">Livro...</a></h3>
      <div class="product_price"><p class="price_color">£9.90</p>
        <p class="instock availability">Out of stock</p></div>
    </article>"""
    produtos, _ = parse_catalogo(html, PAGINA_1)
    assert produtos[0].disponivel is False
    assert produtos[0].preco == 9.90


def test_parse_ignora_artigo_sem_preco():
    html = '<article class="product_pod"><h3><a href="x_1/index.html" title="X">X</a></h3></article>'
    assert parse_catalogo(html, PAGINA_1)[0] == []


@responses.activate
def test_coletar_segue_paginas(html_pagina1, html_pagina50):
    responses.add(responses.GET, PAGINA_1, body=html_pagina1, status=200)
    responses.add(responses.GET, PAGINA_2, body=html_pagina50, status=200)  # sem "next"
    produtos = scraper.coletar(max_paginas=5)
    assert len(produtos) == 40
    assert len(responses.calls) == 2  # parou sozinho: a página 2 (fixture) não tem próxima


@responses.activate
def test_coletar_respeita_max_paginas(html_pagina1):
    responses.add(responses.GET, PAGINA_1, body=html_pagina1, status=200)
    assert len(scraper.coletar(max_paginas=1)) == 20
    assert len(responses.calls) == 1


@responses.activate
def test_coletar_propaga_erro_http():
    responses.add(responses.GET, PAGINA_1, status=503)
    with pytest.raises(requests.HTTPError):
        scraper.coletar(1)
