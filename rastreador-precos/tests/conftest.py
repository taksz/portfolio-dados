import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def html_pagina1() -> str:
    return (FIXTURES / "catalogo_pagina1.html").read_text(encoding="utf-8")


@pytest.fixture
def html_pagina50() -> str:
    return (FIXTURES / "catalogo_pagina50.html").read_text(encoding="utf-8")
