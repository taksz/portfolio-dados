"""
Gera um Projeto do Power BI (formato PBIP) com o dashboard de vendas pronto.

O Power BI Desktop abre a pasta gerada direto (powerbi/AnaliseVendas.pbip), já com:
  - as 5 tabelas do modelo estrela, importadas dos CSVs de data/powerbi/;
  - os 4 relacionamentos, a tabela de datas e o ordenamento dos meses;
  - as 12 medidas (as mesmas de powerbi/medidas.dax);
  - 3 páginas de relatório com cartões, gráficos e segmentações.

Uso:
    python src/exportar_powerbi.py        # gera os CSVs do modelo estrela
    python src/gerar_projeto_pbip.py      # gera o projeto PBIP em powerbi/
    # depois: abra powerbi/AnaliseVendas.pbip no Power BI Desktop

O parâmetro "Pasta" do modelo recebe o caminho absoluto de data/powerbi/ desta máquina.
Se mover o repositório, rode o script de novo (ou edite o parâmetro no Power Query).
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_DIR = BASE_DIR / "data" / "powerbi"
SAIDA_DIR = BASE_DIR / "powerbi"
NOME = "AnaliseVendas"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
S_VERSAO = f"{SCHEMA}/versionMetadata/1.0.0/schema.json"
S_RELATORIO = f"{SCHEMA}/report/3.0.0/schema.json"
S_PAGINAS = f"{SCHEMA}/pagesMetadata/1.0.0/schema.json"
S_PAGINA = f"{SCHEMA}/page/2.0.0/schema.json"
S_VISUAL = f"{SCHEMA}/visualContainer/2.0.0/schema.json"

# --------------------------------------------------------------------------------------
# Modelo: tabelas, colunas e medidas (devem espelhar src/exportar_powerbi.py)
# --------------------------------------------------------------------------------------
# cada coluna: (nome, tipo_tmdl, tipo_m, resumo, propriedades extras)
TABELAS: dict[str, list[tuple]] = {
    "fato_vendas": [
        ("id_venda", "int64", "Int64.Type", "none", {}),
        ("data", "dateTime", "type date", "none", {"formatString": "dd/mm/yyyy"}),
        ("id_produto", "int64", "Int64.Type", "none", {}),
        ("id_regiao", "int64", "Int64.Type", "none", {}),
        ("id_canal", "int64", "Int64.Type", "none", {}),
        ("quantidade", "int64", "Int64.Type", "sum", {}),
        ("preco_unitario", "double", "type number", "none", {"formatString": '"R$" #,0.00'}),
        ("receita", "double", "type number", "none", {"formatString": '"R$" #,0.00'}),
    ],
    "dim_calendario": [
        ("data", "dateTime", "type date", "none", {"formatString": "dd/mm/yyyy", "isKey": True}),
        ("ano", "int64", "Int64.Type", "none", {}),
        ("trimestre", "string", "type text", "none", {}),
        ("mes_num", "int64", "Int64.Type", "none", {}),
        ("mes_nome", "string", "type text", "none", {"sortByColumn": "mes_num"}),
        ("ano_mes", "string", "type text", "none", {}),
        ("dia_semana_num", "int64", "Int64.Type", "none", {}),
        ("dia_semana", "string", "type text", "none", {"sortByColumn": "dia_semana_num"}),
        ("alta_temporada", "string", "type text", "none", {}),
    ],
    "dim_produto": [
        ("id_produto", "int64", "Int64.Type", "none", {}),
        ("produto", "string", "type text", "none", {}),
        ("categoria", "string", "type text", "none", {}),
    ],
    "dim_regiao": [
        ("id_regiao", "int64", "Int64.Type", "none", {}),
        ("regiao", "string", "type text", "none", {}),
    ],
    "dim_canal": [
        ("id_canal", "int64", "Int64.Type", "none", {}),
        ("canal", "string", "type text", "none", {}),
    ],
}

RELACIONAMENTOS = [
    ("rel_fato_calendario", "fato_vendas", "data", "dim_calendario", "data"),
    ("rel_fato_produto", "fato_vendas", "id_produto", "dim_produto", "id_produto"),
    ("rel_fato_regiao", "fato_vendas", "id_regiao", "dim_regiao", "id_regiao"),
    ("rel_fato_canal", "fato_vendas", "id_canal", "dim_canal", "id_canal"),
]

BRL = '"R$" #,0.00'
# (nome, expressão DAX, formato)
MEDIDAS: list[tuple[str, str, str]] = [
    ("Receita Total", "SUM ( fato_vendas[receita] )", BRL),
    ("Vendas", "COUNTROWS ( fato_vendas )", "#,0"),
    ("Unidades Vendidas", "SUM ( fato_vendas[quantidade] )", "#,0"),
    ("Ticket Médio", "DIVIDE ( [Receita Total], [Vendas] )", BRL),
    ("Receita Ano Anterior", "CALCULATE ( [Receita Total], SAMEPERIODLASTYEAR ( dim_calendario[data] ) )", BRL),
    (
        "Crescimento YoY %",
        "VAR AnoAtual = MAX ( dim_calendario[ano] )\n"
        "VAR ReceitaAtual = CALCULATE ( [Receita Total], dim_calendario[ano] = AnoAtual )\n"
        "VAR ReceitaAnterior = CALCULATE ( [Receita Total], dim_calendario[ano] = AnoAtual - 1 )\n"
        "RETURN DIVIDE ( ReceitaAtual - ReceitaAnterior, ReceitaAnterior )",
        "0.0%",
    ),
    ("Receita Acumulada no Ano", "TOTALYTD ( [Receita Total], dim_calendario[data] )", BRL),
    ("Participação na Receita %", "DIVIDE ( [Receita Total], CALCULATE ( [Receita Total], ALLSELECTED () ) )", "0.0%"),
    ("Receita Online %", 'DIVIDE ( CALCULATE ( [Receita Total], dim_canal[canal] = "Online" ), [Receita Total] )', "0.0%"),
    ("Receita Alta Temporada", 'CALCULATE ( [Receita Total], dim_calendario[alta_temporada] = "Sim" )', BRL),
    ("Receita Média Mensal", "DIVIDE ( [Receita Total], DISTINCTCOUNT ( dim_calendario[ano_mes] ) )", BRL),
    (
        "Efeito Alta Temporada",
        'VAR MediaAlta = CALCULATE ( [Receita Média Mensal], dim_calendario[alta_temporada] = "Sim" )\n'
        'VAR MediaResto = CALCULATE ( [Receita Média Mensal], dim_calendario[alta_temporada] = "Não" )\n'
        "RETURN DIVIDE ( MediaAlta, MediaResto )",
        '0.00"x"',
    ),
]


def guid(chave: str) -> str:
    """GUID determinístico: rodar o gerador duas vezes produz arquivos idênticos."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"analise-vendas/{chave}"))


