# Roteiro: dashboard de vendas no Power BI

Este roteiro leva do `vendas.csv` a um dashboard interativo no **Power BI Desktop** (gratuito, Windows). O arquivo `.pbix` não está no repositório porque só pode ser criado dentro do Power BI Desktop; aqui estão os dados prontos, as medidas e o desenho das páginas.

## 1. Gerar os dados do modelo estrela

Na pasta `analise-vendas`:

```bash
python src/gerar_dados.py          # gera data/vendas.csv
python src/exportar_powerbi.py     # gera data/powerbi/*.csv (formato brasileiro)
```

Se o seu Power BI estiver em inglês (separador `,` e ponto decimal), use `python src/exportar_powerbi.py --formato us`.

Tabelas geradas em `data/powerbi/`:

| Arquivo | Conteúdo |
|---|---|
| `fato_vendas.csv` | uma linha por venda: `id_venda`, `data`, chaves das dimensões, `quantidade`, `preco_unitario`, `receita` |
| `dim_calendario.csv` | um dia por linha, com ano, trimestre, mês, dia da semana e `alta_temporada` (nov/dez) |
| `dim_produto.csv` | `id_produto`, `produto`, `categoria` |
| `dim_regiao.csv` | `id_regiao`, `regiao` |
| `dim_canal.csv` | `id_canal`, `canal` |

## Caminho rápido: scripts prontos

Se preferir colar scripts em vez de seguir os passos 2 a 4 na mão:

1. **Importação:** no Power BI Desktop, abra o Power Query (**Página Inicial > Transformar dados**) e crie as consultas de [`importar_dados.m`](importar_dados.m): três parâmetros (`Pasta`, `Separador`, `Cultura`) e uma consulta para cada tabela. Troque o valor de `Pasta` pelo caminho da sua pasta `data\powerbi` (para arquivos `--formato us`, use `,` e `en-US`). Depois, **Fechar e aplicar**.
2. **Relacionamentos e medidas:** abra a visão **TMDL** do Desktop, cole todo o [`modelo.tmdl`](modelo.tmdl) e aplique. Ele cria os 4 relacionamentos e as 12 medidas (as mesmas de `medidas.dax`) numa tabela `Medidas`.
3. **Dois ajustes manuais** (o script não faz de propósito): marcar `dim_calendario` como **tabela de datas** e classificar `mes_nome` por `mes_num`.
4. Siga para o passo 5 (páginas) e o passo 6 (conferência dos números).

Os scripts seguem a sintaxe documentada do Power Query e do TMDL, mas **não foram executados no Power BI Desktop** pelo autor. O que foi verificado automaticamente (`tests/test_powerbi_scripts.py`): os nomes de tabelas e colunas dos scripts batem com o que o `exportar_powerbi.py` exporta, os relacionamentos ligam colunas existentes e com chave única no lado "um", e as 12 medidas do TMDL são as mesmas do `medidas.dax`. Se algo der erro no Desktop, os passos 2 a 4 acima fazem o mesmo manualmente.

## 2. Importar no Power BI Desktop

1. **Obter dados > Texto/CSV** e importe os 5 arquivos (pode selecionar a pasta inteira em **Obter dados > Pasta**).
2. No Editor do Power Query, confira os tipos: `data` como **Data**, `receita` e `preco_unitario` como **Número decimal**, chaves (`id_*`) como **Número inteiro**. Se os valores decimais aparecerem errados, use **Alterar tipo > Usando localidade** e escolha *Português (Brasil)* (arquivos padrão) ou *Inglês (Estados Unidos)* (arquivos com `--formato us`).
3. **Fechar e aplicar**.

## 3. Relacionamentos (visão de Modelo)

Todos de *muitos para um*, com filtro em uma direção (da dimensão para a fato):

- `dim_calendario[data]` 1 → * `fato_vendas[data]`
- `dim_produto[id_produto]` 1 → * `fato_vendas[id_produto]`
- `dim_regiao[id_regiao]` 1 → * `fato_vendas[id_regiao]`
- `dim_canal[id_canal]` 1 → * `fato_vendas[id_canal]`

Depois, selecione `dim_calendario` e use **Ferramentas de tabela > Marcar como tabela de datas** (coluna `data`). Isso é necessário para as medidas de comparação com o ano anterior.

Dica: oculte as colunas de chave (`id_*`) e a `fato_vendas[receita]` na visão de relatório, para que as pessoas usem as medidas.

## 4. Medidas

Abra [`medidas.dax`](medidas.dax) e crie cada medida em **Modelagem > Nova medida** (cole o bloco, uma medida por vez). Coloque-as numa tabela própria (por exemplo, "Medidas") se quiser o modelo organizado.

## 5. Páginas sugeridas

**Página 1 — Visão geral**
- Cartões: `Receita Total`, `Vendas`, `Ticket Médio`, `Crescimento YoY %`.
- Gráfico de linhas: `Receita Total` por `dim_calendario[ano_mes]`, com `Receita Ano Anterior` como segunda linha (mostra o pico de nov/dez).
- Gráfico de barras: `Receita Total` por `dim_produto[categoria]`.
- Segmentações (filtros): `ano`, `dim_regiao[regiao]` e `dim_canal[canal]`.

**Página 2 — Regiões e canais**
- Mapa ou barras: `Receita Total` por região, com `Participação na Receita %` nas dicas de ferramenta.
- Colunas empilhadas 100%: `Receita Total` por `ano`, legenda `dim_canal[canal]` (mostra a perda de peso da loja física).
- Cartão: `Receita Online %`.

**Página 3 — Sazonalidade**
- Colunas: `Receita Média Mensal` por `dim_calendario[mes_nome]` (ordenar por `mes_num`).
- Cartão: `Efeito Alta Temporada` (compare com o 1,26x citado no README).
- Matriz: `dim_produto[categoria]` nas linhas, `ano` nas colunas, `Receita Total` nos valores.

## 6. Conferir se os números batem

Com nenhum filtro aplicado, o dashboard deve mostrar os mesmos valores do README:

- `Receita Total` = **R$ 4.429.491,93** e `Vendas` = **6.655**.
- Crescimento de 2024 sobre 2023 = **19,8%**.

Se os valores não baterem, o mais comum é o separador decimal importado errado (passo 2) ou a tabela de calendário não marcada como tabela de datas (passo 3).

## 7. Compartilhar

Salve o `.pbix` e tire capturas de cada página (**Arquivo > Exportar > PDF**, ou captura de tela). Coloque as imagens em `imgs/` e referencie no README do projeto.
