from datetime import date, timedelta
import pandas as pd
import yfinance as yf


def descargar_datos(tickers, inicio, fin):
    return yf.download(tickers, start=inicio, end=fin, progress=False)


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

        guardar_precios(conn, df)
        resumen[ticker] = len(df)

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