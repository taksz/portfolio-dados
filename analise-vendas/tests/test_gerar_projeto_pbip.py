"""Testes do gerador do projeto Power BI (PBIP): estrutura, consistência com o modelo
exportado e com os scripts de powerbi/, e determinismo da saída."""
import json
import re
from pathlib import Path

import pandas as pd
import pytest

import exportar_powerbi as ep
import gerar_projeto_pbip as gp

POWERBI = Path(__file__).resolve().parent.parent / "powerbi"


@pytest.fixture(scope="module")
def projeto(tmp_path_factory):
    destino = tmp_path_factory.mktemp("pbip")
    arquivos = gp.gerar(destino, Path(r"C:\dados\powerbi"))
    return destino, arquivos


def ler_json(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_todos_os_json_sao_validos(projeto):
    destino, arquivos = projeto
    jsons = [a for a in arquivos if a.suffix in (".json", ".pbip", ".pbir", ".pbism")]
    assert len(jsons) >= 15
    for a in jsons:
        ler_json(a)  # lança exceção se o JSON estiver inválido


def test_estrutura_do_projeto(projeto):
    destino, _ = projeto
    assert ler_json(destino / "AnaliseVendas.pbip")["artifacts"][0]["report"]["path"] == "AnaliseVendas.Report"
    pbir = ler_json(destino / "AnaliseVendas.Report" / "definition.pbir")
    assert pbir["datasetReference"]["byPath"]["path"] == "../AnaliseVendas.SemanticModel"
    assert (destino / "AnaliseVendas.SemanticModel" / "definition" / "model.tmdl").exists()


def test_tabelas_do_modelo_batem_com_o_modelo_exportado(projeto):
    vendas = pd.DataFrame(
        [(1, "2024-01-01", "Moda", "Camiseta", 2, 50.0, 100.0, "Sul", "Online")],
        columns=["id_venda", "data", "categoria", "produto", "quantidade", "preco_unitario", "receita", "regiao", "canal"],
    )
    exportado = ep.construir_modelo(vendas)
    assert set(gp.TABELAS) == set(exportado)
    for tabela, colunas in gp.TABELAS.items():
        assert [c[0] for c in colunas] == list(exportado[tabela].columns), tabela


def test_tmdl_das_tabelas_tem_colunas_e_particao(projeto):
    destino, _ = projeto
    for tabela, colunas in gp.TABELAS.items():
        texto = (destino / "AnaliseVendas.SemanticModel" / "definition" / "tables" / f"{tabela}.tmdl").read_text(encoding="utf-8")
        assert f"partition {tabela} = m" in texto
        for col in colunas:
            assert f"column {col[0]}\n" in texto
        assert f'{tabela}.csv' in texto


def test_calendario_marcado_como_tabela_de_datas_e_meses_ordenados(projeto):
    destino, _ = projeto
    cal = (destino / "AnaliseVendas.SemanticModel" / "definition" / "tables" / "dim_calendario.tmdl").read_text(encoding="utf-8")
    assert "dataCategory: Time" in cal and "isKey" in cal
    assert "sortByColumn: mes_num" in cal


def test_parametro_pasta_recebe_o_caminho(projeto):
    destino, _ = projeto
    exp = (destino / "AnaliseVendas.SemanticModel" / "definition" / "expressions.tmdl").read_text(encoding="utf-8")
    assert r'expression Pasta = "C:\dados\powerbi"' in exp
    assert 'expression Separador = ";"' in exp and 'expression Cultura = "pt-BR"' in exp


def test_relacionamentos_ligam_colunas_existentes(projeto):
    destino, _ = projeto
    texto = (destino / "AnaliseVendas.SemanticModel" / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
    pares = re.findall(r"fromColumn: (\w+)\.(\w+)\s+toColumn: (\w+)\.(\w+)", texto)
    assert len(pares) == 4
    nomes = {t: [c[0] for c in cols] for t, cols in gp.TABELAS.items()}
    for t_de, c_de, t_para, c_para in pares:
        assert c_de in nomes[t_de] and c_para in nomes[t_para]


def test_medidas_do_projeto_sao_as_do_medidas_dax():
    dax = (POWERBI / "medidas.dax").read_text(encoding="utf-8")
    nomes_dax = {
        n
        for n in re.findall(r"^([A-Za-z\u00C0-\u00FF][A-Za-z\u00C0-\u00FF %]*?) =", dax, flags=re.MULTILINE)
        if not n.startswith("VAR ")
    }
    assert {m[0] for m in gp.MEDIDAS} == nomes_dax
    assert len(gp.MEDIDAS) == 12


def visuais(destino: Path) -> list[dict]:
    return [ler_json(p) for p in (destino / "AnaliseVendas.Report" / "definition" / "pages").glob("*/visuals/*/visual.json")]


def test_todo_campo_usado_nos_visuais_existe_no_modelo(projeto):
    destino, _ = projeto
    colunas = {t: [c[0] for c in cols] for t, cols in gp.TABELAS.items()}
    medidas = {m[0] for m in gp.MEDIDAS}
    todos = visuais(destino)
    assert len(todos) == 16
    for v in todos:
        for papel in v["visual"]["query"]["queryState"].values():
            for proj in papel["projections"]:
                campo = proj["field"]
                if "Measure" in campo:
                    assert campo["Measure"]["Expression"]["SourceRef"]["Entity"] == "Medidas"
                    assert campo["Measure"]["Property"] in medidas
                else:
                    ent = campo["Column"]["Expression"]["SourceRef"]["Entity"]
                    assert campo["Column"]["Property"] in colunas[ent]


def test_paginas_e_nomes_de_visuais_unicos(projeto):
    destino, _ = projeto
    pags = ler_json(destino / "AnaliseVendas.Report" / "definition" / "pages" / "pages.json")
    assert len(pags["pageOrder"]) == 3 and pags["activePageName"] == pags["pageOrder"][0]
    for nome in pags["pageOrder"]:
        pasta = destino / "AnaliseVendas.Report" / "definition" / "pages" / nome
        assert ler_json(pasta / "page.json")["name"] == nome
        nomes = [ler_json(p)["name"] for p in (pasta / "visuals").glob("*/visual.json")]
        assert len(nomes) == len(set(nomes)) and all(len(n) <= 50 for n in nomes)


def test_segmentacoes_em_modo_dropdown(projeto):
    destino, _ = projeto
    seg = [v for v in visuais(destino) if v["visual"]["visualType"] == "slicer"]
    assert len(seg) == 3
    for v in seg:
        assert v["visual"]["objects"]["data"][0]["properties"]["mode"]["expr"]["Literal"]["Value"] == "'Dropdown'"


def test_medida_de_crescimento_nao_compara_ano_contra_si_mesmo():
    expr = dict((m[0], m[1]) for m in gp.MEDIDAS)["Crescimento YoY %"]
    assert "AnoAtual - 1" in expr and "SAMEPERIODLASTYEAR" not in expr


def test_saida_e_deterministica(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    gp.gerar(a, Path("X"))
    gp.gerar(b, Path("X"))
    for arq in a.rglob("*"):
        if arq.is_file():
            assert arq.read_bytes() == (b / arq.relative_to(a)).read_bytes()
