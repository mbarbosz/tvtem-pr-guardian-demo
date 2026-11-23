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


def test_importar_grade_parametrizada_bloqueia_sql_injection(monkeypatch):
    monkeypatch.setenv("TVTEM_ADMIN_TOKEN", "admin-token-secreto")
    headers = {"Content-Type": "text/plain", "X-Admin-Token": "admin-token-secreto"}
    payload_sqli = (
        "- id: 6\n"
        "  titulo: \"Teste'); DROP TABLE programas; --\"\n"
        "  genero: \"jornalismo' OR '1'='1\"\n"
        "  horario: \"10:00\"\n"
    )
    try:
        r = client.post(
            "/programas/importar",
            content=payload_sqli,
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json() == {"importados": 1}

        r_prog = client.get("/programas/6")
        assert r_prog.status_code == 200
        assert r_prog.json()["titulo"] == "Teste'); DROP TABLE programas; --"
        assert r_prog.json()["genero"] == "jornalismo' OR '1'='1"

        r_lista = client.get("/programas")
        assert r_lista.status_code == 200
        assert len(r_lista.json()) == 5
    finally:
        db.execute("DELETE FROM programas WHERE id = 6")
        db.commit()


def test_endpoint_admin_backup_removido():
    r = client.get("/admin/backup", params={"destino": "/tmp/backup.db"})
    assert r.status_code == 404


def test_pyyaml_versao_segura_em_requirements():
    from pathlib import Path
    import re

    req_path = Path(__file__).resolve().parent.parent / "requirements.txt"
    conteudo = req_path.read_text(encoding="utf-8")
    assert "PyYAML==5.3.1" not in conteudo
    match = re.search(r"(?im)^pyyaml\s*(==|>=)\s*(\d+)\.(\d+)(?:\.(\d+))?", conteudo)
    assert match is not None, "PyYAML deve estar declarado em requirements.txt"
    major, minor = int(match.group(2)), int(match.group(3))
    assert (major, minor) >= (5, 4), f"Versão vulnerável de PyYAML encontrada: {match.group(0)}"


def test_dependencia_inexistente_removida_de_requirements():
    from pathlib import Path

    req_path = Path(__file__).resolve().parent.parent / "requirements.txt"
    conteudo = req_path.read_text(encoding="utf-8")
    assert "tvtem-analytics-sdk" not in conteudo.lower()
