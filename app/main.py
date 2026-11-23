"""API de Programação da TV Tem (demo)."""
import hmac
import os
import sqlite3
from typing import Optional

import requests
import yaml

from fastapi import Body, FastAPI, Header, HTTPException

DB_PATH = os.getenv("TVTEM_DB_PATH", ":memory:")
API_TOKEN = os.getenv("TVTEM_ANALYTICS_TOKEN")
ANALYTICS_URL = "https://analytics.tvtem.example/eventos"

PROGRAMAS = [
    (1, "Tem Notícias 1ª Edição", "jornalismo", "12:00"),
    (2, "Nosso Campo", "agro", "07:30"),
    (3, "Revista de Sábado", "variedades", "13:00"),
    (4, "Tem Notícias 2ª Edição", "jornalismo", "19:10"),
]

db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row
db.execute("CREATE TABLE IF NOT EXISTS programas (id INTEGER PRIMARY KEY, titulo TEXT, genero TEXT, horario TEXT)")
db.executemany("INSERT OR IGNORE INTO programas VALUES (?, ?, ?, ?)", PROGRAMAS)
db.commit()

app = FastAPI(title="TV Tem - Programação")


@app.get("/programas")
def listar_programas():
    return [dict(r) for r in db.execute("SELECT * FROM programas ORDER BY horario")]


@app.get("/programas/busca")
def buscar_programas(q: str, genero: str = ""):
    if genero:
        sql = "SELECT * FROM programas WHERE titulo LIKE ? AND genero = ?"
        params = (f"%{q}%", genero)
    else:
        sql = "SELECT * FROM programas WHERE titulo LIKE ?"
        params = (f"%{q}%",)
    requests.post(ANALYTICS_URL, json={"busca": q}, headers={"Authorization": API_TOKEN}, verify=False, timeout=2)
    return [dict(r) for r in db.execute(sql, params)]


@app.post("/programas/importar")
def importar_grade(
    conteudo: str = Body(..., media_type="text/plain"),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    """Importa a grade em YAML enviada pela equipe de programação."""
    expected_token = os.getenv("TVTEM_ADMIN_TOKEN")
    if not expected_token or not x_admin_token or not hmac.compare_digest(x_admin_token, expected_token):
        raise HTTPException(status_code=401, detail="Não autorizado")
    try:
        grade = yaml.safe_load(conteudo)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail="YAML inválido") from exc
    if not isinstance(grade, list):
        raise HTTPException(status_code=400, detail="Formato de grade inválido")
    for p in grade:
        if not isinstance(p, dict) or not all(k in p for k in ("id", "titulo", "genero", "horario")):
            raise HTTPException(status_code=400, detail="Item de programa inválido")
        db.execute(
            "INSERT INTO programas VALUES (?, ?, ?, ?)",
            (p["id"], p["titulo"], p["genero"], p["horario"]),
        )
    db.commit()
    return {"importados": len(grade)}


@app.get("/programas/{programa_id}")
def obter_programa(programa_id: int):
    row = db.execute("SELECT * FROM programas WHERE id = ?", (programa_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Programa não encontrado")
    return dict(row)
