"""Gestor de anúncios de veículos: coleta, classifica e mostra o estoque anunciado.

Exemplos:
    python src/cli.py demo                      # cria demo.db com 8 semanas SIMULADAS
    python src/cli.py listar --db demo.db       # situação de cada veículo
    python src/cli.py servir --db demo.db       # painel em http://127.0.0.1:8000
    python src/cli.py coletar                   # uma coleta agora (adaptador demo)
    python src/cli.py agendar --intervalo-min 60
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import alertas
import banco
import coleta
import demo
import regras
from adaptadores import criar_adaptadores_demo

# Plataformas disponíveis. Para plugar uma real, acrescente aqui a função que cria os adaptadores dela.
ADAPTADORES = {"demo": criar_adaptadores_demo}


def _comuns(p: argparse.ArgumentParser, db=banco.DB_PADRAO, arq=alertas.ARQUIVO_ALERTAS) -> None:
    p.add_argument("--db", default=str(db), help=f"arquivo SQLite (padrão: {Path(db).name})")
    p.add_argument("--alertas", default=str(arq), help=f"arquivo de alertas (padrão: {Path(arq).name})")


def _coleta(p: argparse.ArgumentParser) -> None:
    _comuns(p)
    p.add_argument("--adaptador", choices=sorted(ADAPTADORES), default="demo", help="plataformas a coletar")
    p.add_argument("--log", default=None, help="também grava o log da execução neste arquivo")


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gestor-anuncios", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="comando", required=True)

    _coleta(sub.add_parser("coletar", help="faz uma coleta agora"))
    ag = sub.add_parser("agendar", help="coleta periodicamente (Ctrl+C para parar)")
    _coleta(ag)
    ag.add_argument("--intervalo-min", type=float, default=60, help="minutos entre coletas (padrão: 60)")
    ag.add_argument("--execucoes", type=int, default=None, help="para depois de N coletas")

    ls = sub.add_parser("listar", help="mostra a situação de cada veículo")
    _comuns(ls)
    ls.add_argument("--situacao", choices=regras.SITUACOES, help="só veículos nesta situação")

    sv = sub.add_parser("servir", help="abre o painel web (http://127.0.0.1:8000)")
    _comuns(sv)
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--porta", type=int, default=8000)
    sv.add_argument("--somente-leitura", action="store_true", help="desliga o botão/rota de coleta")
    sv.add_argument("--demo", action="store_true", help="se o banco estiver vazio, cria o histórico SIMULADO")

    dm = sub.add_parser("demo", help="cria um banco com 8 semanas de coletas SIMULADAS")
    _comuns(dm, demo.DB_DEMO, demo.ALERTAS_DEMO)
    dm.add_argument("--semanas", type=int, default=8)
    return parser


def _reais(valor) -> str:
    return "—" if valor is None else "R$ " + f"{valor:,.0f}".replace(",", ".")


def cmd_coletar(args) -> int:
    coleta.configurar_logs(args.log)
    conn = banco.conectar(args.db)
    try:
        r = coleta.executar(ADAPTADORES[args.adaptador](), conn, args.alertas)
    finally:
        conn.close()
    return 0 if r["erros"] == 0 else 1


def cmd_agendar(args) -> int:
    import agendador

    coleta.configurar_logs(args.log)
    adaptadores = ADAPTADORES[args.adaptador]()

    def tarefa():
        conn = banco.conectar(args.db)
        try:
            coleta.executar(adaptadores, conn, args.alertas)
        finally:
            conn.close()

    agendador.rodar(tarefa, args.intervalo_min * 60, args.execucoes)
    return 0


def cmd_listar(args) -> int:
    conn = banco.conectar(args.db)
    try:
        ultima = banco.ultima_coleta(conn)
        if not ultima:
            print("Nenhum veículo no banco. Rode `coletar` ou `demo` primeiro.")
            return 0
        veiculos = {v["placa"]: v for v in banco.listar_veiculos(conn)}
        diagnosticos = regras.avaliar_todos(conn, datetime.fromisoformat(ultima))
    finally:
        conn.close()

    print(f"{'Situação':<27} {'Placa':<8} {'Veículo':<42} {'Preço':>11} {'Sugestão':>11}")
    for d in diagnosticos:
        if args.situacao and d.situacao != args.situacao:
            continue
        v = veiculos[d.placa]
        nome = f"{v['marca']} {v['modelo']} {v['versao']} {v['ano']}"[:42]
        print(f"{regras.ROTULOS[d.situacao]:<27} {d.placa:<8} {nome:<42} {_reais(d.preco_atual):>11} "
              f"{_reais(d.sugestao):>11}")
    return 0


def cmd_servir(args) -> int:
    import uvicorn

    import web

    if args.demo and demo.preparar_se_vazio(args.db, args.alertas):
        print("Banco vazio: histórico SIMULADO criado.")
    app = web.criar_app(args.db, args.alertas, criar_adaptadores_demo(), somente_leitura=args.somente_leitura,
                        demo=args.demo)
    uvicorn.run(app, host=args.host, port=args.porta)
    return 0


def cmd_demo(args) -> int:
    if demo.tem_dados(args.db):
        print(f"{args.db} já tem dados. Apague o arquivo (e {args.alertas}) para gerar de novo.")
        return 1
    coleta.configurar_logs()
    demo.gerar(args.db, args.alertas, semanas=args.semanas)
    print(f"Histórico SIMULADO criado em {args.db} ({args.semanas} coletas semanais). "
          f"Abra com: python src/cli.py servir --db {args.db} --alertas {args.alertas} --somente-leitura")
    return 0


COMANDOS = {"coletar": cmd_coletar, "agendar": cmd_agendar, "listar": cmd_listar, "servir": cmd_servir,
            "demo": cmd_demo}


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # acentos no terminal do Windows
    args = montar_parser().parse_args(argv)
    return COMANDOS[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
