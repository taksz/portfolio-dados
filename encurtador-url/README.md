# Encurtador de URL com Analytics

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/tests-pytest-0A9EDC?style=flat&logo=pytest&logoColor=white" alt="pytest" />
</p>

API em Python (FastAPI) que encurta URLs e registra **analytics de cada clique**: quantidade de acessos, visitantes únicos (aproximado), navegador, sistema operacional e origem (referrer) — com uma interface web para encurtar links e um painel de cliques.

## Funcionalidades

- **Encurtar URL** — gera um código curto em base62 (6 caracteres, ex.: `c30gsM`).
- **Redirecionamento** — `GET /{codigo}` redireciona (302) para a URL original e registra o clique.
- **Analytics por link**: total de cliques, visitantes únicos aproximados, cliques por dia, navegador, sistema operacional e top referrers.
- **Página inicial** (`/`) — cola a URL, copia o link curto e vê a lista de todos os links com o total de cliques.
- **Painel de cliques** (`/dashboard/{codigo}`) — gráfico de cliques por dia e rankings de navegadores, sistemas e origens, com atualização a cada 5 segundos. JavaScript puro, sem biblioteca de gráficos.
- **Tema claro, escuro ou automático**: o botão no topo alterna e o navegador lembra a escolha (também aceita `?tema=claro` ou `?tema=escuro` na URL).
- **Privacidade por padrão**: o IP do visitante nunca é armazenado em texto puro — só o hash SHA-256 dele, usado apenas para estimar visitantes únicos.

## Estrutura

```
encurtador-url/
├── app/
│   ├── main.py           # Endpoints da API (FastAPI)
│   ├── models.py         # Acesso a dados (SQLite): criar URL, registrar clique, estatísticas
│   ├── shortener.py      # Geração de código base62 + validação de URL
│   ├── user_agent.py     # Parser simples (regex) de navegador/SO a partir do User-Agent
│   ├── demo.py           # Popula o banco com links e cliques SIMULADOS (só para demonstração)
│   └── static/
│       ├── index.html    # Página inicial (encurtar + lista de links)
│       ├── dashboard.html  # Painel de cliques de um link
│       ├── style.css     # Estilos compartilhados (claro/escuro)
│       └── app.js        # Tema, copiar link e funções compartilhadas
├── imgs/                 # Capturas de tela da interface
├── tests/                # 43 testes pytest
└── requirements.txt
```

## Como executar

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

A API sobe em `http://127.0.0.1:8000`.

### Exemplo de uso (via curl)

```bash
# 1. Encurtar uma URL
curl -X POST http://127.0.0.1:8000/api/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.google.com/search?q=python"}'
# -> {"codigo":"c30gsM","url_original":"...","url_curta":"http://127.0.0.1:8000/c30gsM"}

# 2. Acessar a URL curta (redireciona e registra o clique)
curl -L http://127.0.0.1:8000/c30gsM

# 3. Ver as estatísticas desse link
curl http://127.0.0.1:8000/api/analytics/c30gsM
```

Saída real do passo 3, após 2 cliques (um vindo de `google.com`, outro direto, um Chrome e um Firefox):

```json
{
  "codigo": "c30gsM",
  "url_original": "https://www.google.com/search?q=python",
  "total_cliques": 2,
  "visitantes_unicos_aprox": 1,
  "cliques_por_dia": [{"dia": "2026-11-11", "cliques": 2}],
  "navegadores": [{"navegador": "Firefox", "cliques": 1}, {"navegador": "Chrome", "cliques": 1}],
  "sistemas_operacionais": [{"sistema_operacional": "Outro", "cliques": 2}],
  "top_referrers": [{"referrer": "https://google.com", "cliques": 1}, {"referrer": "(direto)", "cliques": 1}]
}
```

Ou abra `http://127.0.0.1:8000/dashboard/c30gsM` no navegador para ver o mesmo resultado em gráficos.

Também dá para explorar e testar todos os endpoints pela documentação interativa automática do FastAPI, em `http://127.0.0.1:8000/docs`.

## Interface

Depois de subir o servidor, abra `http://127.0.0.1:8000/` no navegador. Dá para encurtar links, copiar o link curto e abrir o painel de cada um sem digitar nenhum comando.

> O GitHub só mostra o código e as imagens: a API é um servidor Python e precisa ser executada na sua máquina (veja "Como executar"). As capturas abaixo vêm da própria interface rodando.

![Página inicial do encurtador](imgs/pagina-inicial.png)

![Painel de cliques de um link, tema claro](imgs/painel.png)

![Painel de cliques de um link, tema escuro](imgs/painel-escuro.png)

Ao encurtar um link, a interface mostra o endereço longo encolhendo até virar o código curto:

![Animação: o endereço longo encolhe e vira o link curto](imgs/animacao-encurtar.gif)

**Os cliques das capturas são simulados.** Um projeto recém-clonado não tem cliques, então o comando abaixo cria 3 links (`demo-docs`, `demo-portfolio` e `demo-dados`) com 14 dias de cliques pseudoaleatórios (semente fixa). Os dados não são reais:

```bash
python -m app.demo           # cria os links de demonstração
python -m app.demo --limpar  # remove só os links de demonstração
```

## Publicar online (Render)

Para qualquer pessoa usar o encurtador pelo navegador, sem instalar nada, o projeto precisa estar hospedado. O repositório já traz o arquivo `render.yaml` na raiz, que descreve o serviço para o [Render](https://render.com) (plano grátis, roda Python):

1. Crie uma conta no Render e escolha **New > Blueprint**.
2. Conecte o repositório `portfolio-dados`. O Render lê o `render.yaml` e propõe o serviço `encurtador-url`.
3. Confirme. Em alguns minutos o site fica no ar em um endereço `https://encurtador-url-xxxx.onrender.com`.

Variáveis de ambiente que o projeto reconhece:

| Variável | Efeito |
|---|---|
| `ENCURTADOR_DB` | Caminho do arquivo SQLite (padrão: `encurtador.db` na pasta do projeto). |
| `ENCURTADOR_DEMO` | Com `1`, se o banco estiver vazio ao iniciar, cria os links de demonstração com cliques **simulados**. |

No plano grátis o disco é apagado a cada reinício e o serviço "dorme" depois de um tempo sem acessos (a primeira visita seguinte demora uns segundos). Por isso o `render.yaml` liga `ENCURTADOR_DEMO=1`: o site sempre abre com dados de exemplo. Links criados por visitantes não são permanentes nessa hospedagem. Para guardá-los, é preciso um disco persistente (plano pago do Render) apontado por `ENCURTADOR_DB`.

## Modelo de dados (SQLite)

```
urls(id, codigo, url_original, criado_em)
cliques(id, url_id, clicado_em, referrer, navegador, sistema_operacional, ip_hash)
```

## Testes

43 testes com `pytest`, cobrindo geração/validação de código, parser de User-Agent, camada de dados (SQLite em memória) e a API de ponta a ponta (com `TestClient` do FastAPI):

```bash
pytest tests/ -v
```

## Próximos passos

- [ ] Autenticação simples para o dashboard (hoje qualquer um com o código vê o analytics)
- [ ] Expiração/desativação de links
- [ ] Deploy público (Render/Railway) com link ao vivo no README
