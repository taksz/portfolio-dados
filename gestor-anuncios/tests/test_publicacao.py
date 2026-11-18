"""Publicação no Render: serviço no render.yaml, demonstração somente leitura e /healthz."""
import re
import shlex
from pathlib import Path

from fastapi.testclient import TestClient

import cli
import demo
import web
from adaptadores import criar_adaptadores_demo

RENDER_YAML = Path(__file__).resolve().parents[2] / "render.yaml"


def servico_gestor() -> str:
    """Trecho do render.yaml do serviço gestor-anuncios (até o próximo serviço)."""
    texto = RENDER_YAML.read_text(encoding="utf-8")
    partes = re.split(r"\n  - type: ", texto)
    trechos = [p for p in partes if re.search(r"^\s*name: gestor-anuncios\s*$", p, re.M)]
    assert len(trechos) == 1, "render.yaml precisa de exatamente um serviço gestor-anuncios"
    return trechos[0]


def comando_inicial() -> list[str]:
    linha = re.search(r"^\s*startCommand: (.+)$", servico_gestor(), re.M).group(1)
    return shlex.split(linha)


def test_render_yaml_tem_o_servico_na_pasta_do_projeto():
    trecho = servico_gestor()
    assert re.search(r"^\s*rootDir: gestor-anuncios\s*$", trecho, re.M)
    assert re.search(r"^\s*healthCheckPath: /healthz\s*$", trecho, re.M)
    assert re.search(r"^\s*buildCommand: pip install -r requirements.txt\s*$", trecho, re.M)


def test_comando_do_render_e_demo_somente_leitura_aberto_para_fora():
    partes = comando_inicial()
    assert partes[:3] == ["python", "src/cli.py", "servir"]
    args = cli.montar_parser().parse_args([p.replace("$PORT", "10000") for p in partes[2:]])
    assert args.host == "0.0.0.0"
    assert args.porta == 10000
    assert args.somente_leitura is True
    assert args.demo is True


def test_demonstracao_publica_abre_com_dados_e_sem_coleta(tmp_path):
    db, arq = tmp_path / "anuncios.db", tmp_path / "alertas.log"
    assert demo.preparar_se_vazio(db, arq) is True  # disco do Render vazio a cada reinício
    c = TestClient(web.criar_app(db, arq, criar_adaptadores_demo(), somente_leitura=True, demo=True))
    assert c.get("/healthz").json() == {"status": "ok"}
    resumo = c.get("/api/resumo").json()
    assert resumo["total"] == 40
    assert resumo["demo"] is True and resumo["somente_leitura"] is True
    assert c.post("/api/coletar").status_code == 403
    assert c.get("/api/alertas").json()["alertas"]
    assert "Dados simulados" in c.get("/").text


def test_demonstracao_nao_recria_dados_se_o_banco_ja_tem(tmp_path):
    db, arq = tmp_path / "anuncios.db", tmp_path / "alertas.log"
    demo.preparar_se_vazio(db, arq)
    antes = arq.read_text(encoding="utf-8")
    assert demo.preparar_se_vazio(db, arq) is False
    assert arq.read_text(encoding="utf-8") == antes
