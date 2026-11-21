"""API de Programação da TV Tem (demo)."""
import os
import secrets
import sqlite3

import httpx
import yaml
from fastapi import Body, FastAPI, Header, HTTPException

DB_PATH = os.getenv("TVTEM_DB_PATH", ":memory:")
ANALYTICS_URL = os.getenv("TVTEM_ANALYTICS_URL")
ANALYTICS_TOKEN = os.getenv("TVTEM_ANALYTICS_TOKEN", "")
ADMIN_TOKEN = os.getenv("TVTEM_ADMIN_TOKEN", "")
CAMPOS = ("id", "titulo", "genero", "horario")

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


def registrar_busca(q: str):
    if not ANALYTICS_URL:
        return
    try:
        httpx.post(ANALYTICS_URL, json={"busca": q}, headers={"Authorization": f"Bearer {ANALYTICS_TOKEN}"}, timeout=2)
    except httpx.HTTPError:
        pass  # analytics é best-effort: falha não derruba a busca


@app.get("/programas")
def listar_programas():
    return [dict(r) for r in db.execute("SELECT * FROM programas ORDER BY horario")]


@app.get("/programas/busca")
def buscar_programas(q: str, genero: str = ""):
    rows = db.execute(
        "SELECT * FROM programas WHERE titulo LIKE ? AND (? = '' OR genero = ?)",
        (f"%{q}%", genero, genero),
    ).fetchall()
    registrar_busca(q)
    return [dict(r) for r in rows]


@app.post("/programas/importar")
def importar_grade(conteudo: str = Body(..., media_type="text/plain"), x_admin_token: str = Header("")):
    """Importa a grade em YAML enviada pela equipe de programação (requer X-Admin-Token)."""
    if not ADMIN_TOKEN or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(401, "Token de administração inválido")
    try:
        grade = yaml.safe_load(conteudo)
    except yaml.YAMLError:
        raise HTTPException(400, "YAML inválido")
    if not isinstance(grade, list) or not all(isinstance(p, dict) and set(CAMPOS) <= p.keys() for p in grade):
        raise HTTPException(422, f"Esperada lista de programas com {', '.join(CAMPOS)}")
    try:
        with db:
            db.executemany("INSERT INTO programas VALUES (?, ?, ?, ?)", [tuple(p[c] for c in CAMPOS) for p in grade])
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Programa com id já existente")
    return {"importados": len(grade)}


@app.get("/programas/{programa_id}")
def obter_programa(programa_id: int):
    row = db.execute("SELECT * FROM programas WHERE id = ?", (programa_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Programa não encontrado")
    return dict(row)
