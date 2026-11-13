"""Interface web local do rastreador: painel com produtos, gráfico de preço e alertas.

Usa só a biblioteca padrão (http.server). Rotas:
    GET  /                      painel (HTML)
    GET  /static/<arquivo>      CSS e JavaScript do painel
    GET  /healthz               verificação de saúde da hospedagem (pública)
    GET  /api/config            limite de alerta, páginas padrão e modos (somente leitura, demo)
    GET  /api/produtos          produtos com último preço e variação
    GET  /api/produto/<id>      histórico de preços + resumo estatístico
    GET  /api/alertas           alertas mais recentes (lidos de alertas.log)
    POST /api/coletar           roda uma coleta agora (acessa o site de verdade);
                                responde 403 se o servidor está em modo somente leitura
"""
from __future__ import annotations

import json
import logging
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import alertas as mod_alertas
import analise
import banco
import coleta

STATIC_DIR = Path(__file__).resolve().parent / "static"
log = logging.getLogger("rastreador")
_trava_coleta = threading.Lock()  # uma coleta por vez


def ler_alertas(arquivo: Path | str, maximo: int = 50) -> list[dict]:
    """Últimos alertas do arquivo (mais recente primeiro). Linha: 'ISO | ALERTA | id | mensagem'."""
    caminho = Path(arquivo)
    if not caminho.exists():
        return []
    itens = []
    for linha in reversed(caminho.read_text(encoding="utf-8").splitlines()):
        partes = linha.split(" | ", 3)
        if len(partes) == 4:
            itens.append({"quando": partes[0], "produto_id": partes[2], "mensagem": partes[3]})
        if len(itens) >= maximo:
            break
    return itens


class _Handler(BaseHTTPRequestHandler):
    db: str = ""
    arquivo_alertas: str = ""
    limite: Optional[float] = None
    paginas: int = 1
    somente_leitura: bool = False  # hospedagem pública: não deixa visitantes dispararem coletas
    demo: bool = False  # os dados exibidos são simulados

    # --- utilidades -------------------------------------------------------
    def log_message(self, formato, *args):  # silencia o log padrão de acesso
        log.debug("web: " + formato, *args)

    def _json(self, dados, status: int = 200) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _erro(self, status: int, mensagem: str) -> None:
        self._json({"erro": mensagem}, status)

    def _arquivo(self, caminho: Path) -> None:
        if not caminho.resolve().is_relative_to(STATIC_DIR.resolve()) or not caminho.is_file():
            return self._erro(404, "Arquivo não encontrado.")
        tipo = mimetypes.guess_type(caminho.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo.endswith("javascript"):
            tipo += "; charset=utf-8"
        corpo = caminho.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    # --- rotas ------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 (nome exigido pelo http.server)
        caminho = unquote(urlparse(self.path).path)
        if caminho == "/":
            return self._arquivo(STATIC_DIR / "index.html")
        if caminho.startswith("/static/"):
            return self._arquivo(STATIC_DIR / caminho[len("/static/"):])
        if caminho == "/healthz":  # verificação de saúde da hospedagem (não expõe dados)
            return self._json({"status": "ok"})
        if caminho == "/api/config":
            return self._json(
                {"limite": self.limite, "paginas": self.paginas, "somente_leitura": self.somente_leitura, "demo": self.demo}
            )
        if caminho == "/api/alertas":
            return self._json(ler_alertas(self.arquivo_alertas))
        if caminho == "/api/produtos":
            conn = banco.conectar(self.db)
            try:
                return self._json([dict(r) for r in banco.listar_com_resumo(conn)])
            finally:
                conn.close()
        if caminho.startswith("/api/produto/"):
            return self._produto(caminho[len("/api/produto/"):])
        self._erro(404, "Rota não encontrada.")

    def _produto(self, produto_id: str) -> None:
        conn = banco.conectar(self.db)
        try:
            prod = banco.buscar_produto(conn, produto_id)
            if prod is None:
                return self._erro(404, "Produto não encontrado.")
            pontos = [(r["coletado_em"], r["preco"]) for r in banco.historico(conn, prod["id"])]
        finally:
            conn.close()
        self._json(
            {
                "id": prod["id"],
                "nome": prod["nome"],
                "url": prod["url"],
                "pontos": [{"coletado_em": d, "preco": p} for d, p in pontos],
                "resumo": analise.resumir(pontos),
            }
        )

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/coletar":
            return self._erro(404, "Rota não encontrada.")
        if self.somente_leitura:
            return self._erro(403, "Esta demonstração é somente leitura: a coleta está desligada.")
        tamanho = int(self.headers.get("Content-Length") or 0)
        try:
            corpo = json.loads(self.rfile.read(tamanho) or b"{}")
            limite = corpo.get("limite", self.limite)
            limite = float(limite) if limite not in (None, "") else None
            paginas = max(1, min(int(corpo.get("paginas", self.paginas)), 5))
        except (ValueError, TypeError):
            return self._erro(422, "Parâmetros inválidos: use limite numérico e paginas entre 1 e 5.")
        if not _trava_coleta.acquire(blocking=False):
            return self._erro(409, "Já existe uma coleta em andamento. Aguarde terminar.")
        try:
            resultado = coleta.executar_coleta(self.db, paginas, limite, None, self.arquivo_alertas)
        finally:
            _trava_coleta.release()
        self._json(resultado, 200 if not resultado["erro"] else 502)


def criar_servidor(
    db: Path | str,
    arquivo_alertas: Path | str = mod_alertas.ARQUIVO_ALERTAS,
    host: str = "127.0.0.1",
    porta: int = 8000,
    limite: Optional[float] = None,
    paginas: int = 1,
    somente_leitura: bool = False,
    demo: bool = False,
) -> ThreadingHTTPServer:
    """Cria (sem iniciar) o servidor. Use porta=0 para o sistema escolher uma porta livre."""
    banco.conectar(db).close()  # garante que o banco e as tabelas existam

    class Handler(_Handler):
        pass

    Handler.db = str(db)
    Handler.arquivo_alertas = str(arquivo_alertas)
    Handler.limite = limite
    Handler.paginas = paginas
    Handler.somente_leitura = somente_leitura
    Handler.demo = demo
    return ThreadingHTTPServer((host, porta), Handler)
