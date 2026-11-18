import sqlite3
import pandas as pd
from datetime import date, timedelta

def acciones_en_fecha(conn, cartera_id, ticker, fecha):

    fila = conn.execute(
        """
        SELECT COALESCE(SUM(CASE
                   WHEN tipo = 'compra' THEN cantidad
                   WHEN tipo = 'venta'  THEN -cantidad
                   ELSE 0
               END), 0)
        FROM operaciones
        WHERE cartera_id = ? AND ticker = ? AND fecha <= ?;
        """,
        (cartera_id, ticker, fecha),
    ).fetchone()
    return fila[0]

def registrar_operacion(conn, cartera_id, ticker, fecha, tipo, cantidad, precio, comision=0):

    if conn.execute("SELECT 1 FROM carteras WHERE id = ?;", (cartera_id,)).fetchone() is None:
        raise ValueError(f"No existe la cartera {cartera_id}")
    if conn.execute("SELECT 1 FROM activos WHERE ticker = ?;",(ticker,)).fetchone() is None:
        raise ValueError(f"El ticker >{ticker}< no está en la tabla activos")
    if fecha > date.today().isoformat():
        raise ValueError(f"La fecha {fecha} es futura")
    acciones = acciones_en_fecha(conn,cartera_id,ticker,fecha)
    if tipo == "venta" and acciones < cantidad:
        raise ValueError(f"Quieres vender {cantidad} acciones de {ticker} y hay solo {acciones}")
    if tipo == "dividendo" and acciones <= 0:
        raise ValueError(f"No tenías acciones de {ticker} el {fecha}")
    
    cur = conn.execute("""INSERT INTO operaciones (cartera_id, ticker, fecha, tipo, cantidad, precio, comision) 
                     VALUES (?,?,?,?,?,?,?);""", (cartera_id, ticker, fecha, tipo, cantidad, precio, comision,))
    conn.commit()
    return cur.lastrowid
            







    

