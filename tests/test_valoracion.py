import pytest

from cartera.operaciones import crear_cartera, registrar_operacion
from cartera.valoracion import acciones_en_fecha, posiciones, rentabilidad_twr, resumen_cartera, valor_historico

HASTA = "2026-01-08"


def test_posicion_y_coste_medio(conn, cartera):
    pos = posiciones(conn, cartera, HASTA)
    assert pos.loc["X", "acciones"] == pytest.approx(6)
    assert pos.loc["X", "coste_medio"] == pytest.approx(100.20)


def test_plusvalia_realizada(conn, cartera):
    pos = posiciones(conn, cartera, HASTA)
    assert pos.loc["X", "plusvalia_realizada"] == pytest.approx(37.20)


def test_antes_de_la_venta(conn, cartera):
    pos = posiciones(conn, cartera, "2026-01-06")
    assert pos.loc["X", "acciones"] == pytest.approx(10)


def test_cartera_vacia(conn):
    cartera_id = crear_cartera(conn, "Vacía")
    assert posiciones(conn, cartera_id).empty


def test_posicion_cerrada(conn, cartera):
    registrar_operacion(conn, cartera, "X", "2026-01-08", "venta", 6, 120, 2)
    assert posiciones(conn, cartera, HASTA).empty
    cerradas = posiciones(conn, cartera, HASTA, incluir_cerradas=True)
    assert cerradas.loc["X", "plusvalia_realizada"] == pytest.approx(37.20 + 116.80)


def test_split(conn, con_split):
    pos = posiciones(conn, con_split, HASTA)
    assert pos.loc["X", "acciones"] == pytest.approx(12)
    assert pos.loc["X", "coste_medio"] == pytest.approx(50.10)
    assert pos.loc["X", "plusvalia_realizada"] == pytest.approx(37.20)


def test_vender_todo_tras_split(conn, con_split):
    assert acciones_en_fecha(conn, con_split, "X", HASTA) == pytest.approx(12)
    registrar_operacion(conn, con_split, "X", HASTA, "venta", 12, 60, 1)
    assert posiciones(conn, con_split, HASTA).empty


def test_valor_en_euros(conn, cartera):
    valor = valor_historico(conn, cartera, HASTA)
    assert list(valor.round(2)) == [833.33, 875.00, 550.00, 600.00]


def test_valor_con_split(conn, con_split):
    assert valor_historico(conn, con_split, HASTA).iloc[-1] == pytest.approx(600.00)


def test_compra_en_sabado(conn):
    conn.execute("INSERT INTO precios_diarios (ticker, fecha, cierre) VALUES ('X', '2026-01-12', 120);")
    conn.execute("INSERT INTO tipos_cambio (divisa, fecha, tasa) VALUES ('USD', '2026-01-12', 1.2);")
    cartera_id = crear_cartera(conn, "Finde")
    registrar_operacion(conn, cartera_id, "X", "2026-01-10", "compra", 1, 120)
    valor = valor_historico(conn, cartera_id, "2026-01-12")
    assert valor.iloc[-1] == pytest.approx(100.00)


def test_faltan_precios(conn):
    conn.execute("INSERT INTO activos (ticker, nombre, divisa) VALUES ('Y', 'Sin precios', 'EUR');")
    cartera_id = crear_cartera(conn, "Huecos")
    registrar_operacion(conn, cartera_id, "Y", "2026-01-05", "compra", 1, 10)
    with pytest.raises(ValueError, match="(?i)faltan precios"):
        valor_historico(conn, cartera_id, HASTA)


def test_rent_diarias(conn, cartera):
    rent = rentabilidad_twr(conn, cartera, HASTA)
    assert list(rent.round(6)) == [0.05, 0.045714, 0.090909]


def test_twr(conn, cartera):
    rent = rentabilidad_twr(conn, cartera, HASTA)
    assert (1 + rent).prod() - 1 == pytest.approx(0.197818, abs=1e-6)


def test_resumen(conn, cartera):
    r = resumen_cartera(conn, cartera, HASTA)
    assert r["valor_actual"] == pytest.approx(600.00)
    assert r["aportado"] == pytest.approx(835.00)
    assert r["retirado"] == pytest.approx(365.00)
    assert r["ganancia_total"] == pytest.approx(130.00)
    assert r["comisiones"] == pytest.approx(4 / 1.2)
    assert r["dividendos_netos"] == pytest.approx(0)


def test_ganancia_cuadra_en_dolares(conn, cartera):
    pos = posiciones(conn, cartera, HASTA)
    latente = 6 * 120 - pos.loc["X", "coste_total"]
    en_dolares = pos.loc["X", "plusvalia_realizada"] + latente
    assert resumen_cartera(conn, cartera, HASTA)["ganancia_total"] == pytest.approx(en_dolares / 1.2)


def test_dividendo_en_sabado(conn, cartera):
    conn.execute("INSERT INTO precios_diarios (ticker, fecha, cierre) VALUES ('X', '2026-01-12', 120);")
    conn.execute("INSERT INTO tipos_cambio (divisa, fecha, tasa) VALUES ('USD', '2026-01-12', 1.2);")
    registrar_operacion(conn, cartera, "X", "2026-01-10", "dividendo", 6, 1, 0.12)
    rent = rentabilidad_twr(conn, cartera, "2026-01-12")
    assert rent.loc["2026-01-12"] == pytest.approx(4.90 / 600)
    assert resumen_cartera(conn, cartera, "2026-01-12")["dividendos_netos"] == pytest.approx(4.90)