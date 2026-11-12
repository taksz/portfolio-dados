# Análise de Vendas de E-commerce (Python + SQL)

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/pandas-2.0%2B-150458?style=flat&logo=pandas&logoColor=white" alt="pandas" />
  <img src="https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/tests-pytest-0A9EDC?style=flat&logo=pytest&logoColor=white" alt="pytest" />
</p>

Projeto de análise de dados de ponta a ponta: geração de um dataset sintético e reprodutível de vendas de e-commerce, carga em banco SQL, consultas de negócio e análise exploratória com pandas, com gráficos e conclusões.

> **Por que dados sintéticos?** Para um projeto público, gerar os próprios dados (com seed fixa, em `src/gerar_dados.py`) evita problemas de licença/privacidade de datasets de terceiros e permite controlar propositalmente padrões realistas (sazonalidade de Black Friday/Natal, crescimento do canal online) para a análise ter algo relevante a descobrir.

## Estrutura

```
analise-vendas/
├── src/
│   ├── gerar_dados.py      # Gera data/vendas.csv (7.618 registros, 2023-2024)
│   ├── carregar_sqlite.py  # Carrega o CSV em data/vendas.db (SQLite)
│   └── analise.py          # Análise com pandas + geração dos gráficos em imgs/
├── sql/
│   └── consultas.sql       # 8 consultas de negócio comentadas
├── imgs/                   # Gráficos gerados (PNG)
├── tests/                  # Testes pytest (geração de dados + métricas)
└── requirements.txt
```

## Como reproduzir

```bash
pip install -r requirements.txt

python src/gerar_dados.py       # gera data/vendas.csv
python src/carregar_sqlite.py   # gera data/vendas.db a partir do CSV
python src/analise.py           # roda a análise e regrava os gráficos em imgs/

pytest tests/ -v                # 13 testes
```

As consultas de `sql/consultas.sql` podem ser rodadas com qualquer cliente SQLite sobre `data/vendas.db`.

## Principais achados

*(números reais, gerados pela execução de `src/analise.py` sobre os dados sintéticos de `src/gerar_dados.py`)*

- **Receita total (2023-2024): R$ 4.834.928,89**, em 7.618 vendas.
- **Crescimento ano a ano de 17,0%**: de R$ 2.227.720,35 em 2023 para R$ 2.607.208,54 em 2024.
- **Eletrônicos é a categoria líder**, respondendo por **51,5%** de toda a receita — bem à frente de Esporte (29,6%).
- **Sudeste concentra 44,1%** da receita, seguido por Nordeste (22,2%) e Sul (18,3%) — reflexo dos pesos populacionais usados na geração dos dados.
- **Efeito Black Friday / Natal é nítido**: a receita média mensal em novembro/dezembro (R$ 363.511,52) é **2,15x maior** que nos demais meses (R$ 169.044,14).
- **O canal Online cresceu de participação**: em 2024 já respondia por **66,6%** da receita, ante um cenário mais equilibrado em 2023 — a loja física inclusive recuou em termos absolutos.

### Receita mensal (2023-2024)

![Receita mensal](imgs/receita_mensal.png)

Os dois picos (novembro de 2023 e de 2024) confirmam visualmente o efeito de alta temporada, com queda acentuada em janeiro/fevereiro — período de retração pós-festas.

### Receita por categoria

![Receita por categoria](imgs/receita_por_categoria.png)

### Participação por região

![Receita por região](imgs/receita_por_regiao.png)

### Online vs. Loja Física, por ano

![Receita por canal](imgs/receita_por_canal.png)

## Consultas SQL (`sql/consultas.sql`)

8 consultas de negócio, entre elas:

1. Receita e ticket médio por mês
2. Top 5 produtos por receita
3. Receita por categoria, com % de participação
4. Receita por região
5. Online vs. Loja Física, por ano
6. Efeito da alta temporada (Nov/Dez) no ticket médio
7. Categoria líder em cada região (usando `RANK() OVER (PARTITION BY ...)`)
8. Crescimento ano a ano da receita total

## Testes

13 testes com `pytest`, cobrindo:
- reprodutibilidade da geração de dados (mesma seed → mesmo resultado)
- validade dos dados gerados (datas no período, categorias/produtos válidos, receita consistente)
- corretude dos cálculos de métricas de negócio usados no relatório

## Próximos passos

- [ ] Dashboard interativo em Power BI a partir de `data/vendas.csv`
- [ ] Versão com dados reais de uma API pública (ex.: IBGE, dados.gov.br)
