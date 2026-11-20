"""Dashboard comercial na web (Streamlit + Plotly).

Versão online do dashboard do Power BI (powerbi/AnaliseVendas.pbip): os mesmos
indicadores e filtros, calculados por dashboard/metricas.py.

Rodar localmente (a partir da pasta analise-vendas):
    pip install -r requirements-dashboard.txt
    streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import metricas  # mesmo diretório deste arquivo

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from gerar_dados import SEED, gerar_vendas  # noqa: E402

# Cores fixas por entidade (paleta validada para daltonismo): a cor segue o
# item, não a posição, então um filtro nunca "repinta" as séries que sobram.
AZUL, LARANJA, CINZA = "#2a78d6", "#eb6834", "#c3c2b7"
COR_ANO = {2023: LARANJA, 2024: AZUL}
COR_CANAL = {"Online": AZUL, "Loja Física": LARANJA}

st.set_page_config(page_title="Dashboard comercial", page_icon="📊", layout="wide")


# --------------------------------------------------------------------------
# Dados
# --------------------------------------------------------------------------
@st.cache_data
def carregar_dados() -> pd.DataFrame:
    """Lê data/vendas.csv; se não existir (ex.: servidor novo), gera a mesma base em memória."""
    csv = RAIZ / "data" / "vendas.csv"
    df = pd.read_csv(csv) if csv.exists() else gerar_vendas(np.random.default_rng(SEED))
    return metricas.preparar(df)


# --------------------------------------------------------------------------
# Formatação no padrão brasileiro
# --------------------------------------------------------------------------
def numero_br(valor: float, casas: int = 2) -> str:
    """1234567.891 -> '1.234.567,89'."""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def reais(valor) -> str:
    return "—" if valor is None else f"R$ {numero_br(valor)}"


def reais_compacto(valor) -> str:
    """Valor curto para os cartões: 4429491.93 -> 'R$ 4,43 mi' (cabe em telas estreitas)."""
    if valor is None:
        return "—"
    if abs(valor) >= 1_000_000:
        return f"R$ {numero_br(valor / 1_000_000)} mi"
    if abs(valor) >= 1_000:
        return f"R$ {numero_br(valor / 1_000, 1)} mil"
    return reais(valor)


def percentual(valor) -> str:
    return "—" if valor is None else f"{numero_br(valor, 1)}%"


def estilizar(fig: go.Figure, altura: int = 360) -> go.Figure:
    """Visual comum a todos os gráficos: fundo limpo, grade discreta, separadores BR."""
    fig.update_layout(
        template="plotly_white", height=altura, separators=",.",
        margin=dict(l=10, r=10, t=80, b=10), barcornerradius=4,
        # legenda numa linha própria, entre o título e o gráfico: não encosta no
        # título nem nos rótulos do eixo, inclusive em tela de celular
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        hoverlabel=dict(bgcolor="white", font_size=13),
        font=dict(family="Inter, Segoe UI, sans-serif", size=13, color="#0b0b0b"),
    )
    fig.update_xaxes(showgrid=False, linecolor="#d9d8d3")
    fig.update_yaxes(gridcolor="#eeede9", zeroline=False)
    return fig


def eixo_x_barras(fig: go.Figure, maximo: float) -> None:
    """Eixo de valores das barras horizontais: poucos rótulos e folga para o texto de % à direita."""
    fig.update_xaxes(tickprefix="R$ ", tickformat=",.0f", nticks=4, tickangle=0,
                     showgrid=True, gridcolor="#eeede9", range=[0, maximo * 1.2])


def mostrar(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# --------------------------------------------------------------------------
# Filtros (barra lateral)
# --------------------------------------------------------------------------
base = carregar_dados()

st.sidebar.header("Filtros")
st.sidebar.caption("Deixe um filtro vazio para considerar todos os valores.")
anos = st.sidebar.multiselect("Ano", sorted(base["ano"].unique()), placeholder="Todos")
regioes = st.sidebar.multiselect("Região", sorted(base["regiao"].unique()), placeholder="Todas")
canais = st.sidebar.multiselect("Canal", sorted(base["canal"].unique()), placeholder="Todos")
categorias = st.sidebar.multiselect("Categoria", sorted(base["categoria"].unique()), placeholder="Todas")
df = metricas.filtrar(base, anos, regioes, canais, categorias)

# --------------------------------------------------------------------------
# Cabeçalho e cartões
# --------------------------------------------------------------------------
st.title("Dashboard comercial")
st.caption("E-commerce fictício · vendas de 2023 e 2024 · **dados sintéticos** gerados para o portfólio "
           "(sazonalidade calibrada com o IBGE). Nenhum número representa uma empresa real.")

if df.empty:
    st.warning("Nenhuma venda com essa combinação de filtros. Remova algum filtro na barra lateral.")
    st.stop()

ind = metricas.indicadores(df)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Receita", reais_compacto(ind["receita"]), help=f"Valor exato: {reais(ind['receita'])}")
c2.metric("Vendas", numero_br(ind["vendas"], 0))
c3.metric("Ticket médio", reais(ind["ticket_medio"]))
c4.metric("Crescimento sobre o ano anterior", percentual(ind["crescimento_pct"]),
          help="Receita do último ano filtrado comparada à do ano anterior. "
               "Fica vazio quando o ano anterior não está no filtro.")

aba_geral, aba_produtos, aba_regioes, aba_sazonal = st.tabs(
    ["Visão geral", "Categorias e produtos", "Regiões e canais", "Sazonalidade"])

# --------------------------------------------------------------------------
# Visão geral
# --------------------------------------------------------------------------
with aba_geral:
    col_a, col_b = st.columns([3, 2])

    mensal = metricas.receita_mensal_por_ano(df)
    fig = go.Figure()
    for ano in mensal.columns:
        fig.add_scatter(x=mensal.index, y=mensal[ano], name=str(ano), mode="lines+markers",
                        line=dict(width=2, color=COR_ANO.get(ano, CINZA)), marker=dict(size=8),
                        hovertemplate=f"{ano} · %{{x}}<br>R$ %{{y:,.2f}}<extra></extra>")
    fig.update_layout(title="Receita por mês, comparando os anos", hovermode="x unified")
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f")
    with col_a:
        mostrar(estilizar(fig))

    por_categoria = metricas.receita_por(df, "categoria").sort_values("receita")
    fig = go.Figure(go.Bar(
        x=por_categoria["receita"], y=por_categoria.index, orientation="h", marker_color=AZUL,
        text=[percentual(p) for p in por_categoria["pct_receita"]], textposition="outside",
        cliponaxis=False, customdata=por_categoria["vendas"],
        hovertemplate="%{y}<br>R$ %{x:,.2f} · %{customdata} vendas<extra></extra>"))
    fig.update_layout(title="Receita por categoria (% do total)")
    eixo_x_barras(fig, por_categoria["receita"].max())
    with col_b:
        mostrar(estilizar(fig))

    with st.expander("Ver tabela: receita por mês e ano"):
        st.dataframe(mensal.style.format(lambda v: reais(v) if pd.notna(v) else "—"), width="stretch")

# --------------------------------------------------------------------------
# Categorias e produtos
# --------------------------------------------------------------------------
with aba_produtos:
    col_a, col_b = st.columns(2)

    top = metricas.top_produtos(df, 10).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top["receita"], y=top["produto"] + " (" + top["categoria"] + ")", orientation="h",
        marker_color=AZUL, customdata=top["vendas"],
        hovertemplate="%{y}<br>R$ %{x:,.2f} · %{customdata} vendas<extra></extra>"))
    fig.update_layout(title="Top 10 produtos por receita")
    eixo_x_barras(fig, top["receita"].max())
    with col_a:
        mostrar(estilizar(fig, 420))

    tabela_cat = metricas.receita_por(df, "categoria")
    tabela_cat["crescimento"] = metricas.crescimento_por_categoria(df)
    tabela_ticket = tabela_cat.sort_values("ticket_medio")
    fig = go.Figure(go.Bar(
        x=tabela_ticket["ticket_medio"], y=tabela_ticket.index, orientation="h", marker_color=AZUL,
        hovertemplate="%{y}<br>Ticket médio: R$ %{x:,.2f}<extra></extra>"))
    fig.update_layout(title="Ticket médio por categoria")
    eixo_x_barras(fig, tabela_ticket["ticket_medio"].max())
    with col_b:
        mostrar(estilizar(fig, 420))

    st.caption("As categorias vendem um número parecido de vezes; o que separa a receita delas é o ticket médio.")
    st.dataframe(pd.DataFrame({
        "Receita": tabela_cat["receita"].map(reais),
        "% da receita": tabela_cat["pct_receita"].map(percentual),
        "Vendas": tabela_cat["vendas"].map(lambda v: numero_br(v, 0)),
        "Ticket médio": tabela_cat["ticket_medio"].map(reais),
        "Crescimento no último ano": tabela_cat["crescimento"].map(lambda v: percentual(v) if pd.notna(v) else "—"),
    }), width="stretch")

# --------------------------------------------------------------------------
# Regiões e canais
# --------------------------------------------------------------------------
with aba_regioes:
    col_a, col_b = st.columns(2)

    por_regiao = metricas.receita_por(df, "regiao").sort_values("receita")
    fig = go.Figure(go.Bar(
        x=por_regiao["receita"], y=por_regiao.index, orientation="h", marker_color=AZUL,
        text=[percentual(p) for p in por_regiao["pct_receita"]], textposition="outside", cliponaxis=False,
        customdata=np.stack([por_regiao["vendas"], por_regiao["ticket_medio"]], axis=-1),
        hovertemplate="%{y}<br>R$ %{x:,.2f}<br>%{customdata[0]} vendas · ticket R$ %{customdata[1]:,.2f}<extra></extra>"))
    fig.update_layout(title="Receita por região (% do total)")
    eixo_x_barras(fig, por_regiao["receita"].max())
    with col_a:
        mostrar(estilizar(fig))

    canal_ano = metricas.participacao_canal_por_ano(df)
    fig = go.Figure()
    for canal in [c for c in COR_CANAL if c in canal_ano.columns]:
        fig.add_bar(x=canal_ano.index.astype(str), y=canal_ano[canal], name=canal, marker_color=COR_CANAL[canal],
                    hovertemplate=f"{canal} · %{{x}}<br>R$ %{{y:,.2f}}<extra></extra>")
    fig.update_layout(title="Receita por canal e ano", barmode="group", bargap=0.35, bargroupgap=0.05)
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f")
    with col_b:
        mostrar(estilizar(fig))

    colunas_pct = st.columns(len(canal_ano))
    for coluna, (ano, linha) in zip(colunas_pct, canal_ano.iterrows()):
        coluna.metric(f"Participação do Online em {ano}", percentual(linha["pct_online"]))

# --------------------------------------------------------------------------
# Sazonalidade
# --------------------------------------------------------------------------
with aba_sazonal:
    efeito = metricas.efeito_alta_temporada(df)
    st.metric("Efeito de alta temporada (Nov/Dez × demais meses)",
              "—" if efeito is None else f"{numero_br(efeito)}x",
              help="Receita média mensal de novembro e dezembro dividida pela receita média dos outros meses.")

    media_mes = metricas.receita_media_por_mes_do_ano(df)
    alta = media_mes.index.isin(["Nov", "Dez"])
    fig = go.Figure()
    fig.add_bar(x=media_mes.index[~alta], y=media_mes[~alta], name="Demais meses", marker_color=AZUL,
                hovertemplate="%{x}<br>Média: R$ %{y:,.2f}<extra></extra>")
    fig.add_bar(x=media_mes.index[alta], y=media_mes[alta], name="Alta temporada (Nov/Dez)",
                marker_color=LARANJA, hovertemplate="%{x}<br>Média: R$ %{y:,.2f}<extra></extra>")
    fig.update_layout(title="Receita média por mês do ano", bargap=0.3)
    fig.update_xaxes(categoryorder="array", categoryarray=metricas.NOMES_MESES)
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f")
    mostrar(estilizar(fig))
    st.caption("A sazonalidade da base foi calibrada com a Pesquisa Mensal de Comércio do IBGE: "
               "dezembro é o mês mais forte, e o pico de fim de ano é moderado (cerca de 25% acima da média).")

st.divider()
st.caption("Código, consultas SQL, notebook e versão em Power BI: "
           "[github.com/taksz/portfolio-dados](https://github.com/taksz/portfolio-dados/tree/main/analise-vendas)")
