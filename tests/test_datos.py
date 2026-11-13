import pandas as pd
import pytest

from cartera.db import conectar, crear_tablas
from cartera.datos import guardar_precios


@pytest.fixture
def conn():
    conn = conectar(":memory:")
    crear_tablas(conn)
    conn.execute(
        "INSERT INTO activos (ticker, nombre, sector, divisa) VALUES (?, ?, ?, ?)",
        ("KO", "Coca-Cola", "Consumo", "USD"),
    )
    conn.commit()
    yield conn
    conn.close()


def precios_de_prueba():
    return pd.DataFrame({
        "fecha": ["2026-10-19", "2026-10-20", "2026-10-21"],
        "ticker": ["KO", "KO", "KO"],
        "cierre": [60.10, 60.50, 59.80],
        "volumen": [1000, 1200, 900],
    })


def contar_precios(conn):
    return conn.execute("SELECT COUNT(*) FROM precios_diarios;").fetchone()[0]


def test_guardar_dos_veces_no_duplica(conn):
    df = precios_de_prueba()

    guardar_precios(conn, df)
    assert contar_precios(conn) == 3

    guardar_precios(conn, df)
    assert contar_precios(conn) == 3