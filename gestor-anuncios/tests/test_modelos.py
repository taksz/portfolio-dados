from datetime import datetime

import pytest

from modelos import AnuncioColetado, normalizar_placa


def novo_anuncio(**extra):
    dados = dict(
        plataforma="AutoFeira", anuncio_id="af-1", placa="abc-1d23", marca="Chevrolet", modelo="Onix",
        versao="LT 1.0", ano=2020, km=45000, preco=68900.0, preco_referencia=66200.0,
        visualizacoes=120, contatos=3, status="ativo", publicado_em=datetime(2026, 9, 1),
    )
    dados.update(extra)
    return AnuncioColetado(**dados)


@pytest.mark.parametrize(
    "entrada, esperado",
    [("abc-1d23", "ABC1D23"), (" brA 3c45 ", "BRA3C45"), ("ABC1234", "ABC1234"), ("xyz-9876", "XYZ9876")],
)
def test_normalizar_placa_aceita_formato_antigo_e_mercosul(entrada, esperado):
    assert normalizar_placa(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "AB12345", "ABCD123", "ABC12D3", "1BC1234", None])
def test_normalizar_placa_rejeita_invalidas(entrada):
    with pytest.raises(ValueError):
        normalizar_placa(entrada)


def test_anuncio_normaliza_placa():
    assert novo_anuncio().placa == "ABC1D23"


def test_anuncio_rejeita_status_desconhecido():
    with pytest.raises(ValueError):
        novo_anuncio(status="excluido")


def test_anuncio_aceita_sem_referencia():
    assert novo_anuncio(preco_referencia=None).preco_referencia is None
