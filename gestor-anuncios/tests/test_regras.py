from datetime import datetime, timedelta

import pytest

import banco
import regras
from modelos import AnuncioColetado
from regras import Config, avaliar, referencia_ajustada

AGORA = datetime(2026, 10, 20, 9, 0, 0)
VEICULO = dict(placa="ABC1D23", marca="Chevrolet", modelo="Onix", versao="LT 1.0", ano=2020, km=90000,
               preco_referencia=66000.0)


def veiculo(**extra):
    v = dict(VEICULO)
    v.update(extra)
    return v


def anuncio(plataforma="AutoFeira", dias_publicado=20):
    return dict(plataforma=plataforma, anuncio_id=f"{plataforma}-1", placa="ABC1D23",
                publicado_em=(AGORA - timedelta(days=dias_publicado)).isoformat())


def snap(dias_atras, contatos, visitas=100, preco=66000.0, plataforma="AutoFeira", status="ativo"):
    return dict(plataforma=plataforma, anuncio_id=f"{plataforma}-1", preco=preco, visualizacoes=visitas,
                contatos=contatos, status=status, coletado_em=(AGORA - timedelta(days=dias_atras)).isoformat())


def semanal(contatos, visitas=None, preco=66000.0, plataforma="AutoFeira", status_final="ativo"):
    """Snapshots há 14, 7 e 0 dias com os acumulados dados (listas de 3)."""
    visitas = visitas or [100, 100, 100]
    return [
        snap(d, c, v, preco, plataforma, status_final if d == 0 else "ativo")
        for d, c, v in zip((14, 7, 0), contatos, visitas)
    ]


def test_vendido_numa_plataforma_pede_remocao_nas_outras():
    snaps = semanal([1, 3, 5], status_final="vendido") + semanal([1, 2, 3], plataforma="CarroJá")
    d = avaliar(veiculo(), snaps, [anuncio(), anuncio("CarroJá")], [], AGORA)
    assert d.situacao == "vendido"
    assert d.vendido_em == "AutoFeira"
    assert d.remover_de == ["CarroJá"]
    assert d.sugestao is None


def test_parado_com_sugestao_de_reducao():
    d = avaliar(veiculo(), semanal([3, 3, 3], preco=70000.0), [anuncio(dias_publicado=35)], [], AGORA)
    assert d.situacao == "parado"
    assert d.contatos_janela == 0
    assert d.dias_anunciado == 35
    # max(min(70000*0,93, 66000*1,03), 66000*0,90) = 65100
    assert d.sugestao == 65100
    assert d.sugestao % 100 == 0


def test_anuncio_novo_sem_contatos_nao_e_parado():
    snaps = [snap(7, 0), snap(0, 0)]
    d = avaliar(veiculo(), snaps, [anuncio(dias_publicado=10)], [], AGORA)
    assert d.situacao == "novo"
    assert d.sugestao is None


def test_atrai_mas_nao_converte():
    d = avaliar(veiculo(), semanal([0, 1, 2], [50, 100, 400]), [anuncio()], [], AGORA)
    assert d.visitas_janela == 300 and d.contatos_janela == 1
    assert d.situacao == "nao_converte"
    assert d.sugestao is not None and d.sugestao < 66000


def test_preco_alto_sugere_voltar_para_perto_da_referencia():
    d = avaliar(veiculo(), semanal([0, 2, 5], preco=83000.0), [anuncio(dias_publicado=10)], [], AGORA)
    assert d.situacao == "preco_alto"
    assert d.sugestao == 67900  # 66000 * 1,03 = 67980 -> 67900


def test_parado_e_caro_mostra_os_dois():
    d = avaliar(veiculo(), semanal([1, 1, 1], preco=83000.0), [anuncio(dias_publicado=40)], [], AGORA)
    assert d.situacao == "parado"
    assert "preco_alto" in d.sinais


def test_nao_converte_tem_prioridade_sobre_parado():
    # muitas visitas e nenhum contato: o diagnóstico mais específico vem primeiro
    d = avaliar(veiculo(), semanal([1, 1, 1], [100, 200, 500]), [anuncio(dias_publicado=40)], [], AGORA)
    assert d.situacao == "nao_converte"
    assert "parado" in d.sinais


