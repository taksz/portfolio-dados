from app.user_agent import identificar_navegador, identificar_sistema_operacional

CHROME_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
)
SAFARI_MAC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.1 Safari/605.1.15"
)
FIREFOX_LINUX = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
)
CHROME_ANDROID = (
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"
)


def test_identificar_navegador_chrome():
    assert identificar_navegador(CHROME_WINDOWS) == "Chrome"


def test_identificar_navegador_safari():
    assert identificar_navegador(SAFARI_MAC) == "Safari"


def test_identificar_navegador_firefox():
    assert identificar_navegador(FIREFOX_LINUX) == "Firefox"


def test_identificar_navegador_vazio():
    assert identificar_navegador("") == "Outro"


def test_identificar_sistema_windows():
    assert identificar_sistema_operacional(CHROME_WINDOWS) == "Windows"


def test_identificar_sistema_mac():
    assert identificar_sistema_operacional(SAFARI_MAC) == "macOS"


def test_identificar_sistema_linux():
    assert identificar_sistema_operacional(FIREFOX_LINUX) == "Linux"


def test_identificar_sistema_ios():
    assert identificar_sistema_operacional(SAFARI_IPHONE) == "iOS"


def test_identificar_sistema_android():
    assert identificar_sistema_operacional(CHROME_ANDROID) == "Android"
