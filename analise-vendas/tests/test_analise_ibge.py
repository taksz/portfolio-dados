"""Testes da análise com dados do IBGE. Sem internet: a API é mockada com uma amostra
REAL da resposta da SIDRA (tests/fixtures/pmc_amostra.json, 2022-2023)."""
import json
from pathlib import Path

import pandas as pd
import pytest
import requests
import responses

import analise_ibge as ai

AMOSTRA = Path(__file__).parent / "fixtures" / "pmc_amostra.json"


@pytest.fixture
def registros():
    return json.loads(AMOSTRA.read_text(encoding="utf-8"))


def serie_sintetica(anos=range(2019, 2026)) -> pd.DataFrame:
    """Série de teste: índice dessazonalizado constante em 100 e sazonalidade conhecida
    (dezembro = +20%, janeiro = -10%, resto = 0)."""
    linhas = []
    for ano in anos:
        for mes in range(1, 13):
            sazonal = {12: 1.2, 1: 0.9}.get(mes, 1.0)
            linhas.append({"periodo": pd.Timestamp(ano, mes, 1), "indice": 100 * sazonal, "indice_dessaz": 100.0})
    return pd.DataFrame(linhas)


def test_parse_amostra_real(registros):
    df = ai.parse_pmc(registros)
    assert list(df.columns) == ["periodo", "indice", "indice_dessaz"]
    assert len(df) == 24  # 24 meses, 2 variáveis por mês
    assert df["periodo"].iloc[0] == pd.Timestamp("2022-01-01")
    assert df["periodo"].is_monotonic_increasing
    assert df[["indice", "indice_dessaz"]].notna().all().all()


def test_parse_ignora_cabecalho_e_converte_numeros(registros):
    df = ai.parse_pmc(registros)
    primeiro = next(r for r in registros[1:] if r["D3C"] == "202201" and r["D2C"] == "7169")
    assert df.loc[df["periodo"] == "2022-01-01", "indice"].iloc[0] == float(primeiro["V"])


def test_parse_resposta_vazia():
    with pytest.raises(ValueError):
        ai.parse_pmc([{"cabecalho": "x"}])


def test_media_de_2022_proxima_de_100(registros):
    # a base do índice é 2022 = 100: a média do índice original em 2022 deve ser ~100
    df = ai.parse_pmc(registros)
    assert df[df["periodo"].dt.year == 2022]["indice"].mean() == pytest.approx(100, abs=0.5)


def test_fator_sazonal_recupera_a_sazonalidade_conhecida():
    f = ai.fator_sazonal_mensal(serie_sintetica(), 2019, 2025)
    assert len(f) == 12 and f.mean() == pytest.approx(1.0)
    assert f[12] > f[6] > f[1]  # dezembro > mês neutro > janeiro
    assert f[12] / f[6] == pytest.approx(1.2)
    assert f[1] / f[6] == pytest.approx(0.9)


def test_fator_sazonal_intervalo_sem_dados():
    with pytest.raises(ValueError):
        ai.fator_sazonal_mensal(serie_sintetica(), 1990, 1995)


def test_efeito_fim_de_ano():
    f = pd.Series({m: 1.0 for m in range(1, 13)})
    f[11], f[12] = 1.5, 2.5
    assert ai.efeito_fim_de_ano(f) == pytest.approx(2.0)


def test_fator_sintetico_reflete_gerar_dados():
    f = ai.fator_sazonal_sintetico()
    assert f.idxmax() == 11 and f.mean() == pytest.approx(1.0)
    assert ai.efeito_fim_de_ano(f) > 2  # o gerador supõe um efeito forte


def test_variacao_anual():
    df = serie_sintetica()
    df.loc[df["periodo"].dt.year == 2024, "indice"] *= 1.10
    assert ai.variacao_anual(df, 2024) == pytest.approx(10.0)
    assert ai.variacao_anual(df, 2023) == pytest.approx(0.0)


def test_resumo_com_serie_sintetica():
    df = serie_sintetica()
    df.loc[df["periodo"] == "2020-04-01", "indice_dessaz"] = 80.0  # queda na "pandemia"
    r = ai.resumo(df, ano_inicial=2019, ano_final=2025)
    assert r["meses"] == 84 and r["ultimo_mes"] == pd.Timestamp("2025-12-01")
    assert r["queda_covid_pct"] == pytest.approx(-20.0)
    assert r["pico_dessaz"] == 100.0
    assert r["efeito_real"] > 1 and r["efeito_sintetico"] > r["efeito_real"]


@responses.activate
def test_baixar_pmc_usa_a_api_do_ibge(registros):
    responses.add(responses.GET, ai.URL_PMC, json=registros, status=200)
    assert ai.baixar_pmc() == registros
    assert "apisidra.ibge.gov.br" in responses.calls[0].request.url


@responses.activate
def test_baixar_pmc_propaga_erro_http():
    responses.add(responses.GET, ai.URL_PMC, status=500)
    with pytest.raises(requests.HTTPError):
        ai.baixar_pmc()


def test_graficos_geram_png(tmp_path, monkeypatch):
    monkeypatch.setattr(ai, "IMGS_DIR", tmp_path)
    df = serie_sintetica(range(2012, 2026))
    f = ai.fator_sazonal_mensal(df, 2014, 2025)
    for caminho in (ai.grafico_serie(df), ai.grafico_sazonalidade(f, ai.fator_sazonal_sintetico(), (2014, 2025))):
        assert caminho.exists() and caminho.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
