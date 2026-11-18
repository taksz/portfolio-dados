import banco
import cli
import demo


def test_demo_cria_historico_simulado(tmp_path):
    db, arq = tmp_path / "demo.db", tmp_path / "alertas.log"
    assert demo.gerar(db, arq) == 8
    conn = banco.conectar(db)
    assert len(banco.listar_veiculos(conn)) == 40
    assert banco.ultima_coleta(conn) == "2026-10-20T09:00:00"
    assert arq.read_text(encoding="utf-8").count("ALERTA") > 10


def test_preparar_se_vazio_so_cria_uma_vez(tmp_path):
    db, arq = tmp_path / "demo.db", tmp_path / "alertas.log"
    assert demo.preparar_se_vazio(db, arq) is True
    assert demo.preparar_se_vazio(db, arq) is False


def test_cli_demo_recusa_banco_com_dados(tmp_path, capsys):
    base = ["--db", str(tmp_path / "demo.db"), "--alertas", str(tmp_path / "a.log")]
    assert cli.main(["demo", *base]) == 0
    assert cli.main(["demo", *base]) == 1
    assert "já tem dados" in capsys.readouterr().out


def test_cli_listar_mostra_situacoes(tmp_path, capsys):
    base = ["--db", str(tmp_path / "demo.db"), "--alertas", str(tmp_path / "a.log")]
    cli.main(["demo", *base])
    capsys.readouterr()
    assert cli.main(["listar", *base]) == 0
    saida = capsys.readouterr().out
    assert "Vendido" in saida and "Parado" in saida
    assert len(saida.strip().splitlines()) == 41  # cabeçalho + 40 veículos


def test_cli_listar_filtra_por_situacao(tmp_path, capsys):
    base = ["--db", str(tmp_path / "demo.db"), "--alertas", str(tmp_path / "a.log")]
    cli.main(["demo", *base])
    capsys.readouterr()
    assert cli.main(["listar", *base, "--situacao", "vendido"]) == 0
    linhas = capsys.readouterr().out.strip().splitlines()[1:]
    assert len(linhas) == 4 and all("Vendido" in linha for linha in linhas)


def test_cli_listar_banco_vazio(tmp_path, capsys):
    assert cli.main(["listar", "--db", str(tmp_path / "vazio.db")]) == 0
    assert "Nenhum veículo" in capsys.readouterr().out


def test_cli_coletar_grava_no_banco(tmp_path):
    db = tmp_path / "g.db"
    assert cli.main(["coletar", "--db", str(db), "--alertas", str(tmp_path / "a.log")]) == 0
    assert len(banco.listar_veiculos(banco.conectar(db))) > 30


def test_cli_agendar_executa_n_vezes(tmp_path):
    db = tmp_path / "g.db"
    args = ["agendar", "--db", str(db), "--alertas", str(tmp_path / "a.log"), "--intervalo-min", "0.004",
            "--execucoes", "2"]
    assert cli.main(args) == 0
    conn = banco.conectar(db)
    assert conn.execute("SELECT COUNT(DISTINCT coletado_em) FROM snapshots").fetchone()[0] >= 1
