"""Painel web (FastAPI): resumo do estoque, tabela com sinalização, filtros e histórico por veículo.

Rotas:
    GET  /                       painel (src/static/index.html)
    GET  /api/resumo             contagem por situação, estoque ativo, média de dias, valor parado
    GET  /api/veiculos           lista com diagnóstico; filtros: situacao, plataforma, marca, q
    GET  /api/veiculos/{placa}   detalhe + histórico por coleta (preço por plataforma, visitas, contatos)
    POST /api/coletar            coleta agora (403 em modo somente leitura)
    GET  /api/alertas            últimos alertas (?limite=)
    GET  /healthz                verificação de saúde (hospedagem)

As regras são avaliadas na data da última coleta, para o histórico SIMULADO
do modo demonstração aparecer igual em qualquer dia.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import alertas
import banco
import coleta
import regras
from adaptadores import AdaptadorPlataforma
from modelos import normalizar_placa

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _texto_busca(v: dict) -> str:
    return f"{v['placa']} {v['marca']} {v['modelo']} {v['versao']} {v['ano']}".lower()


def _placa_busca(q: str) -> str:
    return q.replace("-", "").replace(" ", "").upper()


def criar_app(
    db: Path | str,
    arquivo_alertas: Path | str,
    adaptadores: Optional[Sequence[AdaptadorPlataforma]] = None,
    somente_leitura: bool = False,
    demo: bool = False,
    cfg: regras.Config = regras.Config(),
) -> FastAPI:
    app = FastAPI(title="Gestor de anúncios", docs_url="/docs")

    def estoque() -> tuple[list[dict], Optional[str]]:
        """Veículos com diagnóstico, do mais urgente para o menos."""
        conn = banco.conectar(db)
        try:
            ultima = banco.ultima_coleta(conn)
            if not ultima:
                return [], None
            veiculos = {v["placa"]: dict(v) for v in banco.listar_veiculos(conn)}
            plataformas: dict[str, list[str]] = {}
            for a in banco.todos_anuncios(conn):
                plataformas.setdefault(a["placa"], []).append(a["plataforma"])
            diagnosticos = regras.avaliar_todos(conn, datetime.fromisoformat(ultima), cfg)
        finally:
            conn.close()
        linhas = []
        for d in diagnosticos:
            linha = {**veiculos[d.placa], **asdict(d)}
            linha["rotulo"] = regras.ROTULOS[d.situacao]
            linha["plataformas"] = sorted(plataformas.get(d.placa, []))
            linha["diferenca_ref"] = (
                round(d.preco_atual / d.referencia - 1, 4) if d.preco_atual and d.referencia else None
            )
            linhas.append(linha)
        return linhas, ultima

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/resumo")
    def resumo():
        linhas, ultima = estoque()
        contagem = {s: 0 for s in regras.SITUACOES}
        por_filtro = {s: 0 for s in regras.SITUACOES}  # situação principal ou sinal (igual ao filtro)
        for v in linhas:
            contagem[v["situacao"]] += 1
            for s in {v["situacao"], *v["sinais"]}:
                por_filtro[s] += 1
        ativos = [v for v in linhas if v["situacao"] not in ("vendido", "fora_do_ar")]
        parados = [v for v in ativos if {"parado", "nao_converte"} & {v["situacao"], *v["sinais"]}]
        return {
            "total": len(linhas),
            "ativos": len(ativos),
            "por_situacao": contagem,
            "por_filtro": por_filtro,
            "remover": sum(1 for v in linhas if v["remover_de"]),
            "acima_referencia": sum(1 for v in linhas if "preco_alto" in [v["situacao"], *v["sinais"]]),
            "media_dias": round(sum(v["dias_anunciado"] for v in ativos) / len(ativos)) if ativos else 0,
            "valor_parado": sum(v["preco_atual"] or 0 for v in parados),
            "ultima_coleta": ultima,
            "demo": demo,
            "somente_leitura": somente_leitura or not adaptadores,
            "plataformas": sorted({p for v in linhas for p in v["plataformas"]}),
            "marcas": sorted({v["marca"] for v in linhas}),
            "rotulos": regras.ROTULOS,
            "config": asdict(cfg),
        }

    @app.get("/api/veiculos")
    def listar(
        situacao: Optional[str] = None,
        plataforma: Optional[str] = None,
        marca: Optional[str] = None,
        q: Optional[str] = Query(None, max_length=60),
    ):
        linhas, _ = estoque()
        if situacao:
            linhas = [v for v in linhas if situacao == v["situacao"] or situacao in v["sinais"]]
        if plataforma:
            linhas = [v for v in linhas if plataforma in v["plataformas"]]
        if marca:
            linhas = [v for v in linhas if v["marca"] == marca]
        if q and q.strip():
            termo, placa = q.strip().lower(), _placa_busca(q)
            linhas = [v for v in linhas if termo in _texto_busca(v) or (len(placa) >= 3 and placa in v["placa"])]
        return {"veiculos": linhas}

    @app.get("/api/veiculos/{placa}")
    def detalhe(placa: str):
        try:
            placa = normalizar_placa(placa)
        except ValueError:
            raise HTTPException(404, "veículo não encontrado")
        linhas, _ = estoque()
        linha = next((v for v in linhas if v["placa"] == placa), None)
        if linha is None:
            raise HTTPException(404, "veículo não encontrado")

        conn = banco.conectar(db)
        try:
            anuncios = [dict(a) for a in banco.anuncios_do_veiculo(conn, placa)]
            snaps = [dict(s) for s in banco.snapshots_do_veiculo(conn, placa)]
        finally:
            conn.close()

        # Histórico por coleta: preço de cada plataforma ativa e quanto entrou de visitas/contatos desde a anterior.
        historico, anteriores = [], {}
        for momento in sorted({s["coletado_em"] for s in snaps}):
            ponto = {"coletado_em": momento, "precos": {}, "visitas": 0, "contatos": 0}
            for s in (s for s in snaps if s["coletado_em"] == momento):
                if s["status"] == "ativo":  # menor preço da plataforma, se houver anúncio duplicado
                    ponto["precos"][s["plataforma"]] = min(s["preco"], ponto["precos"].get(s["plataforma"], s["preco"]))
                chave = (s["plataforma"], s["anuncio_id"])
                antes = anteriores.get(chave)
                if antes:
                    ponto["visitas"] += max(0, s["visualizacoes"] - antes["visualizacoes"])
                    ponto["contatos"] += max(0, s["contatos"] - antes["contatos"])
                anteriores[chave] = s
            historico.append(ponto)

        ultimos = {}
        for s in snaps:
            ultimos[(s["plataforma"], s["anuncio_id"])] = s
        for a in anuncios:
            u = ultimos.get((a["plataforma"], a["anuncio_id"]))
            a["status"], a["preco"] = (u["status"], u["preco"]) if u else ("—", None)
        return {"veiculo": linha, "anuncios": anuncios, "historico": historico}

    @app.post("/api/coletar")
    def coletar():
        if somente_leitura or not adaptadores:
            raise HTTPException(403, "coleta desligada neste painel (somente leitura)")
        conn = banco.conectar(db)
        try:
            return coleta.executar(adaptadores, conn, arquivo_alertas, cfg=cfg)
        finally:
            conn.close()

    @app.get("/api/alertas")
    def ultimos_alertas(limite: int = Query(20, ge=1, le=200)):
        return {"alertas": alertas.ler(arquivo_alertas, limite)}

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
