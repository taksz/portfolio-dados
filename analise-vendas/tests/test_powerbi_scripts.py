"""Confere os scripts do Power BI (importar_dados.m, modelo.tmdl, medidas.dax) contra o modelo
estrela que src/exportar_powerbi.py realmente gera. Não substitui testar no Power BI Desktop,
mas pega nomes de colunas/tabelas errados e medidas fora de sincronia."""
import re
from pathlib import Path

import pandas as pd
import pytest

import exportar_powerbi as ep

POWERBI = Path(__file__).resolve().parent.parent / "powerbi"
M = (POWERBI / "importar_dados.m").read_text(encoding="utf-8")
TMDL = (POWERBI / "modelo.tmdl").read_text(encoding="utf-8")
DAX = (POWERBI / "medidas.dax").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def modelo():
    vendas = pd.DataFrame(
        [(1, "2024-01-01", "Moda", "Camiseta", 2, 50.0, 100.0, "Sul", "Online")],
        columns=["id_venda", "data", "categoria", "produto", "quantidade", "preco_unitario", "receita", "regiao", "canal"],
    )
    return ep.construir_modelo(vendas)


BARRA = re.escape(chr(92))  # barra invertida, escrita sem depender de escapes no padrão


def colunas_do_m() -> dict[str, list[str]]:
    padrao = r'Pasta & "' + BARRA + r'(\w+)\.csv".*?TransformColumnTypes\(.*?\{\{(.*?)\}\}'
    achados = re.findall(padrao, M, flags=re.DOTALL)
    return {tabela: re.findall(r'"(\w+)",', lista) for tabela, lista in achados}


def test_m_cobre_as_cinco_tabelas(modelo):
    assert set(colunas_do_m()) == set(modelo)


def test_m_tipa_exatamente_as_colunas_exportadas(modelo):
    for tabela, colunas in colunas_do_m().items():
        assert colunas == list(modelo[tabela].columns), f"colunas divergentes em {tabela}"


def test_m_define_os_tres_parametros():
    for nome in ("Pasta", "Separador", "Cultura"):
        assert f'CONSULTA "{nome}"' in M
    assert M.count("IsParameterQuery = true") == 3


def test_tmdl_relacionamentos_apontam_para_colunas_existentes(modelo):
    pares = re.findall(r"fromColumn: (\w+)\.(\w+)\s+toColumn: (\w+)\.(\w+)", TMDL)
    assert len(pares) == 4
    for t_de, c_de, t_para, c_para in pares:
        assert t_de == "fato_vendas" and t_para != "fato_vendas"  # muitos (fato) -> um (dimensão)
        assert c_de in modelo[t_de].columns and c_para in modelo[t_para].columns
        assert modelo[t_para][c_para].is_unique  # o lado "um" precisa ter chave única


def test_tmdl_referencias_de_coluna_nas_medidas_existem(modelo):
    refs = re.findall(r"(\w+)\[(\w+)\]", TMDL)
    assert refs
    for tabela, coluna in refs:
        assert tabela in modelo and coluna in modelo[tabela].columns, f"{tabela}[{coluna}] não existe"


def medidas_tmdl() -> set[str]:
    return {a or b for a, b in re.findall(r"measure (?:'([^']+)'|(\w+)) =", TMDL)}


def medidas_dax() -> set[str]:
    # nome da medida = texto só com letras, espaços e % antes de " =" no começo da linha
    # (linhas de continuação começam com CALCULATE ( ... e não casam)
    nomes = re.findall(r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ %]*?) =", DAX, flags=re.MULTILINE)
    return {n for n in nomes if not n.startswith("VAR ")}  # VAR = variável dentro da medida, não medida


def test_tmdl_e_dax_tem_as_mesmas_medidas():
    assert len(medidas_dax()) == 12
    assert medidas_tmdl() == medidas_dax()


def test_medidas_referenciadas_existem():
    nomes = medidas_tmdl()
    for ref in re.findall(r"(?<![\w\]])\[([^\]]+)\]", TMDL):
        if ref != "Medidas":  # coluna auxiliar da tabela de medidas
            assert ref in nomes, f"medida [{ref}] não definida"


def test_nenhum_script_usa_emoji():
    pat = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]")
    for texto in (M, TMDL, DAX):
        assert not pat.search(texto)
