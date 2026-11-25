import numpy as np
import pandas as pd
import pytest

from cartera.simulacion import simular_gbm, conv_orden_fuerte, trayectorias_cartera


def test_forma_y_s0():
    S = simular_gbm(100, 0.08, 0.2, 1, 50, 1000, semilla=1)
    assert S.shape == (1000, 51)
    assert np.all(S[:, 0] == 100)


def test_misma_semilla():
    a = simular_gbm(100, 0.08, 0.2, 1, 50, 1000, semilla=7)
    b = simular_gbm(100, 0.08, 0.2, 1, 50, 1000, semilla=7)
    np.testing.assert_array_equal(a, b)


def test_media_final():
    n = 100_000
    ST = simular_gbm(100, 0.08, 0.2, 1, 50, n, semilla=3)[:, -1]
    et = ST.std(ddof=1) / np.sqrt(n)
    assert abs(ST.mean() - 100 * np.exp(0.08)) < 4 * et


def test_orden_fuerte():
    _, pendiente = conv_orden_fuerte(100, 0.08, 0.2, 1)
    assert 0.4 < pendiente < 0.6


def test_correlaciones_cholesky():
    C = np.array([[1, 0.6, 0.2], [0.6, 1, -0.3], [0.2, -0.3, 1]])
    L = np.linalg.cholesky(C)
    Z = np.random.default_rng(5).standard_normal((200_000, 3))
    X = Z @ L.T
    np.testing.assert_allclose(np.corrcoef(X.T), C, atol=0.01)


def test_cartera_sin_volatilidad():
    dias = 252
    m = np.array([0.0004, 0.0002])
    ruido = np.random.default_rng(9).standard_normal((500, 2)) * 1e-9
    rlog = pd.DataFrame(m + ruido, columns=["A", "B"])
    valores = pd.Series([1000.0, 500.0], index=["A", "B"])
    fin = trayectorias_cartera(rlog, valores, dias=dias, n=100, semilla=0)[:, -1]
    esperado = (valores.values * np.exp(m * dias)).sum()
    np.testing.assert_allclose(fin, esperado, rtol=1e-5)