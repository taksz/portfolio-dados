// Power Query (M): importa os 5 CSVs do modelo estrela gerados por src/exportar_powerbi.py.
//
// Como usar, no Power BI Desktop: Página Inicial > Transformar dados (abre o Power Query).
// Para CADA bloco abaixo, crie uma consulta em branco (Nova Fonte > Consulta em Branco),
// abra o Editor Avançado, apague tudo e cole o bloco. Renomeie a consulta com o nome indicado
// no cabeçalho do bloco (ex.: Pasta, Separador, Cultura, fato_vendas...).
// Crie primeiro os três parâmetros (Pasta, Separador, Cultura); depois as cinco tabelas.
// Ao terminar: Fechar e aplicar. Depois siga com modelo.tmdl (relacionamentos e medidas).
//
// Aviso: este script segue a sintaxe padrão do Power Query, mas não foi executado dentro do
// Power BI Desktop pelo autor. Se alguma consulta der erro, o Editor Avançado mostra a linha.

// ============================================================================
// CONSULTA "Pasta"  (texto): caminho da pasta data\powerbi desta máquina
// ============================================================================
"C:\caminho\para\analise-vendas\data\powerbi" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]

// ============================================================================
// CONSULTA "Separador"  (texto): ";" para o formato brasileiro (padrão),
// "," se você exportou com --formato us
// ============================================================================
";" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]

// ============================================================================
// CONSULTA "Cultura"  (texto): "pt-BR" para o formato brasileiro (padrão),
// "en-US" se você exportou com --formato us
// ============================================================================
"pt-BR" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]

// ============================================================================
// CONSULTA "fato_vendas"
// ============================================================================
let
    Fonte = Csv.Document(File.Contents(Pasta & "\fato_vendas.csv"), [Delimiter = Separador, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(Cabecalho, {{"id_venda", Int64.Type}, {"data", type date}, {"id_produto", Int64.Type}, {"id_regiao", Int64.Type}, {"id_canal", Int64.Type}, {"quantidade", Int64.Type}, {"preco_unitario", type number}, {"receita", type number}}, Cultura)
in
    Tipos

// ============================================================================
// CONSULTA "dim_calendario"
// ============================================================================
let
    Fonte = Csv.Document(File.Contents(Pasta & "\dim_calendario.csv"), [Delimiter = Separador, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(Cabecalho, {{"data", type date}, {"ano", Int64.Type}, {"trimestre", type text}, {"mes_num", Int64.Type}, {"mes_nome", type text}, {"ano_mes", type text}, {"dia_semana_num", Int64.Type}, {"dia_semana", type text}, {"alta_temporada", type text}}, Cultura)
in
    Tipos

// ============================================================================
// CONSULTA "dim_produto"
// ============================================================================
let
    Fonte = Csv.Document(File.Contents(Pasta & "\dim_produto.csv"), [Delimiter = Separador, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(Cabecalho, {{"id_produto", Int64.Type}, {"produto", type text}, {"categoria", type text}}, Cultura)
in
    Tipos

// ============================================================================
// CONSULTA "dim_regiao"
// ============================================================================
let
    Fonte = Csv.Document(File.Contents(Pasta & "\dim_regiao.csv"), [Delimiter = Separador, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(Cabecalho, {{"id_regiao", Int64.Type}, {"regiao", type text}}, Cultura)
in
    Tipos

// ============================================================================
// CONSULTA "dim_canal"
// ============================================================================
let
    Fonte = Csv.Document(File.Contents(Pasta & "\dim_canal.csv"), [Delimiter = Separador, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(Cabecalho, {{"id_canal", Int64.Type}, {"canal", type text}}, Cultura)
in
    Tipos
