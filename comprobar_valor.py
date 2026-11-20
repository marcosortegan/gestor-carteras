import pandas as pd

from cartera.db import conectar, crear_tablas
from cartera.operaciones import registrar_operacion
from cartera.valoracion import resumen_cartera, valor_historico

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


def comparar(etiqueta, obtenido, esperado):
    ok = obtenido is not None and abs(obtenido - esperado) < 0.01
    marca = "OK " if ok else "MAL"
    print(f"  {marca} {etiqueta}: esperado {esperado:10.4f}  obtenido {obtenido}")
    return ok


def comprobar_valor(nombre, precio_dia8, con_split, esperado):
    conn = preparar(precio_dia8, con_split)
    resultado = valor_historico(conn, 1, DIAS[-1])
    conn.close()

    resultado.index = pd.to_datetime(resultado.index).strftime("%Y-%m-%d")
    print(f"\n{nombre}")
    todo_bien = True
    for dia, valor_esperado in esperado.items():
        todo_bien &= comparar(dia, resultado.get(dia), valor_esperado)
    print("  Resultado:", "correcto" if todo_bien else "HAY DIFERENCIAS")
    return todo_bien


def comprobar_resumen(nombre, precio_dia8, con_split, esperado):
    conn = preparar(precio_dia8, con_split)
    resumen = resumen_cartera(conn, 1, DIAS[-1])
    conn.close()

    print(f"\n{nombre}")
    todo_bien = True
    for clave, valor_esperado in esperado.items():
        todo_bien &= comparar(clave, resumen.get(clave), valor_esperado)
    print("  Resultado:", "correcto" if todo_bien else "HAY DIFERENCIAS")
    return todo_bien


VALOR_ESPERADO = {
    "2026-01-05": 833.33,
    "2026-01-06": 875.00,
    "2026-01-07": 550.00,
    "2026-01-08": 600.00,
}

RESUMEN_ESPERADO = {
    "valor_actual": 600.00,
    "aportado": 833.33,
    "retirado": 366.67,
    "ganancia_total": 133.33,
    "dividendos_netos": 0.00,
    "comisiones": 0.00,
    "twr": 0.20,
}


if __name__ == "__main__":
    resultados = [
        comprobar_valor("Valor: sin split", 120, False, VALOR_ESPERADO),
        comprobar_valor("Valor: split 2x1 el día 8 y precio 60", 60, True, VALOR_ESPERADO),
        comprobar_resumen("Resumen: sin split", 120, False, RESUMEN_ESPERADO),
        comprobar_resumen("Resumen: split 2x1 el día 8 y precio 60", 60, True, RESUMEN_ESPERADO),
    ]
    print("\nTODO CORRECTO" if all(resultados) else "\nREVISA LOS CASOS MARCADOS CON MAL")