import pytest

from cartera.operaciones import borrar_cartera, crear_cartera, listar_carteras, registrar_operacion


def test_crear_y_listar(conn):
    crear_cartera(conn, "A")
    crear_cartera(conn, "B")
    assert list(listar_carteras(conn)["nombre"]) == ["A", "B"]


def test_cartera_repetida(conn):
    crear_cartera(conn, "A")
    with pytest.raises(ValueError, match="Ya existe"):
        crear_cartera(conn, "A")


def test_borrar_cartera(conn, cartera):
    vacia = crear_cartera(conn, "Vacía")
    assert borrar_cartera(conn, vacia) is True
    assert borrar_cartera(conn, 999) is False
    with pytest.raises(ValueError, match="operaciones"):
        borrar_cartera(conn, cartera)


def test_vender_de_mas(conn, cartera):
    with pytest.raises(ValueError):
        registrar_operacion(conn, cartera, "X", "2026-01-08", "venta", 7, 120)


def test_vender_todo(conn, cartera):
    registrar_operacion(conn, cartera, "X", "2026-01-08", "venta", 6, 120)
    with pytest.raises(ValueError):
        registrar_operacion(conn, cartera, "X", "2026-01-08", "venta", 1, 120)


def test_venta_que_rompe_una_posterior(conn, cartera):
    with pytest.raises(ValueError, match="venta ya registrada"):
        registrar_operacion(conn, cartera, "X", "2026-01-06", "venta", 7, 105)


def test_dividendo_sin_acciones(conn):
    cartera_id = crear_cartera(conn, "Vacía")
    with pytest.raises(ValueError, match="No tenías"):
        registrar_operacion(conn, cartera_id, "X", "2026-01-06", "dividendo", 10, 1)


@pytest.mark.parametrize("ticker, fecha, motivo", [
    ("TSLA", "2026-01-06", "activos"),
    ("X", "2099-01-01", "futura"),
    ("X", "06/01/2026", "formato"),
])
def test_datos_malos(conn, cartera, ticker, fecha, motivo):
    with pytest.raises(ValueError, match=motivo):
        registrar_operacion(conn, cartera, ticker, fecha, "compra", 1, 100)


def test_cartera_que_no_existe(conn):
    with pytest.raises(ValueError, match="No existe"):
        registrar_operacion(conn, 999, "X", "2026-01-06", "compra", 1, 100)