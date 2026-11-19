import pandas as pd
from datetime import date
import numpy as np

def acciones_en_fecha(conn, cartera_id, ticker, fecha):
    pos = posiciones(conn, cartera_id, fecha)
    if ticker in pos.index:
        return float(pos.loc[ticker, "acciones"])
    return 0.0



def posiciones(conn, cartera_id, fecha=None, incluir_cerradas=False):

    if fecha is None:
        fecha = date.today().isoformat()

    ops = pd.read_sql_query(
        """
        SELECT fecha, ticker, tipo, cantidad, precio, comision
        FROM operaciones
        WHERE cartera_id = ? AND fecha <= ?;
        """,conn, params=(cartera_id, fecha))
    splits = pd.read_sql_query(
        """
        SELECT fecha, ticker, 'split' AS tipo, valor AS cantidad,
               0 AS precio, 0 AS comision
        FROM eventos
        WHERE tipo = 'split' AND fecha <= ?
          AND ticker IN (SELECT ticker FROM operaciones WHERE cartera_id = ?);
        """,conn, params=(fecha, cartera_id))

    eventos = pd.concat([splits, ops], ignore_index=True)
    eventos["orden"] = (eventos["tipo"] != "split").astype(int)   # split = 0 primero
    eventos = eventos.sort_values(["ticker", "fecha", "orden"], kind="stable")

    estado = {}  
    for ev in eventos.itertuples():
        e = estado.setdefault(ev.ticker, {"acciones": 0.0, "coste": 0.0, "realizado": 0.0})

        if ev.tipo == "compra":
            e["acciones"] += ev.cantidad
            e["coste"] += np.multiply(ev.cantidad, ev.precio) + ev.comision
        elif ev.tipo == "venta":
            if ev.cantidad > e["acciones"] + 1e-9:
                raise ValueError(
                    f"Venta de {ev.cantidad} {ev.ticker} el {ev.fecha}, "
                    f"pero solo hay {e['acciones']}."
                )
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



def valor_historico(conn,cartera_id,hasta=None):

    if hasta is None:
        hasta = date.today().isoformat()

    ops = pd.read_sql_query(""" SELECT fecha,ticker,
    CASE WHEN tipo = 'compra' THEN cantidad ELSE -cantidad END AS neto FROM operaciones
    WHERE cartera_id = ? AND tipo IN ('compra','venta') AND fecha <=?""", conn, params=(cartera_id,hasta),parse_dates=["fecha"])   

    if ops.empty:
        return pd.Series(dtype=float,name = "valor_eur")

    tickers = sorted(ops["ticker"].unique())
    huecos = ", ".join("?"*len(tickers))  
    dias = pd.date_range(ops["fecha"].min(),hasta, freq = "D")

    precios_largos = pd.read_sql_query(f""" SELECT fecha, ticker, cierre FROM precios_diarios
    WHERE ticker IN ({huecos}) AND fecha <=?;""",conn, params=(*tickers,hasta), parse_dates=["fecha"],) 

    precios = precios_largos.pivot(index = "fecha",columns="ticker",values="cierre")
    dias_bolsa = precios.index[precios.index >= dias[0]]
    precios = precios.reindex(index = dias,columns = tickers).ffill()

    splits_largos = pd.read_sql_query(f""" SELECT ticker,fecha,valor FROM eventos
    WHERE tipo = 'split' AND ticker in ({huecos}) AND fecha <=?;""",conn, params=(*tickers,hasta), parse_dates=["fecha"])
    
    splits = splits_largos.pivot(index = "fecha", columns="ticker",values="valor")
    factor = splits.reindex(index=dias,columns = tickers).fillna(1).cumprod()

    neto = ops.pivot_table(index="fecha",columns="ticker",values="neto",aggfunc="sum")
    neto = neto.reindex(index = dias ,columns=tickers).fillna(0)
    acciones = (neto/factor).cumsum()*factor

    valor = acciones*precios #en usd

    divisas = dict(conn.execute(f"SELECT ticker, divisa FROM activos WHERE ticker IN ({huecos});",tickers).fetchall())
    fx_largos = pd.read_sql_query("""SELECT fecha, divisa, tasa FROM tipos_cambio WHERE fecha<=?;""", conn, params=(hasta,),parse_dates=["fecha"])    
    fx_largos = fx_largos.pivot(index="fecha",columns="divisa",values="tasa").reindex(dias).ffill()
    for t in tickers:
        if divisas[t] != "EUR":
            valor[t] = valor[t]/ fx_largos[divisas[t]] #lo paso a EUR

    sin_precio = (acciones.abs() > 1e-9) & valor.isna() #acciones con un casi 0 no nos sirven
    if sin_precio.any().any():
        faltan = sorted(valor.columns[sin_precio.any()])
        raise ValueError(f"Faltan precios o tipos de cambio para: {', '.join(faltan)}. "
                         "Ejecuta actualizar.py.")

    total = valor.sum(axis=1)
    return total.loc[dias_bolsa].rename("valor_eur")
    

        







    

