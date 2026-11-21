"""API de Programação da TV Tem (demo)."""
import os
import sqlite3

from fastapi import FastAPI, HTTPException

DB_PATH = os.getenv("TVTEM_DB_PATH", ":memory:")

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
def buscar_programas(q: str):
    rows = db.execute("SELECT * FROM programas WHERE titulo LIKE ?", (f"%{q}%",))
    return [dict(r) for r in rows]


@app.get("/programas/{programa_id}")
def obter_programa(programa_id: int):
    row = db.execute("SELECT * FROM programas WHERE id = ?", (programa_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Programa não encontrado")
    return dict(row)
