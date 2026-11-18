"""Carteras-registro de operaciones"""

import sqlite3
import pandas as pd


def crear_cartera(conn, nombre):
    """Crea una cartera y devuelve su id"""
    try:
        cur = conn.execute("INSERT INTO carteras (nombre) VALUES (?);", (nombre,))
    except sqlite3.IntegrityError:
        raise ValueError(f"Ya existe una cartera llamada «{nombre}».")
    conn.commit()
    return cur.lastrowid

def listar_carteras(conn):
    df = pd.read_sql_query("SELECT * FROM carteras;",conn)
    return df

def borrar_cartera(conn, cartera_id):
    try:
        cur = conn.execute("DELETE FROM carteras WHERE id = ?;",(cartera_id,))
    except sqlite3.IntegrityError:
        num = conn.execute("SELECT COUNT(*) FROM operaciones WHERE cartera_id = ? ;",(cartera_id,)).fetchone()[0]
        raise ValueError(f"La cartera «{cartera_id}» tiene «{num}» operaciones y no se puede borrar.")
    else:
        conn.commit()
        return cur.rowcount() > 0

    


    