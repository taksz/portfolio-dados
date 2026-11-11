# 🔗 Encurtador de URL com Analytics

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/tests-pytest-0A9EDC?style=flat&logo=pytest&logoColor=white" alt="pytest" />
</p>

API em Python (FastAPI) que encurta URLs e registra **analytics de cada clique**: quantidade de acessos, visitantes únicos (aproximado), navegador, sistema operacional e origem (referrer) — com um dashboard HTML simples para visualizar tudo.

## ⚙️ Funcionalidades

- 🔗 **Encurtar URL** — gera um código curto em base62 (6 caracteres, ex.: `c30gsM`).
- ↪️ **Redirecionamento** — `GET /{codigo}` redireciona (302) para a URL original e registra o clique.
- 📊 **Analytics por link**: total de cliques, visitantes únicos aproximados, cliques por dia, navegador, sistema operacional e top referrers.
- 🖥️ **Dashboard HTML** (`/dashboard/{codigo}`) — visualização simples em gráficos de barra, sem depender de nenhuma biblioteca de gráficos externa (JS puro).
- 🔒 **Privacidade por padrão**: o IP do visitante nunca é armazenado em texto puro — só o hash SHA-256 dele, usado apenas para estimar visitantes únicos.

## 📁 Estrutura

```
encurtador-url/
├── app/
│   ├── main.py           # Endpoints da API (FastAPI)
│   ├── models.py         # Acesso a dados (SQLite): criar URL, registrar clique, estatísticas
│   ├── shortener.py      # Geração de código base62 + validação de URL
│   ├── user_agent.py     # Parser simples (regex) de navegador/SO a partir do User-Agent
│   └── static/
│       └── dashboard.html
├── tests/                # 36 testes pytest
└── requirements.txt
```

## 🚀 Como executar

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

Ou abra `http://127.0.0.1:8000/dashboard/c30gsM` no navegador para ver o mesmo resultado em gráficos de barra.

Também dá para explorar e testar todos os endpoints pela documentação interativa automática do FastAPI, em `http://127.0.0.1:8000/docs`.

## 🧮 Modelo de dados (SQLite)

```
urls(id, codigo, url_original, criado_em)
cliques(id, url_id, clicado_em, referrer, navegador, sistema_operacional, ip_hash)
```

## 🧪 Testes

36 testes com `pytest`, cobrindo geração/validação de código, parser de User-Agent, camada de dados (SQLite em memória) e a API de ponta a ponta (com `TestClient` do FastAPI):

```bash
pytest tests/ -v
```

## 🚧 Próximos passos

- [ ] Autenticação simples para o dashboard (hoje qualquer um com o código vê o analytics)
- [ ] Expiração/desativação de links
- [ ] Deploy público (Render/Railway) com link ao vivo no README
