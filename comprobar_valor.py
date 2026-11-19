import pandas as pd

from cartera.db import conectar, crear_tablas
from cartera.operaciones import registrar_operacion
from cartera.valoracion import valor_historico

DIAS = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
TASA = 1.20


def preparar(precio_dia8, con_split):
    conn = conectar(":memory:")
    crear_tablas(conn)

    conn.execute(
        "INSERT INTO activos (ticker, nombre, sector, divisa) VALUES (?, ?, ?, ?)",
        ("X", "Activo X", "Prueba", "USD"),
    )
    conn.execute("INSERT INTO carteras (id, nombre) VALUES (?, ?)", (1, "Prueba"))

    precios = [100, 105, 110, precio_dia8]
    conn.executemany(
        "INSERT INTO precios_diarios (fecha, ticker, cierre, volumen) VALUES (?, ?, ?, ?)",
        [(dia, "X", precio, 0) for dia, precio in zip(DIAS, precios)],
    )
    conn.executemany(
        "INSERT INTO tipos_cambio (fecha, divisa, tasa) VALUES (?, ?, ?)",
        [(dia, "USD", TASA) for dia in DIAS],
    )
    if con_split:
        conn.execute(
            "INSERT INTO eventos (fecha, ticker, tipo, valor) VALUES (?, ?, ?, ?)",
            ("2026-01-08", "X", "split", 2),
        )
    conn.commit()

    registrar_operacion(conn, 1, "X", "2026-01-05", "compra", 10, 100)
    registrar_operacion(conn, 1, "X", "2026-01-07", "venta", 4, 110)
    return conn


def comprobar(nombre, precio_dia8, con_split, esperado):
    conn = preparar(precio_dia8, con_split)
    resultado = valor_historico(conn, 1, DIAS[-1])
    conn.close()

    resultado.index = pd.to_datetime(resultado.index).strftime("%Y-%m-%d")
    print(f"\n{nombre}")
    todo_bien = True
    for dia, valor_esperado in esperado.items():
        obtenido = resultado.get(dia)
        ok = obtenido is not None and abs(obtenido - valor_esperado) < 0.01
        todo_bien = todo_bien and ok
        marca = "OK " if ok else "MAL"
        print(f"  {marca} {dia}: esperado {valor_esperado:8.2f}  obtenido {obtenido}")
    print("  Resultado:", "correcto" if todo_bien else "HAY DIFERENCIAS")
    return todo_bien


if __name__ == "__main__":
    caso1 = comprobar(
        "Caso 1: sin split",
        precio_dia8=120,
        con_split=False,
        esperado={
            "2026-01-05": 833.33,
            "2026-01-06": 875.00,
            "2026-01-07": 550.00,
            "2026-01-08": 600.00,
        },
    )
    caso2 = comprobar(
        "Caso 2: split 2x1 el día 8 y precio 60",
        precio_dia8=60,
        con_split=True,
        esperado={
            "2026-01-05": 833.33,
            "2026-01-06": 875.00,
            "2026-01-07": 550.00,
            "2026-01-08": 600.00,
        },
    )
    print("\nTODO CORRECTO" if caso1 and caso2 else "\nREVISA LOS CASOS MARCADOS CON MAL")