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
    precios = precios.reindex(precios.index.union(dias)).ffill().reindex(index=dias, columns=tickers)

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
    fx = fx_largos.pivot(index="fecha", columns="divisa", values="tasa")
    fx = fx.reindex(fx.index.union(dias)).ffill().reindex(dias)
    for t in tickers:
        if divisas[t] != "EUR":
            valor[t] = valor[t]/ fx[divisas[t]] #lo paso a EUR

    sin_precio = (acciones.abs() > 1e-9) & valor.isna() #acciones con un casi 0 no nos sirven
    if sin_precio.any().any():
        faltan = sorted(valor.columns[sin_precio.any()])
        raise ValueError(f"Faltan precios o tipos de cambio para: {', '.join(faltan)}. "
                         "Ejecuta actualizar.py.")

    total = valor.sum(axis=1)
    return total.loc[dias_bolsa].rename("valor_eur")




def tipos_cambio_diarios(conn, dias):
    fx_largos = pd.read_sql_query(
    "SELECT fecha, divisa, tasa FROM tipos_cambio WHERE fecha <= ?;",
    conn, params=(dias[-1].strftime("%Y-%m-%d"),), parse_dates=["fecha"])
    fx = fx_largos.pivot(index="fecha", columns="divisa", values="tasa")
    fx = fx.reindex(fx.index.union(dias)).ffill().reindex(dias)
    fx["EUR"] = 1.0
    return fx


def flujos_en_euros(conn, cartera_id, hasta=None):
    if hasta is None:
        hasta = date.today().isoformat()
    ops = pd.read_sql_query(
        """SELECT o.fecha, o.tipo, o.cantidad * o.precio AS bruto, o.comision, a.divisa
        FROM operaciones o JOIN activos a ON o.ticker = a.ticker
        WHERE o.cartera_id = ? AND o.fecha <= ?;""",
        conn, params=(cartera_id, hasta), parse_dates=["fecha"])
    if ops.empty:
        return pd.DataFrame(columns=["fecha", "tipo", "importe_eur", "comision_eur"])

    dias = pd.date_range(ops["fecha"].min(), hasta, freq="D")
    fx = tipos_cambio_diarios(conn, dias)
    tasa = [fx.at[f, d] for f, d in zip(ops["fecha"], ops["divisa"])]
    ops["importe_eur"] = ops["bruto"] / tasa
    ops["comision_eur"] = ops["comision"] / tasa
    return ops[["fecha", "tipo", "importe_eur", "comision_eur"]]


def rentabilidad_twr(conn,cartera_id,hasta=None):
    valor = valor_historico(conn,cartera_id,hasta)
    if len(valor)<2:
        return pd.Series(dtype=float,name = "rent_diaria")

    fl = flujos_en_euros(conn,cartera_id,hasta)
    signo = fl["tipo"].map({"compra":1,"venta":-1,"dividendo":-1})
    fl["flujo"] = fl["importe_eur"]*signo
    flujo_dia = fl.groupby("fecha")["flujo"].sum()

    #flujos findes/festivos --> al día siguiente de bolsa
    dias = pd.date_range(min(flujo_dia.index.min(),valor.index.min()),valor.index.max(),freq="D")
    acumulado = flujo_dia.reindex(dias,fill_value=0).cumsum()
    flujo_bolsa = acumulado.reindex(valor.index).diff()
    flujo_bolsa.iloc[0] = acumulado.loc[valor.index[0]]

    anterior = valor.shift(1)
    rent = (valor-flujo_bolsa)/anterior-1
    rent = rent.where(anterior > 1e-9)
    return rent.iloc[1:].fillna(0).rename("rent_diaria")

def resumen_cartera(conn,cartera_id,hasta=None):
    valor = valor_historico(conn,cartera_id,hasta)
    fl = flujos_en_euros(conn,cartera_id,hasta)
    compras = fl[fl["tipo"] == "compra"]
    ventas = fl[fl["tipo"] == "venta"]
    divid = fl[fl["tipo"] == "dividendo"]

    aportado = float((compras["importe_eur"] + compras["comision_eur"]).sum())
    dividendos = float((divid["importe_eur"] - divid["comision_eur"]).sum())
    retirado = float((ventas["importe_eur"] - ventas["comision_eur"]).sum()) + dividendos
    valor_actual = float(valor.iloc[-1]) if len(valor) else 0.0
    rent = rentabilidad_twr(conn, cartera_id, hasta)

    return {
        "valor_actual": valor_actual,
        "aportado": aportado,
        "retirado": retirado,
        "ganancia_total": valor_actual+retirado-aportado,
        "dividendos_netos": dividendos,
        "comisiones": float(fl.loc[fl["tipo"] != "dividendo", "comision_eur"].sum()),
        "twr": float(np.add(1,rent).prod() - 1)}
    

        







    

