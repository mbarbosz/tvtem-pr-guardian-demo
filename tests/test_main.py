import importlib
import os
from fastapi.testclient import TestClient

from app.main import app

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


def test_obter_programa_inexistente():
    r = client.get("/programas/999")
    assert r.status_code == 404


def test_api_token_lido_de_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv("TVTEM_ANALYTICS_TOKEN", "token-de-teste")
    import app.main as main_module
    importlib.reload(main_module)
    assert main_module.API_TOKEN == "token-de-teste"
    assert main_module.API_TOKEN != "tvtem-secret-token-hardcoded-12345"


def test_busca_parametrizada_bloqueia_sql_injection(monkeypatch):
    monkeypatch.setattr("app.main.requests.post", lambda *args, **kwargs: None)

    r_q = client.get("/programas/busca", params={"q": "' OR '1'='1"})
    assert r_q.status_code == 200
    assert r_q.json() == []

    r_genero = client.get(
        "/programas/busca",
        params={"q": "Tem", "genero": "jornalismo' OR '1'='1"},
    )
    assert r_genero.status_code == 200
    assert r_genero.json() == []

    r_valido = client.get(
        "/programas/busca",
        params={"q": "Tem", "genero": "jornalismo"},
    )
    assert r_valido.status_code == 200
    assert len(r_valido.json()) == 2
