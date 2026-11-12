import pytest

import analise

SERIE = [
    ("2026-01-01T10:00:00", 20.0),
    ("2026-01-02T10:00:00", 18.0),
    ("2026-01-03T10:00:00", 12.0),  # maior queda: 18 -> 12
    ("2026-01-04T10:00:00", 15.0),
]


def test_resumo_basico():
    r = analise.resumir(SERIE)
    assert r["coletas"] == 4
    assert r["preco_inicial"] == 20.0 and r["preco_atual"] == 15.0
    assert r["variacao_total"] == -5.0
    assert r["menor_preco"] == 12.0 and r["menor_preco_em"] == "2026-01-03T10:00:00"
    assert r["maior_preco"] == 20.0
    assert r["preco_medio"] == 16.25


def test_maior_queda():
    q = analise.resumir(SERIE)["maior_queda"]
    assert q["valor"] == 6.0
    assert q["percentual"] == 33.3
    assert (q["de"], q["para"], q["em"]) == (18.0, 12.0, "2026-01-03T10:00:00")


def test_sem_queda():
    r = analise.resumir([("2026-01-01T00:00:00", 5.0), ("2026-01-02T00:00:00", 6.0)])
    assert r["maior_queda"]["em"] is None
    assert "nenhuma queda" in analise.formatar_resumo("X", r)


def test_uma_unica_coleta():
    r = analise.resumir([("2026-01-01T00:00:00", 9.0)])
    assert r["variacao_total"] == 0.0 and r["menor_preco"] == 9.0


def test_historico_vazio():
    with pytest.raises(ValueError):
        analise.resumir([])


def test_formatar_resumo_contem_campos():
    texto = analise.formatar_resumo("Meu Livro", analise.resumir(SERIE))
    assert "Meu Livro" in texto and "£12.00" in texto and "Maior queda" in texto


def test_gerar_grafico_cria_png(tmp_path):
    saida = analise.gerar_grafico("Meu Livro", SERIE, tmp_path / "sub" / "g.png", limite=14.0)
    assert saida.exists() and saida.stat().st_size > 1000
    assert saida.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
