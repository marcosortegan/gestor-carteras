from cartera.db import conectar, crear_tablas
from cartera.operaciones import borrar_cartera, crear_cartera, registrar_operacion
from cartera.valoracion import acciones_en_fecha, posiciones, resumen_cartera

NOMBRE = "Demo"
COMISION = 3.0
RETENCION = 0.19

OPERACIONES = [
    ("2025-12-01", "BBVA.MC", "compra", 300),
    ("2025-12-01", "KO", "compra", 40),
    ("2025-12-15", "REP.MC", "compra", 150),
    ("2026-01-12", "JPM", "compra", 10),
    ("2026-02-02", "TEF.MC", "compra", 500),
    ("2026-03-02", "BBVA.MC", "compra", 100),
    ("2026-04-06", "KO", "compra", 20),
    ("2026-05-04", "REP.MC", "venta", 50),
    ("2026-06-01", "JPM", "compra", 5),
    ("2026-07-01", "TEF.MC", "venta", 200),
    ("2026-09-01", "BBVA.MC", "venta", 150),
    ("2026-10-01", "KO", "compra", 15),
]


def ultimo_cierre(conn, ticker, fecha):
    fila = conn.execute("""SELECT fecha, cierre FROM precios_diarios
    WHERE ticker = ? AND fecha <= ? ORDER BY fecha DESC LIMIT 1;""", (ticker, fecha)).fetchone()
    if fila is None:
        raise ValueError(f"No hay precios de {ticker} hasta el {fecha}, ejecuta actualizar.py")
    return fila


def borrar_si_existe(conn, nombre):
    fila = conn.execute("SELECT id FROM carteras WHERE nombre = ?;", (nombre,)).fetchone()
    if fila is not None:
        conn.execute("DELETE FROM operaciones WHERE cartera_id = ?;", (fila[0],))
        conn.commit()
        borrar_cartera(conn, fila[0])


def meter_dividendos(conn, cartera_id, retencion=RETENCION):
    tickers = [t for (t,) in conn.execute(
        "SELECT DISTINCT ticker FROM operaciones WHERE cartera_id = ?;", (cartera_id,)).fetchall()]
    if not tickers:
        return 0
    primera = conn.execute(
        "SELECT MIN(fecha) FROM operaciones WHERE cartera_id = ?;", (cartera_id,)).fetchone()[0]

    huecos = ", ".join("?" * len(tickers))
    divs = conn.execute(f"""SELECT ticker, fecha, valor FROM eventos
    WHERE tipo = 'dividendo' AND fecha >= ? AND ticker IN ({huecos}) ORDER BY fecha;""",
                        (primera, *tickers)).fetchall()

    n = 0
    for ticker, fecha, por_accion in divs:
        acciones = acciones_en_fecha(conn, cartera_id, ticker, fecha)
        if acciones > 0:
            retenido = round(acciones * por_accion * retencion, 2)
            registrar_operacion(conn, cartera_id, ticker, fecha, "dividendo", acciones, por_accion, retenido)
            n += 1
    return n


def crear_demo(conn, nombre=NOMBRE, ops=OPERACIONES):
    borrar_si_existe(conn, nombre)
    cartera_id = crear_cartera(conn, nombre)
    for fecha, ticker, tipo, cantidad in ops:
        dia, cierre = ultimo_cierre(conn, ticker, fecha)
        registrar_operacion(conn, cartera_id, ticker, dia, tipo, cantidad, cierre, COMISION)
    n = meter_dividendos(conn, cartera_id)
    print(f"Cartera {nombre} creada con {len(ops)} operaciones y {n} dividendos")
    return cartera_id


if __name__ == "__main__":
    conn = conectar()
    try:
        crear_tablas(conn)
        cartera_id = crear_demo(conn)

        print("\nPosiciones:")
        print(posiciones(conn, cartera_id).round(2))

        print("\nResumen (EUR):")
        for k, v in resumen_cartera(conn, cartera_id).items():
            if k == "twr":
                print(f"  {k:<18}{v:>12.2%}")
            else:
                print(f"  {k:<18}{v:>12,.2f}")
    finally:
        conn.close()