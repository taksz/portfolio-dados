import pandas as pd
import pytest

import exportar_powerbi as ep


def vendas_exemplo() -> pd.DataFrame:
    return pd.DataFrame(
        [
            (1, "2024-01-01", "Moda", "Camiseta", 2, 50.0, 100.0, "Sul", "Online"),
            (2, "2024-01-03", "Moda", "Tênis", 1, 300.0, 300.0, "Sudeste", "Loja Física"),
            (3, "2024-01-05", "Casa", "Panela", 3, 40.0, 120.0, "Sul", "Online"),
            (4, "2024-01-05", "Moda", "Camiseta", 1, 55.0, 55.0, "Norte", "Online"),
        ],
        columns=["id_venda", "data", "categoria", "produto", "quantidade", "preco_unitario", "receita", "regiao", "canal"],
    )


def test_modelo_tem_as_cinco_tabelas():
    m = ep.construir_modelo(vendas_exemplo())
    assert set(m) == {"fato_vendas", "dim_calendario", "dim_produto", "dim_regiao", "dim_canal"}


def test_fato_preserva_linhas_e_receita():
    v = vendas_exemplo()
    fato = ep.construir_modelo(v)["fato_vendas"]
    assert len(fato) == len(v)
    assert fato["receita"].sum() == v["receita"].sum()
    assert fato["id_venda"].is_unique


def test_integridade_referencial_das_chaves():
    m = ep.construir_modelo(vendas_exemplo())
    fato = m["fato_vendas"]
    assert fato[["id_produto", "id_regiao", "id_canal"]].notna().all().all()
    assert set(fato["id_produto"]) <= set(m["dim_produto"]["id_produto"])
    assert set(fato["id_regiao"]) <= set(m["dim_regiao"]["id_regiao"])
    assert set(fato["id_canal"]) <= set(m["dim_canal"]["id_canal"])
    assert set(fato["data"]) <= set(m["dim_calendario"]["data"])


def test_dimensoes_sem_duplicidade():
    m = ep.construir_modelo(vendas_exemplo())
    assert m["dim_produto"]["id_produto"].is_unique
    assert not m["dim_produto"].duplicated(["produto", "categoria"]).any()
    assert len(m["dim_regiao"]) == 3 and len(m["dim_canal"]) == 2


def test_chave_do_produto_acompanha_nome_e_categoria():
    m = ep.construir_modelo(vendas_exemplo())
    juntou = m["fato_vendas"].merge(m["dim_produto"], on="id_produto")
    assert list(juntou.loc[juntou["id_venda"] == 2, ["produto", "categoria"]].iloc[0]) == ["Tênis", "Moda"]


def test_calendario_continuo_e_com_alta_temporada():
    cal = ep.construir_calendario(pd.Timestamp("2023-01-01"), pd.Timestamp("2024-12-31"))
    assert len(cal) == 365 + 366  # 2024 é bissexto
    assert (cal["data"].diff().dropna() == pd.Timedelta(days=1)).all()
    assert cal.loc[cal["mes_num"].isin([11, 12]), "alta_temporada"].eq("Sim").all()
    assert cal.loc[~cal["mes_num"].isin([11, 12]), "alta_temporada"].eq("Não").all()
    assert cal.loc[cal["data"] == "2024-03-04", "dia_semana"].iloc[0] == "segunda-feira"
    assert cal.loc[cal["data"] == "2023-03-01", "mes_nome"].iloc[0] == "março"


def test_colunas_ausentes():
    with pytest.raises(ValueError, match="Colunas ausentes"):
        ep.construir_modelo(vendas_exemplo().drop(columns=["receita"]))


def test_gravar_formato_brasileiro(tmp_path):
    modelo = ep.construir_modelo(vendas_exemplo())
    ep.gravar_modelo(modelo, tmp_path, "ptbr")
    texto = (tmp_path / "fato_vendas.csv").read_text(encoding="utf-8-sig")
    assert texto.splitlines()[0].startswith("id_venda;data;")
    assert "100,0" in texto and "2024-01-01" in texto
    assert "Tênis" in (tmp_path / "dim_produto.csv").read_text(encoding="utf-8-sig")


def test_gravar_formato_us_e_releitura(tmp_path):
    modelo = ep.construir_modelo(vendas_exemplo())
    ep.gravar_modelo(modelo, tmp_path, "us")
    fato = pd.read_csv(tmp_path / "fato_vendas.csv")
    assert fato["receita"].sum() == 575.0 and len(fato) == 4


def test_formato_invalido(tmp_path):
    with pytest.raises(ValueError):
        ep.gravar_modelo(ep.construir_modelo(vendas_exemplo()), tmp_path, "xx")