# --------------------------------------------------------------------------------------
# Modelo semântico (TMDL)
# --------------------------------------------------------------------------------------
def consulta_m(tabela: str, colunas: list[tuple]) -> str:
    tipos = ", ".join(f'{{"{c[0]}", {c[2]}}}' for c in colunas)
    return (
        "let\n"
        f'    Fonte = Csv.Document(File.Contents(Pasta & "\\{tabela}.csv"), '
        "[Delimiter = Separador, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n"
        "    Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true]),\n"
        f"    Tipos = Table.TransformColumnTypes(Cabecalho, {{{tipos}}}, Cultura)\n"
        "in\n"
        "    Tipos"
    )


def tmdl_tabela(nome: str, colunas: list[tuple]) -> str:
    linhas = [f"table {nome}", f"\tlineageTag: {guid('tabela/' + nome)}"]
    if nome == "dim_calendario":
        linhas.append("\tdataCategory: Time")
    linhas.append("")
    for col, tipo, _tipo_m, resumo, extras in colunas:
        linhas += [f"\tcolumn {col}", f"\t\tdataType: {tipo}", f"\t\tlineageTag: {guid(f'coluna/{nome}/{col}')}"]
        if extras.get("isKey"):
            linhas.append("\t\tisKey")
        if "formatString" in extras:
            linhas.append(f"\t\tformatString: {extras['formatString']}")
        linhas += [f"\t\tsummarizeBy: {resumo}", f"\t\tsourceColumn: {col}"]
        if "sortByColumn" in extras:
            linhas.append(f"\t\tsortByColumn: {extras['sortByColumn']}")
        linhas.append("")
    m = consulta_m(nome, colunas).replace("\n", "\n\t\t\t\t")
    linhas += [f"\tpartition {nome} = m", "\t\tmode: import", "\t\tsource =", f"\t\t\t\t{m}", ""]
    return "\n".join(linhas)


def tmdl_medidas() -> str:
    linhas = ["table Medidas", f"\tlineageTag: {guid('tabela/Medidas')}", ""]
    for nome, dax, formato in MEDIDAS:
        expr = dax.replace("\n", "\n\t\t\t\t")
        if "\n" in dax:
            linhas += [f"\tmeasure '{nome}' = ```", f"\t\t\t\t{expr}", "\t\t\t\t```"]
        else:
            linhas.append(f"\tmeasure '{nome}' = {dax}")
        linhas += [f"\t\tformatString: {formato}", f"\t\tlineageTag: {guid('medida/' + nome)}", ""]
    linhas += [
        "\tcolumn Medidas",
        "\t\tisHidden",
        f"\t\tlineageTag: {guid('coluna/Medidas/Medidas')}",
        "\t\tsummarizeBy: none",
        "\t\tsourceColumn: [Medidas]",
        "",
        "\tpartition Medidas = calculated",
        "\t\tmode: import",
        '\t\tsource = ROW ( "Medidas", 1 )',
        "",
    ]
    return "\n".join(linhas)


