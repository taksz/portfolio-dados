"""Interface de linha de comando do rastreador de preços.

Uso:
    python src/cli.py coletar  --limite 20
    python src/cli.py agendar  --intervalo-min 60 --limite 20
    python src/cli.py listar
    python src/cli.py analisar "tipping the velvet" --grafico imgs/tipping.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import agendador
import alertas
import analise
import banco
import coleta

RAIZ = Path(__file__).resolve().parent.parent


def _args_coleta(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", default=str(banco.DB_PADRAO), help="arquivo SQLite (padrão: precos.db)")
    p.add_argument("--paginas", type=int, default=1, help="páginas do catálogo a coletar (20 produtos cada)")
    p.add_argument("--limite", type=float, help="alerta se o preço ficar abaixo deste valor (£)")
    p.add_argument("--limites-json", help='JSON {"id_do_produto": limite} com limites individuais')
    p.add_argument("--alertas", default=str(alertas.ARQUIVO_ALERTAS), help="arquivo de alertas")
    p.add_argument("--log", default=str(RAIZ / "rastreador.log"), help="arquivo de log")


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rastreador-precos", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="comando", required=True)

    _args_coleta(sub.add_parser("coletar", help="faz uma coleta agora"))

    ag = sub.add_parser("agendar", help="coleta periodicamente (Ctrl+C para parar)")
    _args_coleta(ag)
    ag.add_argument("--intervalo-min", type=float, default=60, help="minutos entre coletas (padrão: 60)")
    ag.add_argument("--execucoes", type=int, help="para após N execuções (padrão: roda para sempre)")

    ls = sub.add_parser("listar", help="lista os produtos com o último preço")
    ls.add_argument("--db", default=str(banco.DB_PADRAO))
    ls.add_argument("--limite", type=int, default=20, help="quantos produtos mostrar")

    an = sub.add_parser("analisar", help="resumo + gráfico de um produto")
    an.add_argument("produto", help="id exato ou parte do nome")
    an.add_argument("--db", default=str(banco.DB_PADRAO))
    an.add_argument("--grafico", help="caminho do PNG de saída (padrão: imgs/<id>.png)")
    an.add_argument("--limite", type=float, help="desenha a linha do limite de alerta no gráfico")

    sv = sub.add_parser("servir", help="abre o painel web no navegador (http://127.0.0.1:8000)")
    sv.add_argument("--db", default=str(banco.DB_PADRAO))
    sv.add_argument("--porta", type=int, default=8000)
    sv.add_argument("--host", default="127.0.0.1", help="endereço de escuta (padrão: só esta máquina)")
    sv.add_argument("--limite", type=float, help="limite de alerta padrão do painel (£)")
    sv.add_argument("--alertas", default=str(alertas.ARQUIVO_ALERTAS), help="arquivo de alertas")
    sv.add_argument("--log", default=str(RAIZ / "rastreador.log"), help="arquivo de log")

    dm = sub.add_parser("demo", help="cria um banco SIMULADO (demo.db) para demonstrar a análise")
    dm.add_argument("--db", default=str(RAIZ / "demo.db"))
    dm.add_argument("--snapshots", type=int, default=10)
    return parser


def _cmd_coletar(a: argparse.Namespace) -> int:
    coleta.configurar_logs(a.log)
    limites = alertas.carregar_limites(a.limites_json) if a.limites_json else None
    r = coleta.executar_coleta(a.db, a.paginas, a.limite, limites, a.alertas)
    return 1 if r["erro"] else 0


def _cmd_agendar(a: argparse.Namespace) -> int:
    coleta.configurar_logs(a.log)
    limites = alertas.carregar_limites(a.limites_json) if a.limites_json else None
    agendador.rodar(
        lambda: coleta.executar_coleta(a.db, a.paginas, a.limite, limites, a.alertas),
        a.intervalo_min * 60,
        a.execucoes,
    )
    return 0


def _cmd_listar(a: argparse.Namespace) -> int:
    conn = banco.conectar(a.db)
    linhas = banco.listar_produtos(conn)[: a.limite]
    conn.close()
    if not linhas:
        print("Banco vazio. Rode `coletar` primeiro.")
        return 1
    for r in linhas:
        estoque = "em estoque" if r["disponivel"] else "indisponível"
        print(f"£{r['preco']:>6.2f}  {r['nome'][:45]:<45}  {estoque}  [{r['id']}]")
    return 0


def _cmd_analisar(a: argparse.Namespace) -> int:
    conn = banco.conectar(a.db)
    prod = banco.buscar_produto(conn, a.produto)
    if prod is None:
        print(f"Produto não encontrado: {a.produto!r}", file=sys.stderr)
        return 1
    pontos = [(r["coletado_em"], r["preco"]) for r in banco.historico(conn, prod["id"])]
    conn.close()
    print(analise.formatar_resumo(prod["nome"], analise.resumir(pontos)))
    saida = a.grafico or str(RAIZ / "imgs" / f"{prod['id']}.png")
    analise.gerar_grafico(prod["nome"], pontos, saida, a.limite)
    print(f"Gráfico salvo em: {saida}")
    return 0


def _cmd_demo(a: argparse.Namespace) -> int:
    import demo
    import scraper

    print("Coletando preços reais como base e gerando histórico SIMULADO...")
    base = scraper.coletar(1)
    n = demo.gerar_historico_simulado(base, a.db, a.snapshots)
    print(f"{n} registros SIMULADOS gravados em {a.db} (não misturar com o histórico real).")
    return 0


def _cmd_servir(a: argparse.Namespace) -> int:
    import web

    coleta.configurar_logs(a.log)
    servidor = web.criar_servidor(a.db, a.alertas, a.host, a.porta, a.limite)
    print(f"Painel em http://{a.host}:{servidor.server_address[1]}  (Ctrl+C para parar)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        servidor.server_close()
    return 0


COMANDOS = {
    "servir": _cmd_servir,
    "coletar": _cmd_coletar,
    "agendar": _cmd_agendar,
    "listar": _cmd_listar,
    "analisar": _cmd_analisar,
    "demo": _cmd_demo,
}


def main(argv: list[str] | None = None) -> int:
    args = montar_parser().parse_args(argv)
    return COMANDOS[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
