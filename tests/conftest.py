import pytest

from cartera.db import conectar, crear_tablas
from cartera.operaciones import crear_cartera, registrar_operacion

PRECIOS_X = {
    "2026-01-05": 100.0,
    "2026-01-06": 105.0,
    "2026-01-07": 110.0,
    "2026-01-08": 120.0,
}
TASA = 1.20


@pytest.fixture
def conn():
    conn = conectar(":memory:")
    crear_tablas(conn)
    conn.execute("INSERT INTO activos (ticker, nombre, sector, divisa) VALUES ('X', 'Empresa X', NULL, 'USD');")
    for fecha, cierre in PRECIOS_X.items():
        conn.execute("INSERT INTO precios_diarios (ticker, fecha, cierre) VALUES ('X', ?, ?);", (fecha, cierre))
        conn.execute("INSERT INTO tipos_cambio (divisa, fecha, tasa) VALUES ('USD', ?, ?);", (fecha, TASA))
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def cartera(conn):
    cartera_id = crear_cartera(conn, "Prueba")
    registrar_operacion(conn, cartera_id, "X", "2026-01-05", "compra", 10, 100, 2)
    registrar_operacion(conn, cartera_id, "X", "2026-01-07", "venta", 4, 110, 2)
    return cartera_id


@pytest.fixture
def con_split(conn, cartera):
    conn.execute("UPDATE precios_diarios SET cierre = 60 WHERE ticker = 'X' AND fecha = '2026-01-08';")
    conn.execute("INSERT INTO eventos (ticker, fecha, tipo, valor) VALUES ('X', '2026-01-08', 'split', 2);")
    conn.commit()
    return cartera