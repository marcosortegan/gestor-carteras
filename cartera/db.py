import sqlite3
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="The inplace keyword")

CARPETA_PAQUETE = Path(__file__).resolve().parent
RUTA_ESQUEMA = CARPETA_PAQUETE / "esquema.sql"
RUTA_DB = CARPETA_PAQUETE.parent / "cartera.db"

def conectar(ruta_db=RUTA_DB):
    conn = sqlite3.connect(ruta_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def crear_tablas(conn, ruta_esquema=RUTA_ESQUEMA):
    sql = Path(ruta_esquema).read_text(encoding="utf-8")
    conn.executescript(sql)

def listar_tablas(conn):
    filas = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name;"
    ).fetchall()
    return [nombre for (nombre,) in filas]

def insertar_activos(conn, activos):
    conn.executemany(
        "INSERT OR IGNORE INTO activos (ticker, nombre, sector, divisa) VALUES (?, ?, ?, ?)",
        activos,
    )
    conn.commit()

if __name__ == "__main__":
    conn = conectar()
    try:
        crear_tablas(conn)
        print("Base de datos:", RUTA_DB)
        print("Tablas:", ", ".join(listar_tablas(conn)))
    finally:
        conn.close()

