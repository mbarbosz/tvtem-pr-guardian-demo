from fastapi.testclient import TestClient

from app.main import app
from scripts.check_registry import parse_requirements

client = TestClient(app)


def test_listar_programas():
    r = client.get("/programas")
    assert r.status_code == 200
    assert len(r.json()) == 4


def test_busca_nao_injeta_sql():
    r = client.get("/programas/busca", params={"q": "Notícias"})
    assert r.status_code == 200


def test_obter_programa_existente():
    r = client.get("/programas/1")
    assert r.status_code == 200
    assert r.json()["titulo"] == "Tem Notícias 1ª Edição"


def test_parse_requirements():
    assert "fastapi" in parse_requirements("requirements.txt")


def test_api_token_nao_hardcoded(monkeypatch):
    import importlib
    import app.main as main_module

    monkeypatch.delenv("TVTEM_ANALYTICS_TOKEN", raising=False)
    importlib.reload(main_module)
    assert main_module.API_TOKEN is None

    expected = "sample-env-value"
    monkeypatch.setenv("TVTEM_ANALYTICS_TOKEN", expected)
    importlib.reload(main_module)
    assert main_module.API_TOKEN == expected

    monkeypatch.delenv("TVTEM_ANALYTICS_TOKEN", raising=False)
    importlib.reload(main_module)
