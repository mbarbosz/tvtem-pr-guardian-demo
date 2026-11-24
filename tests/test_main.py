"""Testes básicos da API de Programação."""
import hmac
import importlib
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_listar_programas():
    r = client.get("/programas")
    assert r.status_code == 200
    assert len(r.json()) >= 4


def test_busca_nao_injeta_sql():
    r = client.get("/programas/busca", params={"q": "' OR '1'='1"})
    assert r.status_code == 200
    assert r.json() == []


def test_busca_parametrizada_bloqueia_sql_injection():
    r_q = client.get("/programas/busca", params={"q": "' OR '1'='1"})
    assert r_q.status_code == 200
    assert r_q.json() == []

    r_gen = client.get("/programas/busca", params={"q": "", "genero": "' OR '1'='1"})
    assert r_gen.status_code == 200
    assert r_gen.json() == []


def test_busca_nao_faz_chamada_externa_insegura():
    import app.main as main_module

    assert not hasattr(main_module, "requests")
    assert not hasattr(main_module, "ANALYTICS_URL")

    source = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text(encoding="utf-8")
    assert "verify=False" not in source
    assert "ANALYTICS_URL" not in source

    r = client.get("/programas/busca", params={"q": "Notícias"})
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_importar_grade_rejeita_sem_token(monkeypatch):
    monkeypatch.setenv("TVTEM_ADMIN_TOKEN", "segredo-teste")
    r = client.post(
        "/programas/importar",
        content="- id: 99\n  titulo: Teste\n  genero: teste\n  horario: '10:00'",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 401


def test_importar_grade_rejeita_token_invalido(monkeypatch):
    monkeypatch.setenv("TVTEM_ADMIN_TOKEN", "segredo-teste")
    r = client.post(
        "/programas/importar",
        content="- id: 99\n  titulo: Teste\n  genero: teste\n  horario: '10:00'",
        headers={"X-Admin-Token": "token-errado", "Content-Type": "text/plain"},
    )
    assert r.status_code == 401


def test_importar_grade_falha_se_variavel_admin_ausente(monkeypatch):
    monkeypatch.delenv("TVTEM_ADMIN_TOKEN", raising=False)
    r = client.post(
        "/programas/importar",
        content="- id: 99\n  titulo: Teste\n  genero: teste\n  horario: '10:00'",
        headers={"X-Admin-Token": "qualquer-coisa", "Content-Type": "text/plain"},
    )
    assert r.status_code == 401


def test_importar_grade_rejeita_payload_yaml_inseguro(monkeypatch):
    monkeypatch.setenv("TVTEM_ADMIN_TOKEN", "segredo-teste")
    payload_malicioso = "!!python/object/apply:os.system ['echo explorado']"
    r = client.post(
        "/programas/importar",
        content=payload_malicioso,
        headers={"X-Admin-Token": "segredo-teste", "Content-Type": "text/plain"},
    )
    assert r.status_code == 400


def test_importar_grade_aceita_yaml_valido_com_token(monkeypatch):
    monkeypatch.setenv("TVTEM_ADMIN_TOKEN", "segredo-teste")
    payload_valido = "- id: 99\n  titulo: Bom Dia Cidade\n  genero: jornalismo\n  horario: '06:00'"
    r = client.post(
        "/programas/importar",
        content=payload_valido,
        headers={"X-Admin-Token": "segredo-teste", "Content-Type": "text/plain"},
    )
    assert r.status_code == 200
    assert r.json() == {"importados": 1}


def test_api_token_lido_de_variavel_de_ambiente(monkeypatch):
    import app.main as main_module

    monkeypatch.setenv("TVTEM_ANALYTICS_TOKEN", "token-teste-env")
    reloaded = importlib.reload(main_module)
    assert reloaded.API_TOKEN == "token-teste-env"

    monkeypatch.delenv("TVTEM_ANALYTICS_TOKEN", raising=False)
    reloaded = importlib.reload(main_module)
    assert reloaded.API_TOKEN is None


def test_importar_grade_usa_comparacao_tempo_constante():
    source = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text(encoding="utf-8")
    assert "hmac.compare_digest" in source
    assert "==" not in source.split("def importar_grade")[1].split("grade = yaml.safe_load")[0]


def test_importar_grade_nao_reutiliza_token_analytics(monkeypatch):
    monkeypatch.setenv("TVTEM_ANALYTICS_TOKEN", "token-analytics-apenas")
    monkeypatch.setenv("TVTEM_ADMIN_TOKEN", "token-admin-exclusivo")
    payload_valido = "- id: 100\n  titulo: Jornal Regional\n  genero: jornalismo\n  horario: '18:00'"
    r = client.post(
        "/programas/importar",
        content=payload_valido,
        headers={"X-Admin-Token": "token-analytics-apenas", "Content-Type": "text/plain"},
    )
    assert r.status_code == 401
    assert not hmac.compare_digest("token-analytics-apenas", "token-admin-exclusivo")


def test_requirements_nao_contem_requests_vulneravel():
    reqs = (Path(__file__).resolve().parent.parent / "requirements.txt").read_text(encoding="utf-8").splitlines()
    pacotes = [line.strip().split("==")[0].split(">=")[0].lower() for line in reqs if line.strip() and not line.strip().startswith("#")]
    assert "requests" not in pacotes