def tmdl_relacionamentos() -> str:
    blocos = []
    for nome, t_de, c_de, t_para, c_para in RELACIONAMENTOS:
        blocos.append(
            f"relationship {guid('rel/' + nome)}\n\tfromColumn: {t_de}.{c_de}\n\ttoColumn: {t_para}.{c_para}\n"
        )
    return "\n".join(blocos)


def tmdl_expressoes(pasta: Path) -> str:
    def param(nome: str, valor: str) -> str:
        return (
            f'expression {nome} = "{valor}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
            f"\tlineageTag: {guid('expr/' + nome)}\n"
            "\tqueryGroup: Parametros\n"
        )

    return "\n".join([param("Pasta", str(pasta)), param("Separador", ";"), param("Cultura", "pt-BR")])


def tmdl_modelo() -> str:
    refs = "\n".join(f"ref table {t}" for t in [*TABELAS, "Medidas"])
    return (
        "model Model\n\tculture: pt-BR\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tdiscourageImplicitMeasures\n\tsourceQueryCulture: pt-BR\n\n"
        "queryGroup Parametros\n\n" + refs + "\n"
    )


# --------------------------------------------------------------------------------------
# Relatório (PBIR): páginas e visuais
# --------------------------------------------------------------------------------------
def coluna(tabela: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": tabela}}, "Property": prop}}


def medida(prop: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": prop}}


def projecao(campo: dict) -> dict:
    if "Measure" in campo:
        ent, prop = campo["Measure"]["Expression"]["SourceRef"]["Entity"], campo["Measure"]["Property"]
    else:
        ent, prop = campo["Column"]["Expression"]["SourceRef"]["Entity"], campo["Column"]["Property"]
    return {"field": campo, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}


def visual(
    nome: str, tipo: str, x: int, y: int, w: int, h: int, papeis: dict, titulo: str | None = None, objetos: dict | None = None
) -> dict:
    corpo = {
        "visualType": tipo,
        "query": {"queryState": {p: {"projections": [projecao(c) for c in campos]} for p, campos in papeis.items()}},
        "drillFilterOtherVisuals": True,
    }
    if objetos:
        corpo["objects"] = objetos
    if titulo:
        corpo["visualContainerObjects"] = {
            "title": [
                {
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "true"}}},
                        "text": {"expr": {"Literal": {"Value": "'" + titulo.replace("'", "''") + "'"}}},
                    }
                }
            ]
        }
    return {
        "$schema": S_VISUAL,
        "name": nome,
        "position": {"x": x, "y": y, "z": 0, "height": h, "width": w},
        "visual": corpo,
    }


def cartao(nome, x, y, w, h, med):
    return visual(nome, "card", x, y, w, h, {"Values": [medida(med)]})


