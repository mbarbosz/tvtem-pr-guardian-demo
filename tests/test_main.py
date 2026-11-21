from fastapi.testclient import TestClient

from app.main import app
from scripts.check_registry import parse_requirements

client = TestClient(app)


def test_listar():
    assert len(client.get("/programas").json()) == 4


def test_obter_404():
    assert client.get("/programas/999").status_code == 404


def test_busca_nao_injeta_sql():
    assert client.get("/programas/busca", params={"q": "Notícias"}).json()[0]["genero"] == "jornalismo"
    assert client.get("/programas/busca", params={"q": "' OR '1'='1"}).json() == []


def test_parse_requirements():
    txt = "# c\nfastapi==1.0\n\nPyYAML == 5.3.1  # x\nsemversao\n"
    assert parse_requirements(txt) == [("fastapi", "1.0"), ("PyYAML", "5.3.1")]
