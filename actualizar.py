import warnings

from cartera.db import conectar, crear_tablas
from cartera.datos import actualizar_precios, actualizar_tipo_cambio

warnings.filterwarnings("ignore", message="The inplace keyword")


def main():
    conn = conectar()
    try:
        crear_tablas(conn)

        tickers = [t for (t,) in conn.execute("SELECT ticker FROM activos;").fetchall()]
        if not tickers:
            print("No hay activos en la tabla activos.")
        else:
            resumen = actualizar_precios(conn, tickers)
            for ticker, filas in resumen.items():
                print(f"{ticker}: {filas} filas")

        filas_fx = actualizar_tipo_cambio(conn)
        print(f"EURUSD: {filas_fx} filas")
    finally:
        conn.close()


if __name__ == "__main__":
    main()