def test_sugestao_nunca_fica_abaixo_do_piso_depois_de_arredondar():
    # piso = 61234 * 0,90 = 55110,6; arredondar para baixo daria 55.100 (abaixo do piso)
    assert regras._sugestao(57950, 61234, Config()) == 55200


def test_dois_anuncios_ativos_na_mesma_plataforma_usa_o_menor_preco():
    a1 = dict(anuncio(), anuncio_id="AF-1")
    a2 = dict(anuncio(), anuncio_id="AF-2")
    snaps = [dict(s, anuncio_id="AF-1") for s in semanal([0, 2, 5], preco=70000.0)]
    snaps += [dict(s, anuncio_id="AF-2") for s in semanal([0, 0, 0], preco=66000.0)]
    d = avaliar(veiculo(), snaps, [a1, a2], [], AGORA)
    assert d.preco_atual == 66000.0
    assert d.precos == {"AutoFeira": 66000.0}
    assert d.situacao == "divergente"  # anúncio duplicado com preço diferente


def test_km_alta_reduz_referencia():
    assert referencia_ajustada(veiculo(km=180000), [], AGORA) == pytest.approx(59400)
    assert referencia_ajustada(veiculo(km=90000), [], AGORA) == pytest.approx(66000)
    assert referencia_ajustada(veiculo(km=45000), [], AGORA) == pytest.approx(69300)


def test_km_alta_evita_falso_preco_baixo():
    d = avaliar(veiculo(km=180000), semanal([0, 2, 5], preco=52000.0), [anuncio()], [], AGORA)
    assert "preco_baixo" not in [d.situacao, *d.sinais]


def test_preco_baixo_sinaliza_sem_sugerir_aumento():
    d = avaliar(veiculo(), semanal([0, 0, 0], preco=52000.0), [anuncio(dias_publicado=10)], [], AGORA)
    assert d.situacao == "preco_baixo"
    assert d.sugestao is None


def test_preco_divergente_entre_plataformas():
    snaps = semanal([0, 2, 5]) + semanal([0, 1, 2], preco=68000.0, plataforma="CarroJá")
    d = avaliar(veiculo(), snaps, [anuncio(), anuncio("CarroJá")], [], AGORA)
    assert d.situacao == "divergente"
    assert d.precos == {"AutoFeira": 66000.0, "CarroJá": 68000.0}
    assert d.preco_atual == 66000.0


def test_diferenca_pequena_nao_e_divergencia():
    snaps = semanal([0, 2, 5]) + semanal([0, 1, 2], preco=66900.0, plataforma="CarroJá")
    d = avaliar(veiculo(), snaps, [anuncio(), anuncio("CarroJá")], [], AGORA)
    assert d.situacao == "bem"


def test_performando_bem():
    d = avaliar(veiculo(), semanal([0, 2, 6]), [anuncio()], [], AGORA)
    assert d.situacao == "bem"
    assert d.sinais == []


def test_sem_fipe_usa_mediana_de_carros_parecidos():
    estoque = [
        dict(placa="XYZ1A11", marca="Chevrolet", modelo="Onix", ano=2019, preco_atual=60000.0),
        dict(placa="XYZ1A12", marca="Chevrolet", modelo="Onix", ano=2021, preco_atual=64000.0),
        dict(placa="XYZ1A13", marca="Chevrolet", modelo="Onix", ano=2024, preco_atual=99000.0),  # ano longe
        dict(placa="XYZ1A14", marca="Fiat", modelo="Argo", ano=2020, preco_atual=10.0),  # outro modelo
    ]
    d = avaliar(veiculo(preco_referencia=None), semanal([0, 2, 5]), [anuncio()], estoque, AGORA)
    assert d.referencia == pytest.approx(62000)
    assert d.origem_referencia == "mediana"


