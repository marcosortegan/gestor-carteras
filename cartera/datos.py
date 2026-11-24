from datetime import date, timedelta

import numpy as np
import pandas as pd
import yfinance as yf


def descargar_datos(tickers, inicio, fin):
    return yf.download(tickers, start=inicio, end=fin, auto_adjust=False, progress=False)


def reordenar(dat):
    xd = dat.stack(level="Ticker", future_stack=True).reset_index()
    xd = xd.rename(columns={"Date": "fecha", "Ticker": "ticker",
                            "Close": "cierre", "Volume": "volumen"})
    xd = xd[["fecha", "ticker", "cierre", "volumen"]]
    xd.columns.name = None
    xd = xd.dropna(subset=["cierre"])
    xd["fecha"] = pd.to_datetime(xd["fecha"]).dt.strftime("%Y-%m-%d")
    xd["volumen"] = xd["volumen"].fillna(0).astype(int)
    return xd


def descargar_precios(tickers, inicio, fin):
    dat = descargar_datos(tickers, inicio, fin)
    if dat.empty:
        return pd.DataFrame(columns=["fecha", "ticker", "cierre", "volumen"])
    return reordenar(dat)


def guardar_precios(conn, df):
    df.to_sql("temporal", conn, if_exists="replace", index=False)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO precios_diarios (fecha, ticker, cierre, volumen)
        SELECT fecha, ticker, cierre, volumen FROM temporal;
    """)
    cur.execute("DROP TABLE IF EXISTS temporal;")
    conn.commit()


def factor_futuro(fechas, splits):
    return np.array([splits[splits.index > f].prod() for f in fechas], dtype=float)


def splits_guardados(conn, ticker):
    df = pd.read_sql_query("SELECT fecha, valor FROM eventos WHERE tipo = 'split' AND ticker = ?;",
                           conn, params=(ticker,), parse_dates=["fecha"])
    return df.set_index("fecha")["valor"]


def desajustar(df, splits):
    if splits.empty or df.empty:
        return df
    f = factor_futuro(pd.to_datetime(df["fecha"]), splits)
    df = df.copy()
    df["cierre"] = df["cierre"] * f
    df["volumen"] = (df["volumen"] / f).round().astype(int)
    return df


def actualizar_precios(conn, tickers):
    hoy = date.today()
    fin = hoy + timedelta(days=1)
    hace_5_anos = hoy - timedelta(days=5 * 365)

    filas = conn.execute("""
        SELECT ticker, MAX(fecha)
        FROM precios_diarios
        GROUP BY ticker;
    """).fetchall()
    ultimas = {ticker: date.fromisoformat(fecha) for ticker, fecha in filas}

    resumen = {}
    for ticker in tickers:
        if ticker in ultimas:
            inicio = ultimas[ticker] + timedelta(days=1)
        else:
            inicio = hace_5_anos

        if inicio > hoy:
            resumen[ticker] = 0
            continue

        df = descargar_precios([ticker], inicio, fin)
        if df.empty:
            resumen[ticker] = 0
            continue

        df = desajustar(df, splits_guardados(conn, ticker))
        guardar_precios(conn, df)
        resumen[ticker] = len(df)

    return resumen


def a_fechas(serie):
    idx = pd.to_datetime(serie.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return pd.Series(serie.values, index=idx.normalize(), dtype=float)


def actualizar_eventos(conn, tickers):
    desde = pd.Timestamp(date.today() - timedelta(days=5 * 365))
    resumen = {}
    for ticker in tickers:
        t = yf.Ticker(ticker)
        splits = a_fechas(t.splits)
        splits = splits[(splits > 0) & (splits.index >= desde)]
        divs = a_fechas(t.dividends)
        divs = divs[(divs > 0) & (divs.index >= desde)]
        if not divs.empty and not splits.empty:
            divs = divs * factor_futuro(divs.index, splits)

        filas = [(f.strftime("%Y-%m-%d"), ticker, "split", float(v)) for f, v in splits.items()]
        filas += [(f.strftime("%Y-%m-%d"), ticker, "dividendo", float(v)) for f, v in divs.items()]
        if not filas:
            resumen[ticker] = 0
            continue
        cur = conn.executemany(
            "INSERT OR IGNORE INTO eventos (fecha, ticker, tipo, valor) VALUES (?, ?, ?, ?);", filas)
        conn.commit()
        resumen[ticker] = cur.rowcount
    return resumen


def actualizar_tipo_cambio(conn):
    hoy = date.today()
    fin = hoy + timedelta(days=1)

    fila = conn.execute(
        "SELECT MAX(fecha) FROM tipos_cambio WHERE divisa = 'USD';"
    ).fetchone()

    if fila[0] is None:
        inicio = hoy - timedelta(days=5 * 365)
    else:
        inicio = date.fromisoformat(fila[0]) + timedelta(days=1)

    if inicio > hoy:
        return 0

    dat = yf.download("EURUSD=X", start=inicio, end=fin, progress=False)
    if dat.empty:
        return 0

    cierre = dat["Close"]
    if isinstance(cierre, pd.DataFrame):
        cierre = cierre.iloc[:, 0]

    df = cierre.dropna().reset_index()
    df.columns = ["fecha", "tasa"]
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m-%d")
    df["divisa"] = "USD"

    conn.executemany(
        "INSERT OR IGNORE INTO tipos_cambio (fecha, divisa, tasa) VALUES (?, ?, ?)",
        df[["fecha", "divisa", "tasa"]].itertuples(index=False, name=None),
    )
    conn.commit()
    return len(df)