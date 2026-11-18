"""Carteras-registro de operaciones"""

import sqlite3
import pandas as pd
from datetime import date
from cartera.valoracion import acciones_en_fecha



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
        return cur.rowcount > 0


def comprobar_ventas_posteriores(conn, cartera_id, ticker, fecha, cantidad):
    fechas = conn.execute(
        """
        SELECT DISTINCT fecha FROM operaciones
        WHERE cartera_id = ? AND ticker = ? AND tipo = 'venta' AND fecha > ?
        ORDER BY fecha;
        """,
        (cartera_id, ticker, fecha),
    ).fetchall()
    for (f,) in fechas:
        if acciones_en_fecha(conn, cartera_id, ticker, f) - cantidad < 0:
            raise ValueError(
                f"Con esta venta no habría acciones de {ticker} suficientes "
                f"para la venta ya registrada el {f}."
            )



def registrar_operacion(conn, cartera_id, ticker, fecha, tipo, cantidad, precio, comision=0):

    if conn.execute("SELECT 1 FROM carteras WHERE id = ?;", (cartera_id,)).fetchone() is None:
        raise ValueError(f"No existe la cartera {cartera_id}.")
    if conn.execute("SELECT 1 FROM activos WHERE ticker = ?;", (ticker,)).fetchone() is None:
        raise ValueError(f"El ticker {ticker} no está en la tabla de activos.")

    acciones = acciones_en_fecha(conn, cartera_id, ticker, fecha)
    if tipo == "venta":
        if acciones < cantidad:
            raise ValueError(
                f"Quieres vender {cantidad} acciones de {ticker} el {fecha} "
                f"y solo tenías {acciones:g}."
            )
        comprobar_ventas_posteriores(conn, cartera_id, ticker, fecha, cantidad)
    if tipo == "dividendo" and acciones <= 0:
        raise ValueError(f"No tenías acciones de {ticker} el {fecha}.")

    cur = conn.execute(
        """
        INSERT INTO operaciones (cartera_id, ticker, fecha, tipo, cantidad, precio, comision)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (cartera_id, ticker, fecha, tipo, cantidad, precio, comision),
    )
    conn.commit()
    return cur.lastrowid

    


    