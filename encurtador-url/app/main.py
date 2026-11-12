"""
API do encurtador de URL com analytics.

Endpoints:
    GET  /                     -> página inicial: encurtar links e ver a lista
    POST /api/shorten         -> cria uma URL curta
    GET  /api/urls             -> lista as URLs já criadas (com total de cliques)
    GET  /api/analytics/{code} -> estatísticas de cliques de um código
    GET  /dashboard/{code}     -> painel HTML com o analytics do link
    GET  /{code}               -> redireciona para a URL original e registra o clique

Rodar localmente:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
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


@app.get("/", include_in_schema=False)
def pagina_inicial():
    return FileResponse(STATIC_DIR / "index.html")


class EncurtarRequest(BaseModel):
    url: str = Field(..., description="URL original (http:// ou https://)")


class EncurtarResponse(BaseModel):
    codigo: str
    url_original: str
    url_curta: str


@app.post("/api/shorten", response_model=EncurtarResponse)
def encurtar(payload: EncurtarRequest, request: Request):
    if not validar_url(payload.url):
        raise HTTPException(status_code=422, detail="URL inválida. Use http:// ou https://.")

    conn = models.conectar(str(DB_PATH))
    try:
        codigo = models.criar_url_curta(conn, payload.url)
    finally:
        conn.close()

    base_url = str(request.base_url).rstrip("/")
    return EncurtarResponse(
        codigo=codigo,
        url_original=payload.url,
        url_curta=f"{base_url}/{codigo}",
    )


@app.get("/api/urls")
def listar_urls():
    conn = models.conectar(str(DB_PATH))
    try:
        return models.listar_urls(conn)
    finally:
        conn.close()


@app.get("/api/analytics/{codigo}")
def analytics(codigo: str):
    conn = models.conectar(str(DB_PATH))
    try:
        stats = models.obter_estatisticas(conn, codigo)
    finally:
        conn.close()

    if stats is None:
        raise HTTPException(status_code=404, detail="Código não encontrado.")
    return stats


@app.get("/dashboard/{codigo}")
def dashboard(codigo: str):
    conn = models.conectar(str(DB_PATH))
    try:
        url = models.obter_url(conn, codigo)
    finally:
        conn.close()

    if url is None:
        raise HTTPException(status_code=404, detail="Código não encontrado.")
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/{codigo}")
def redirecionar(codigo: str, request: Request):
    conn = models.conectar(str(DB_PATH))
    try:
        url = models.obter_url(conn, codigo)
        if url is None:
            raise HTTPException(status_code=404, detail="Código não encontrado.")

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
