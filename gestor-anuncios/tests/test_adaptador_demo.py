from collections import defaultdict
from datetime import datetime, timedelta

import pytest

from adaptadores import AdaptadorPlataforma, PLATAFORMAS_DEMO, criar_adaptadores_demo
from modelos import AnuncioColetado

INICIO = datetime(2026, 9, 1, 9, 0, 0)


def coletar_tudo(adaptadores, agora):
    return [a for ad in adaptadores for a in ad.coletar(agora)]


def test_interface_abstrata_nao_instancia():
    with pytest.raises(TypeError):
        AdaptadorPlataforma()


def test_adaptador_minimo_implementa_coletar():
    class Fake(AdaptadorPlataforma):
        nome = "Fake"

        def coletar(self, agora):
            return []

    assert Fake().coletar(INICIO) == []


def test_tres_plataformas_ficticias():
    adaptadores = criar_adaptadores_demo()
    assert [a.nome for a in adaptadores] == list(PLATAFORMAS_DEMO)
    assert all(isinstance(a, AdaptadorPlataforma) for a in adaptadores)


def test_quarenta_veiculos_com_placas_validas_ao_fim_da_demo():
    anuncios = coletar_tudo(criar_adaptadores_demo(), INICIO + timedelta(weeks=7))
    assert all(isinstance(a, AnuncioColetado) for a in anuncios)
    assert len({a.placa for a in anuncios}) == 40
    assert all(a.plataforma == a.plataforma.strip() and a.plataforma in PLATAFORMAS_DEMO for a in anuncios)


def test_deterministico_com_mesma_semente():
    agora = INICIO + timedelta(days=10)
    assert coletar_tudo(criar_adaptadores_demo(), agora) == coletar_tudo(criar_adaptadores_demo(), agora)


def test_semente_diferente_muda_dados():
    agora = INICIO + timedelta(days=10)
    assert coletar_tudo(criar_adaptadores_demo(semente=1), agora) != coletar_tudo(criar_adaptadores_demo(), agora)


def test_contadores_nao_diminuem_com_o_tempo():
    adaptadores = criar_adaptadores_demo()
    antes = {(a.plataforma, a.anuncio_id): a for a in coletar_tudo(adaptadores, INICIO + timedelta(days=7))}
    depois = coletar_tudo(adaptadores, INICIO + timedelta(days=14))
    for a in depois:
        anterior = antes.get((a.plataforma, a.anuncio_id))
        if anterior:
            assert a.visualizacoes >= anterior.visualizacoes
            assert a.contatos >= anterior.contatos


def test_nao_lista_anuncio_antes_da_publicacao():
    for a in coletar_tudo(criar_adaptadores_demo(), INICIO):
        assert a.publicado_em <= INICIO


def test_carro_vendido_em_uma_plataforma_continua_ativo_em_outra():
    anuncios = coletar_tudo(criar_adaptadores_demo(), INICIO + timedelta(weeks=5))
    por_placa = defaultdict(set)
    for a in anuncios:
        por_placa[a.placa].add(a.status)
    assert any({"vendido", "ativo"} <= status for status in por_placa.values())


def test_algum_carro_tem_preco_diferente_entre_plataformas():
    anuncios = coletar_tudo(criar_adaptadores_demo(), INICIO + timedelta(weeks=1))
    precos = defaultdict(set)
    for a in anuncios:
        precos[a.placa].add(a.preco)
    assert any(len(p) > 1 for p in precos.values())


def test_um_carro_fica_pausado_em_todas_as_plataformas():
    anuncios = coletar_tudo(criar_adaptadores_demo(), INICIO + timedelta(weeks=7))
    por_placa = defaultdict(set)
    for a in anuncios:
        por_placa[a.placa].add(a.status)
    assert sum(1 for s in por_placa.values() if s == {"pausado"}) == 1


def test_alguns_anuncios_sem_fipe_informada():
    anuncios = coletar_tudo(criar_adaptadores_demo(), INICIO + timedelta(weeks=7))
    assert any(a.preco_referencia is None for a in anuncios)
    assert any(a.preco_referencia is not None for a in anuncios)
