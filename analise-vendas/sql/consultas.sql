-- Consultas SQL de análise de negócio sobre a tabela `vendas`
-- (gerada por src/carregar_sqlite.py a partir de data/vendas.csv).
--
-- Rodar com: sqlite3 data/vendas.db < sql/consultas.sql
-- ou copiar/colar cada bloco em um cliente SQL de preferência.

-- 1) Receita total e número de vendas por mês
SELECT
    strftime('%Y-%m', data) AS mes,
    COUNT(*) AS qtd_vendas,
    ROUND(SUM(receita), 2) AS receita_total,
    ROUND(AVG(receita), 2) AS ticket_medio
FROM vendas
GROUP BY mes
ORDER BY mes;

-- 2) Top 5 produtos por receita total
SELECT
    produto,
    categoria,
    COUNT(*) AS qtd_vendas,
    SUM(quantidade) AS unidades_vendidas,
    ROUND(SUM(receita), 2) AS receita_total
FROM vendas
GROUP BY produto, categoria
ORDER BY receita_total DESC
LIMIT 5;

-- 3) Receita por categoria, com participação percentual do total
SELECT
    categoria,
    ROUND(SUM(receita), 2) AS receita_total,
    ROUND(100.0 * SUM(receita) / (SELECT SUM(receita) FROM vendas), 2) AS pct_do_total
FROM vendas
GROUP BY categoria
ORDER BY receita_total DESC;

-- 4) Receita por região
SELECT
    regiao,
    COUNT(*) AS qtd_vendas,
    ROUND(SUM(receita), 2) AS receita_total,
    ROUND(AVG(receita), 2) AS ticket_medio
FROM vendas
GROUP BY regiao
ORDER BY receita_total DESC;

-- 5) Comparação Online vs Loja Física, por ano
SELECT
    strftime('%Y', data) AS ano,
    canal,
    COUNT(*) AS qtd_vendas,
    ROUND(SUM(receita), 2) AS receita_total
FROM vendas
GROUP BY ano, canal
ORDER BY ano, canal;

-- 6) Efeito da Black Friday / Natal: receita de nov/dez vs. meses regulares
SELECT
    CASE WHEN strftime('%m', data) IN ('11', '12') THEN 'Nov/Dez (alta temporada)'
         ELSE 'Demais meses' END AS periodo,
    ROUND(AVG(receita), 2) AS ticket_medio,
    ROUND(SUM(receita) / COUNT(DISTINCT strftime('%Y-%m', data)), 2) AS receita_media_mensal
FROM vendas
GROUP BY periodo;

-- 7) Categoria mais vendida em cada região (top 1 por receita)
SELECT regiao, categoria, receita_total FROM (
    SELECT
        regiao,
        categoria,
        SUM(receita) AS receita_total,
        RANK() OVER (PARTITION BY regiao ORDER BY SUM(receita) DESC) AS posicao
    FROM vendas
    GROUP BY regiao, categoria
)
WHERE posicao = 1
ORDER BY receita_total DESC;

-- 8) Crescimento ano a ano (YoY) da receita total
SELECT
    strftime('%Y', data) AS ano,
    ROUND(SUM(receita), 2) AS receita_total
FROM vendas
GROUP BY ano
ORDER BY ano;
