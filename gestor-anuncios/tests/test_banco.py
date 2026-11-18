from datetime import datetime

import banco
from modelos import AnuncioColetado

T1 = datetime(2026, 9, 1, 9, 0, 0)
T2 = datetime(2026, 9, 8, 9, 0, 0)


def anuncio(plataforma="AutoFeira", anuncio_id="af-1", placa="ABC1D23", preco=68900.0, **extra):
    dados = dict(
        plataforma=plataforma, anuncio_id=anuncio_id, placa=placa, marca="Chevrolet", modelo="Onix",
        versao="LT 1.0", ano=2020, km=45000, preco=preco, preco_referencia=66200.0, visualizacoes=100,
        contatos=2, status="ativo", publicado_em=datetime(2026, 8, 20),
    )
    dados.update(extra)
    return AnuncioColetado(**dados)


def test_conectar_e_idempotente(tmp_path):
    db = tmp_path / "g.db"
    banco.conectar(db).close()
    conn = banco.conectar(db)
    assert banco.listar_veiculos(conn) == []
    assert banco.ultima_coleta(conn) is None


def test_mesma_placa_em_formatos_diferentes_vira_um_veiculo(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    banco.salvar_coleta(conn, "AutoFeira", [anuncio(placa="abc-1d23")], T1)
    banco.salvar_coleta(conn, "CarroJá", [anuncio(plataforma="CarroJá", anuncio_id="cj-9", placa="ABC1D23")], T1)
    assert [v["placa"] for v in banco.listar_veiculos(conn)] == ["ABC1D23"]
    assert {a["plataforma"] for a in banco.anuncios_do_veiculo(conn, "abc-1d23")} == {"AutoFeira", "CarroJá"}


def test_salvar_coleta_grava_snapshot_e_devolve_quantidade(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    assert banco.salvar_coleta(conn, "AutoFeira", [anuncio(), anuncio(anuncio_id="af-2", placa="XYZ9876")], T1) == 2
    snaps = banco.snapshots_do_veiculo(conn, "ABC1D23")
    assert len(snaps) == 1
    assert snaps[0]["preco"] == 68900.0
    assert snaps[0]["coletado_em"] == "2026-09-01T09:00:00"
    assert banco.ultima_coleta(conn) == "2026-09-01T09:00:00"


def test_dados_do_veiculo_sao_atualizados_na_coleta_seguinte(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    banco.salvar_coleta(conn, "AutoFeira", [anuncio()], T1)
    banco.salvar_coleta(conn, "AutoFeira", [anuncio(km=47000, preco_referencia=65000.0)], T2)
    v = banco.buscar_veiculo(conn, "ABC1D23")
    assert v["km"] == 47000 and v["preco_referencia"] == 65000.0


def test_fipe_ausente_nao_apaga_a_que_ja_existe(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    banco.salvar_coleta(conn, "AutoFeira", [anuncio()], T1)
    banco.salvar_coleta(conn, "CarroJá", [anuncio(plataforma="CarroJá", anuncio_id="cj-1", preco_referencia=None)], T1)
    assert banco.buscar_veiculo(conn, "ABC1D23")["preco_referencia"] == 66200.0


def test_anuncio_que_some_da_plataforma_fica_ausente(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    banco.salvar_coleta(conn, "AutoFeira", [anuncio(), anuncio(anuncio_id="af-2", placa="XYZ9876")], T1)
    banco.salvar_coleta(conn, "AutoFeira", [anuncio()], T2)
    snaps = banco.snapshots_do_veiculo(conn, "XYZ9876")
    assert [s["status"] for s in snaps] == ["ativo", "ausente"]
    assert snaps[-1]["preco"] == snaps[0]["preco"]


def test_ausencia_numa_plataforma_nao_afeta_outra(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    banco.salvar_coleta(conn, "AutoFeira", [anuncio()], T1)
    banco.salvar_coleta(conn, "CarroJá", [], T2)
    assert [s["status"] for s in banco.snapshots_do_veiculo(conn, "ABC1D23")] == ["ativo"]


def test_snapshots_ordenados_por_data_com_plataforma(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    banco.salvar_coleta(conn, "AutoFeira", [anuncio(preco=70000.0)], T2)
    banco.salvar_coleta(conn, "AutoFeira", [anuncio(preco=71000.0)], T1)
    snaps = banco.snapshots_do_veiculo(conn, "ABC1D23")
    assert [s["coletado_em"] for s in snaps] == ["2026-09-01T09:00:00", "2026-09-08T09:00:00"]
    assert snaps[0]["plataforma"] == "AutoFeira"


def test_buscar_veiculo_inexistente_ou_placa_invalida(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    assert banco.buscar_veiculo(conn, "ZZZ0000") is None
    assert banco.buscar_veiculo(conn, "isso nao e placa") is None


def test_situacoes_em_lote(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    banco.salvar_situacoes(conn, {"AAA1A11": "parado", "BBB2B22": "bem"}, T1)
    banco.salvar_situacoes(conn, {"AAA1A11": "vendido"}, T2)
    assert banco.situacoes_salvas(conn) == {"AAA1A11": "vendido", "BBB2B22": "bem"}


def test_situacao_salva_e_atualizada(tmp_path):
    conn = banco.conectar(tmp_path / "g.db")
    assert banco.situacao_salva(conn, "ABC1D23") is None
    banco.salvar_situacao(conn, "ABC1D23", "parado", T1)
    banco.salvar_situacao(conn, "ABC1D23", "vendido", T2)
    assert banco.situacao_salva(conn, "ABC1D23") == "vendido"
