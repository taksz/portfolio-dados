# Portfólio de Dados

<p align="left">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/SQL-4479A1?style=flat&logo=postgresql&logoColor=white" alt="SQL" />
  <img src="https://img.shields.io/badge/pandas-150458?style=flat&logo=pandas&logoColor=white" alt="pandas" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/scikit--learn-F7931E?style=flat&logo=scikitlearn&logoColor=white" alt="scikit-learn" />
</p>

Projetos de análise de dados, Python, SQL e automação, feitos durante meus estudos de Ciência da Computação na UDF.

## Projetos

1. **[analise-vendas](analise-vendas/)** — Análise de vendas de e-commerce: geração de dataset, carga em SQL (SQLite), consultas de negócio, análise exploratória com pandas em notebook Jupyter, comparação com dados reais do IBGE (API SIDRA) e dashboard em Power BI, com versão web em Streamlit. [Ver README do projeto](analise-vendas/README.md) | [Ver notebook](analise-vendas/notebooks/analise_exploratoria.ipynb) | [Demonstração ao vivo](https://dashboard-vendas-vxtp.onrender.com).
2. **[encurtador-url](encurtador-url/)** — API (FastAPI) de encurtador de URL com analytics: cliques por dia, navegador, sistema operacional e origem, com dashboard, validade e desativação de links e senha opcional. [Ver README do projeto](encurtador-url/README.md) | [Demonstração ao vivo](https://encurtador-url-amgn.onrender.com).
3. **[rastreador-precos](rastreador-precos/)** — Robô de automação que monitora preços (web scraping), guarda o histórico em SQLite, alerta quando o preço cai abaixo de um limite e gera gráficos de evolução. [Ver README do projeto](rastreador-precos/README.md) | [Demonstração ao vivo](https://rastreador-precos-4zyj.onrender.com).
4. **[gestor-anuncios](gestor-anuncios/)** — MVP de gestão de anúncios de veículos para revendas: arquitetura de adaptadores por plataforma, histórico em SQLite, motor de regras que junta o mesmo carro pela placa e classifica cada um (vendido, parado, preço fora da referência FIPE, performando bem) com sugestão de preço, agendador com alertas e painel FastAPI. [Ver README do projeto](gestor-anuncios/README.md) | [Demonstração ao vivo](https://gestor-anuncios-6xy4.onrender.com).
5. **[etl-dados-df](https://github.com/taksz/etl-dados-df)** — Pipeline ETL (extração → transformação → validação → carga) da inflação oficial (IPCA) de Brasília: consome a API pública do IBGE com requests e novas tentativas, achata o JSON, aplica 6 regras de qualidade antes de gravar, carrega em SQLite de forma idempotente e registra tudo com logging. *Repositório próprio.* [Ver repositório](https://github.com/taksz/etl-dados-df).
6. **[modelo-preditivo](https://github.com/taksz/modelo-preditivo)** — Classificação com pandas e scikit-learn sobre a base pública Bank Marketing (UCI): separação treino/teste estratificada, comparação com baseline, validação cruzada, análise de overfitting e remoção de vazamento de dados, tudo em um notebook Jupyter. *Repositório próprio.* [Ver repositório](https://github.com/taksz/modelo-preditivo) | [Ver notebook](https://github.com/taksz/modelo-preditivo/blob/main/notebooks/modelo_preditivo.ipynb).

## Sobre mim

Estudante do 6º semestre de Ciência da Computação (UDF), Brasília - DF. Busco estágio em Dados, Automação, Python ou TI.
