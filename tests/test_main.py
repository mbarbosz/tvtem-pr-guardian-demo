import importlib
import os
from fastapi.testclient import TestClient

from app.main import app, db

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


def test_importar_grade_requer_autenticacao(monkeypatch):
    monkeypatch.setenv("TVTEM_ADMIN_TOKEN", "admin-token-secreto")
    payload = "- id: 5\n  titulo: Teste\n  genero: agro\n  horario: '08:00'\n"

    r_sem_token = client.post(
        "/programas/importar",
        content=payload,
        headers={"Content-Type": "text/plain"},
    )
    assert r_sem_token.status_code == 401

    r_token_invalido = client.post(
        "/programas/importar",
        content=payload,
        headers={"Content-Type": "text/plain", "X-Admin-Token": "errado"},
    )
    assert r_token_invalido.status_code == 401


def test_importar_grade_bloqueia_yaml_inseguro_e_aceita_yaml_valido(monkeypatch):
    monkeypatch.setenv("TVTEM_ADMIN_TOKEN", "admin-token-secreto")
    headers = {"Content-Type": "text/plain", "X-Admin-Token": "admin-token-secreto"}

    r_malicioso = client.post(
        "/programas/importar",
        content="!!python/object/apply:os.system ['echo pwned']\n",
        headers=headers,
    )
    assert r_malicioso.status_code == 400

    payload_valido = (
        "- id: 5\n"
        "  titulo: Bom Dia Cidade\n"
        "  genero: jornalismo\n"
        "  horario: '06:00'\n"
    )
    try:
        r_valido = client.post(
            "/programas/importar",
            content=payload_valido,
            headers=headers,
        )
        assert r_valido.status_code == 200
        assert r_valido.json() == {"importados": 1}
    finally:
        db.execute("DELETE FROM programas WHERE id = 5")
        db.commit()
