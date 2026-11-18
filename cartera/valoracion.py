import sqlite3
import pandas as pd
from datetime import date
import numpy as np

def acciones_en_fecha(conn, cartera_id, ticker, fecha):
    pos = posiciones(conn, cartera_id, fecha)
    if ticker in pos.index:
        return float(pos.loc[ticker, "acciones"])
    return 0.0



def posiciones(conn, cartera_id, fecha=None, incluir_cerradas=False):
    """Posiciones de una cartera al cierre de `fecha` (hoy si es None).

    Devuelve un DataFrame indexado por ticker con: acciones, coste_medio,
    coste_total y plusvalia_realizada (en la divisa de cada activo).
    """
    if fecha is None:
        fecha = date.today().isoformat()

    ops = pd.read_sql_query(
        """
        SELECT fecha, ticker, tipo, cantidad, precio, comision
        FROM operaciones
        WHERE cartera_id = ? AND fecha <= ?;
        """,
        conn, params=(cartera_id, fecha),
    )
    splits = pd.read_sql_query(
        """
        SELECT fecha, ticker, 'split' AS tipo, valor AS cantidad,
               0 AS precio, 0 AS comision
        FROM eventos
        WHERE tipo = 'split' AND fecha <= ?
          AND ticker IN (SELECT ticker FROM operaciones WHERE cartera_id = ?);
        """,
        conn, params=(fecha, cartera_id),
    )

    eventos = pd.concat([splits, ops], ignore_index=True)
    eventos["orden"] = (eventos["tipo"] != "split").astype(int)   # split = 0 primero
    eventos = eventos.sort_values(["ticker", "fecha", "orden"], kind="stable")

    estado = {}  
    for ev in eventos.itertuples():
        e = estado.setdefault(ev.ticker, {"acciones": 0.0, "coste": 0.0, "realizado": 0.0})

        if ev.tipo == "compra":
            e["acciones"] += ev.cantidad
            e["coste"] += np.multiply(ev.cantidad,ev.precio)+ev.comision
        if e["acciones"] <= 0:
            raise ValueError(f"Venta de {ev.ticker} el {ev.fecha} sin acciones.")
        elif ev.tipo == "venta":
            coste_medio = e["coste"] / e["acciones"]
            e["realizado"] += (ev.precio - coste_medio) * ev.cantidad - ev.comision
            e["coste"] -= ev.cantidad * coste_medio
            e["acciones"] -= ev.cantidad
        elif ev.tipo == "split":
            e["acciones"] *= ev.cantidad

    columnas = ["acciones", "coste_medio", "coste_total", "plusvalia_realizada"]
    if not estado:
        return pd.DataFrame(columns=columnas).rename_axis("ticker")

    df = pd.DataFrame.from_dict(estado, orient="index")
    df = df.rename(columns={"coste": "coste_total", "realizado": "plusvalia_realizada"})
    if not incluir_cerradas:
        df = df[df["acciones"].abs() > 1e-9]
    df = df.copy()
    df["coste_medio"] = df["coste_total"] / df["acciones"].where(df["acciones"].abs() > 1e-9)
    df.index.name = "ticker"
    return df[columnas].sort_index()
            







    

