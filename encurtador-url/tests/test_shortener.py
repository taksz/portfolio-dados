from app.shortener import TAMANHO_PADRAO, gerar_codigo, validar_url


def test_gerar_codigo_tamanho_padrao():
    codigo = gerar_codigo()
    assert len(codigo) == TAMANHO_PADRAO


def test_gerar_codigo_tamanho_customizado():
    assert len(gerar_codigo(10)) == 10


def test_gerar_codigo_usa_apenas_alfabeto_base62():
    codigo = gerar_codigo(100)
    assert all(c.isalnum() for c in codigo)


def test_gerar_codigo_e_aleatorio():
    codigos = {gerar_codigo() for _ in range(50)}
    assert len(codigos) > 1  # extremamente improvável gerar o mesmo código 50x


def test_validar_url_https_valida():
    assert validar_url("https://exemplo.com/pagina") is True


def test_validar_url_http_valida():
    assert validar_url("http://exemplo.com") is True


def test_validar_url_sem_esquema_invalida():
    assert validar_url("exemplo.com") is False


def test_validar_url_esquema_nao_http_invalida():
    assert validar_url("ftp://exemplo.com/arquivo") is False


def test_validar_url_vazia_invalida():
    assert validar_url("") is False


def test_validar_url_sem_dominio_invalida():
    assert validar_url("https://") is False