def segmentacao(nome, x, y, w, h, tabela, col, titulo):
    # modo "Dropdown": a segmentação ocupa uma linha e abre a lista completa ao clicar
    dropdown = {"data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}}}]}
    return visual(nome, "slicer", x, y, w, h, {"Values": [coluna(tabela, col)]}, titulo, dropdown)


PAGINAS: list[tuple[str, str, list[dict]]] = [
    (
        "pagina_visao_geral",
        "Visão geral",
        [
            segmentacao("seg_ano", 20, 16, 200, 70, "dim_calendario", "ano", "Ano"),
            segmentacao("seg_regiao", 236, 16, 200, 70, "dim_regiao", "regiao", "Região"),
            segmentacao("seg_canal", 452, 16, 200, 70, "dim_canal", "canal", "Canal"),
            cartao("card_receita", 20, 100, 300, 100, "Receita Total"),
            cartao("card_vendas", 340, 100, 300, 100, "Vendas"),
            cartao("card_ticket", 660, 100, 300, 100, "Ticket Médio"),
            cartao("card_yoy", 980, 100, 280, 100, "Crescimento YoY %"),
            visual(
                "linha_mensal", "lineChart", 20, 220, 780, 480,
                {"Category": [coluna("dim_calendario", "ano_mes")], "Y": [medida("Receita Total"), medida("Receita Ano Anterior")]},
                "Receita por mês, com o mesmo período do ano anterior",
            ),
            visual(
                "barra_categoria", "clusteredBarChart", 820, 220, 440, 480,
                {"Category": [coluna("dim_produto", "categoria")], "Y": [medida("Receita Total")]},
                "Receita por categoria",
            ),
        ],
    ),
    (
        "pagina_regioes_canais",
        "Regiões e canais",
        [
            cartao("card_online", 20, 20, 300, 100, "Receita Online %"),
            visual(
                "barra_regiao", "clusteredBarChart", 20, 140, 620, 560,
                {"Category": [coluna("dim_regiao", "regiao")], "Y": [medida("Receita Total")]},
                "Receita por região",
            ),
            visual(
                "colunas_canal", "hundredPercentStackedColumnChart", 660, 140, 600, 560,
                {"Category": [coluna("dim_calendario", "ano")], "Series": [coluna("dim_canal", "canal")], "Y": [medida("Receita Total")]},
                "Participação de cada canal na receita, por ano",
            ),
        ],
    ),
    (
        "pagina_sazonalidade",
        "Sazonalidade",
        [
            cartao("card_efeito", 20, 20, 300, 100, "Efeito Alta Temporada"),
            cartao("card_alta", 340, 20, 460, 100, "Receita Alta Temporada"),
            visual(
                "colunas_mes", "clusteredColumnChart", 20, 140, 780, 560,
                {"Category": [coluna("dim_calendario", "mes_nome")], "Y": [medida("Receita Média Mensal")]},
                "Receita média por mês do ano",
            ),
            visual(
                "tabela_categoria", "tableEx", 820, 140, 440, 560,
                {"Values": [coluna("dim_produto", "categoria"), medida("Receita Total"), medida("Participação na Receita %")]},
                "Receita e participação por categoria",
            ),
        ],
    ),
]


# --------------------------------------------------------------------------------------
# Gravação dos arquivos
# --------------------------------------------------------------------------------------
def gravar(caminho: Path, conteudo: str | dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(conteudo, ensure_ascii=False, indent=2) if isinstance(conteudo, dict) else conteudo
    caminho.write_text(texto.rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def gerar(destino: Path = SAIDA_DIR, pasta_csv: Path = CSV_DIR) -> list[Path]:
    """Gera o projeto PBIP em `destino` e devolve os arquivos gravados."""
    modelo = destino / f"{NOME}.SemanticModel"
    relatorio = destino / f"{NOME}.Report"
    escritos: list[Path] = []

    def w(caminho: Path, conteudo) -> None:
        gravar(caminho, conteudo)
        escritos.append(caminho)

    w(destino / f"{NOME}.pbip", {"version": "1.0", "artifacts": [{"report": {"path": f"{NOME}.Report"}}], "settings": {"enableAutoRecovery": True}})

    w(modelo / "definition.pbism", {"version": "4.2", "settings": {}})
    w(modelo / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    w(modelo / "definition" / "model.tmdl", tmdl_modelo())
    w(modelo / "definition" / "expressions.tmdl", tmdl_expressoes(pasta_csv))
    w(modelo / "definition" / "relationships.tmdl", tmdl_relacionamentos())
    for nome, colunas in TABELAS.items():
        w(modelo / "definition" / "tables" / f"{nome}.tmdl", tmdl_tabela(nome, colunas))
    w(modelo / "definition" / "tables" / "Medidas.tmdl", tmdl_medidas())

    w(relatorio / "definition.pbir", {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOME}.SemanticModel"}}})
    defn = relatorio / "definition"
    w(defn / "version.json", {"$schema": S_VERSAO, "version": "2.0.0"})
    w(
        defn / "report.json",
        {
            "$schema": S_RELATORIO,
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU10",
                    "reportVersionAtImport": {"visual": "1.8.50", "page": "1.3.50", "report": "2.0.50"},
                    "type": "SharedResources",
                }
            },
        },
    )
    w(defn / "pages" / "pages.json", {"$schema": S_PAGINAS, "pageOrder": [p[0] for p in PAGINAS], "activePageName": PAGINAS[0][0]})
    for nome_pagina, titulo, visuais in PAGINAS:
        w(
            defn / "pages" / nome_pagina / "page.json",
            {"$schema": S_PAGINA, "name": nome_pagina, "displayName": titulo, "displayOption": "FitToPage", "height": 720, "width": 1280},
        )
        for v in visuais:
            w(defn / "pages" / nome_pagina / "visuals" / v["name"] / "visual.json", v)
    return escritos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--csv", type=Path, default=CSV_DIR, help="pasta com os CSVs (padrão: data/powerbi)")
    args = parser.parse_args()
    if not (args.csv / "fato_vendas.csv").exists():
        raise SystemExit("CSVs não encontrados. Rode antes: python src/exportar_powerbi.py")
    arquivos = gerar(SAIDA_DIR, args.csv.resolve())
    print(f"Projeto Power BI gerado: {SAIDA_DIR / (NOME + '.pbip')} ({len(arquivos)} arquivos)")
    print("Abra o arquivo .pbip no Power BI Desktop.")


if __name__ == "__main__":
    main()
