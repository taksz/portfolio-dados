"""
API do encurtador de URL com analytics.

Endpoints (os marcados com [login] exigem senha quando ENCURTADOR_SENHA está definida):
    GET   /                     [login] página inicial: encurtar links e ver a lista
    POST  /api/shorten          [login] cria uma URL curta (com expiração opcional)
    GET   /api/urls             [login] lista as URLs criadas (com cliques e status)
    PATCH /api/urls/{code}      [login] desativa/reativa o link ou muda a expiração
    GET   /api/analytics/{code} [login] estatísticas de cliques de um código
    GET   /dashboard/{code}     [login] painel HTML com o analytics do link
    GET   /{code}               redireciona para a URL original e registra o clique
                                (responde 410 se o link expirou ou foi desativado)
    GET   /healthz              verificação de saúde da hospedagem (pública)

Variáveis de ambiente:
    ENCURTADOR_SENHA    se definida, protege tudo, menos o redirecionamento dos links
                        curtos, com senha (HTTP Basic; usuário padrão "admin")
    ENCURTADOR_USUARIO  muda o nome de usuário (padrão: admin)
    ENCURTADOR_DB       caminho do arquivo SQLite
    ENCURTADOR_DEMO     com "1", cria links de demonstração se o banco estiver vazio

Rodar localmente:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import models
from .shortener import validar_url

BASE_DIR = Path(__file__).resolve().parent
# ENCURTADOR_DB muda o arquivo do banco (útil em hospedagem, com disco montado).
DB_PATH = Path(os.environ.get("ENCURTADOR_DB") or BASE_DIR.parent / "encurtador.db")
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = models.conectar(str(DB_PATH))
    models.inicializar_schema(conn)
    # ENCURTADOR_DEMO=1: se o banco estiver vazio, cria links com cliques SIMULADOS.
    # Serve para uma hospedagem de demonstração não abrir vazia (veja app/demo.py).
    if os.environ.get("ENCURTADOR_DEMO") == "1" and not models.listar_urls(conn):
        from . import demo

        demo.popular(conn)
    conn.close()
    yield


app = FastAPI(title="Encurtador de URL com Analytics", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --------------------------------------------------------------------------------------
# Autenticação simples (HTTP Basic). Só vale quando ENCURTADOR_SENHA está definida; sem ela
# o app fica aberto, como no desenvolvimento local. Use sempre com HTTPS em hospedagem.
# --------------------------------------------------------------------------------------
_basico = HTTPBasic(auto_error=False)


def exigir_login(credenciais: Optional[HTTPBasicCredentials] = Depends(_basico)) -> None:
    senha = os.environ.get("ENCURTADOR_SENHA", "")
    if not senha:
        return
    usuario = os.environ.get("ENCURTADOR_USUARIO", "admin")
    usuario_ok = secrets.compare_digest((credenciais.username if credenciais else "").encode("utf-8"), usuario.encode("utf-8"))
    senha_ok = secrets.compare_digest((credenciais.password if credenciais else "").encode("utf-8"), senha.encode("utf-8"))
    if credenciais is None or not (usuario_ok and senha_ok):
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária.",
            headers={"WWW-Authenticate": 'Basic realm="Encurtador", charset="UTF-8"'},
        )


PROTEGIDO = [Depends(exigir_login)]


@app.get("/", include_in_schema=False, dependencies=PROTEGIDO)
def pagina_inicial():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz", include_in_schema=False)
def saude():
    """Verificação de saúde para a hospedagem (pública de propósito: não expõe nenhum dado)."""
    return {"status": "ok"}


class EncurtarRequest(BaseModel):
    url: str = Field(..., description="URL original (http:// ou https://)")
    expira_em_dias: Optional[int] = Field(
        None, ge=1, le=3650, description="Dias até o link expirar (omita para nunca expirar)"
    )


class EncurtarResponse(BaseModel):
    codigo: str
    url_original: str
    url_curta: str
    expira_em: Optional[str] = None


class AtualizarRequest(BaseModel):
    ativo: Optional[bool] = Field(None, description="false desativa o link; true reativa")
    expira_em_dias: Optional[int] = Field(None, ge=1, le=3650, description="Nova expiração, contada a partir de agora")
    sem_expiracao: bool = Field(False, description="true remove a data de expiração")


@app.post("/api/shorten", response_model=EncurtarResponse, dependencies=PROTEGIDO)
def encurtar(payload: EncurtarRequest, request: Request):
    if not validar_url(payload.url):
        raise HTTPException(status_code=422, detail="URL inválida. Use http:// ou https://.")

    expira_em = datetime.now(timezone.utc) + timedelta(days=payload.expira_em_dias) if payload.expira_em_dias else None

    conn = models.conectar(str(DB_PATH))
    try:
        codigo = models.criar_url_curta(conn, payload.url, expira_em)
    finally:
        conn.close()

    base_url = str(request.base_url).rstrip("/")
    return EncurtarResponse(
        codigo=codigo,
        url_original=payload.url,
        url_curta=f"{base_url}/{codigo}",
        expira_em=expira_em.isoformat() if expira_em else None,
    )


@app.get("/api/urls", dependencies=PROTEGIDO)
def listar_urls():
    conn = models.conectar(str(DB_PATH))
    try:
        return models.listar_urls(conn)
    finally:
        conn.close()


@app.patch("/api/urls/{codigo}", dependencies=PROTEGIDO)
def atualizar_url(codigo: str, payload: AtualizarRequest):
    if payload.ativo is None and payload.expira_em_dias is None and not payload.sem_expiracao:
        raise HTTPException(status_code=422, detail="Informe ativo, expira_em_dias ou sem_expiracao.")
    if payload.expira_em_dias is not None and payload.sem_expiracao:
        raise HTTPException(status_code=422, detail="Use expira_em_dias ou sem_expiracao, não os dois.")

    conn = models.conectar(str(DB_PATH))
    try:
        if models.obter_url(conn, codigo) is None:
            raise HTTPException(status_code=404, detail="Código não encontrado.")
        if payload.ativo is not None:
            models.definir_ativo(conn, codigo, payload.ativo)
        if payload.expira_em_dias is not None:
            models.definir_expiracao(conn, codigo, datetime.now(timezone.utc) + timedelta(days=payload.expira_em_dias))
        elif payload.sem_expiracao:
            models.definir_expiracao(conn, codigo, None)
        url = models.obter_url(conn, codigo)
        return {
            "codigo": codigo,
            "ativo": bool(url["ativo"]),
            "expira_em": url["expira_em"],
            "status": models.status_url(url),
        }
    finally:
        conn.close()


@app.get("/api/analytics/{codigo}", dependencies=PROTEGIDO)
def analytics(codigo: str):
    conn = models.conectar(str(DB_PATH))
    try:
        stats = models.obter_estatisticas(conn, codigo)
    finally:
        conn.close()

    if stats is None:
        raise HTTPException(status_code=404, detail="Código não encontrado.")
    return stats


@app.get("/dashboard/{codigo}", dependencies=PROTEGIDO)
def dashboard(codigo: str):
    conn = models.conectar(str(DB_PATH))
    try:
        url = models.obter_url(conn, codigo)
    finally:
        conn.close()

    if url is None:
        raise HTTPException(status_code=404, detail="Código não encontrado.")
    return FileResponse(STATIC_DIR / "dashboard.html")


_MENSAGENS_INDISPONIVEL = {
    "expirado": ("Este link expirou", "O endereço curto passou da data de validade e não leva mais a lugar nenhum."),
    "desativado": ("Este link foi desativado", "Quem criou o endereço curto desligou o redirecionamento."),
}


def _pagina_indisponivel(status: str) -> HTMLResponse:
    titulo, texto = _MENSAGENS_INDISPONIVEL[status]
    html = (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f"<title>{titulo}</title>"
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@400;600;800'
        '&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">'
        '<link rel="stylesheet" href="/static/style.css"></head><body><div class="page">'
        '<header class="topo"><span class="marca"><b>/</b>encurtador</span><nav></nav></header>'
        f'<main class="hero"><h1>{titulo}.</h1><p>{texto}</p></main></div>'
        '<script src="/static/app.js"></script></body></html>'
    )
    return HTMLResponse(html, status_code=410)


@app.get("/{codigo}")
def redirecionar(codigo: str, request: Request):
    conn = models.conectar(str(DB_PATH))
    try:
        url = models.obter_url(conn, codigo)
        if url is None:
            raise HTTPException(status_code=404, detail="Código não encontrado.")

        status = models.status_url(url)
        if status != "ativo":
            # link desligado ou vencido: não redireciona e não conta clique
            return _pagina_indisponivel(status)

        cliente_ip: Optional[str] = request.client.host if request.client else None
        models.registrar_clique(
            conn,
            url_id=url["id"],
            referrer=request.headers.get("referer"),
            user_agent=request.headers.get("user-agent"),
            ip=cliente_ip,
        )
    finally:
        conn.close()

    return RedirectResponse(url=url["url_original"], status_code=302)
