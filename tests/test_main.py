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


ADMIN = {"X-Admin-Token": "teste-admin", "Content-Type": "text/plain"}


def test_busca_por_genero():
    assert [p["id"] for p in client.get("/programas/busca", params={"q": "", "genero": "agro"}).json()] == [2]


def test_importar_exige_token():
    assert client.post("/programas/importar", content="[]", headers={"Content-Type": "text/plain"}).status_code == 401


def test_importar_grade(monkeypatch):
    monkeypatch.setattr("app.main.ADMIN_TOKEN", "teste-admin")
    yml = "- {id: 10, titulo: Bem Estar, genero: saude, horario: '10:00'}"
    assert client.post("/programas/importar", content=yml, headers=ADMIN).json() == {"importados": 1}
    assert client.post("/programas/importar", content=yml, headers=ADMIN).status_code == 409


def test_importar_yaml_malicioso_nao_executa(monkeypatch, tmp_path):
    monkeypatch.setattr("app.main.ADMIN_TOKEN", "teste-admin")
    alvo = tmp_path / "pwned"
    yml = f"!!python/object/apply:os.system ['touch {alvo}']"
    assert client.post("/programas/importar", content=yml, headers=ADMIN).status_code == 400
    assert not alvo.exists()