def test_sem_fipe_e_sem_parecidos_nao_julga_preco():
    estoque = [dict(placa="XYZ1A11", marca="Chevrolet", modelo="Onix", ano=2019, preco_atual=60000.0)]
    d = avaliar(veiculo(preco_referencia=None), semanal([0, 2, 5], preco=150000.0), [anuncio()], estoque, AGORA)
    assert d.referencia is None
    assert d.situacao == "bem"


def test_sem_referencia_parado_sugere_cinco_por_cento():
    d = avaliar(veiculo(preco_referencia=None), semanal([1, 1, 1], preco=70000.0), [anuncio(dias_publicado=40)], [], AGORA)
    assert d.sugestao == 66500


def test_anuncio_fora_do_ar_nao_vira_vendido_nem_parado():
    snaps = [snap(14, 1), snap(7, 1), snap(0, 1, status="ausente")]
    d = avaliar(veiculo(), snaps, [anuncio(dias_publicado=60)], [], AGORA)
    assert d.situacao == "fora_do_ar"
    assert d.sugestao is None
    assert d.preco_atual is None


def test_pausado_tambem_fica_fora_do_ar():
    d = avaliar(veiculo(), [snap(0, 1, status="pausado")], [anuncio(dias_publicado=60)], [], AGORA)
    assert d.situacao == "fora_do_ar"


def test_primeira_coleta_de_anuncio_recente_conta_tudo_na_janela():
    d = avaliar(veiculo(), [snap(0, 2, 40)], [anuncio(dias_publicado=3)], [], AGORA)
    assert d.contatos_janela == 2
    assert d.situacao == "bem"


def test_primeira_coleta_de_anuncio_antigo_estima_pela_media():
    # 20 contatos em 40 dias = 3,5 por semana: não é parado
    d = avaliar(veiculo(), [snap(0, 20, 400)], [anuncio(dias_publicado=40)], [], AGORA)
    assert d.contatos_janela == 3
    assert d.situacao == "bem"


def test_coleta_anterior_muito_antiga_e_proporcionalizada():
    # 30 contatos entre uma coleta de 30 dias atrás e hoje: na janela de 7 dias contam 7
    snaps = [snap(30, 0, 0), snap(0, 30, 3000)]
    d = avaliar(veiculo(), snaps, [anuncio(dias_publicado=40)], [], AGORA)
    assert d.contatos_janela == 7
    assert d.visitas_janela == 700


def test_snapshots_futuros_sao_ignorados():
    snaps = semanal([0, 2, 5]) + [snap(-7, 50, preco=99000.0, status="vendido")]
    d = avaliar(veiculo(), snaps, [anuncio()], [], AGORA)
    assert d.situacao == "bem"


def test_config_altera_limites():
    d = avaliar(veiculo(), semanal([0, 2, 5]), [anuncio()], [], AGORA, Config(contatos_min=10, dias_parado=5))
    assert d.situacao == "parado"


def test_avaliar_todos_le_do_banco(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    base = dict(marca="Chevrolet", modelo="Onix", versao="LT", ano=2020, km=90000, preco_referencia=66000.0,
                visualizacoes=10, publicado_em=AGORA - timedelta(days=40))
    banco.salvar_coleta(conn, "AutoFeira", [
        AnuncioColetado(plataforma="AutoFeira", anuncio_id="a1", placa="AAA1A11", preco=66000.0, contatos=0, status="ativo", **base),
        AnuncioColetado(plataforma="AutoFeira", anuncio_id="a2", placa="BBB2B22", preco=66000.0, contatos=0, status="vendido", **base),
    ], AGORA - timedelta(days=7))
    banco.salvar_coleta(conn, "AutoFeira", [
        AnuncioColetado(plataforma="AutoFeira", anuncio_id="a1", placa="AAA1A11", preco=66000.0, contatos=0, status="ativo", **base),
    ], AGORA)
    diags = {d.placa: d for d in regras.avaliar_todos(conn, AGORA)}
    assert diags["AAA1A11"].situacao == "parado"
    assert diags["BBB2B22"].situacao == "vendido"
    assert list(diags)[0] == "BBB2B22"  # mais urgente primeiro


def test_todas_as_situacoes_tem_rotulo():
    assert set(regras.ROTULOS) == set(regras.SITUACOES)
