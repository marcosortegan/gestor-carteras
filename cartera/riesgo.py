import numpy as np
import pandas as pd

DIAS = 252

def rentabilidad_anual(r):
    return (1 + r).prod() ** (DIAS / r.count()) - 1

def volatilidad_anual(r):
    return r.std() * np.sqrt(DIAS)

def volatilidad_ewma(r, lam=0.94):
    var = (r**2).ewm(alpha=1-lam,adjust = False).mean()
    return np.sqrt(var.shift(1) * DIAS)

def rf_diario(rf_anual):
    """Tipo libre de riesgo anual pasado a diario (compuesto)."""
    return (1 + rf_anual) ** (1 / DIAS) - 1


def sharpe(r, rf_anual=0.0):
    """Ratio de Sharpe anualizado."""
    exceso = r - rf_diario(rf_anual)
    return exceso.mean() / exceso.std() * np.sqrt(DIAS)


def sortino(r, rf_anual=0.0):
    """Como Sharpe, pero solo penaliza la volatilidad de las caídas."""
    exceso = r - rf_diario(rf_anual)
    abajo = np.sqrt((exceso.clip(upper=0) ** 2).mean())
    return exceso.mean() / abajo * np.sqrt(DIAS)

def drawdowns(r):
    """Caída desde el máximo anterior, día a día (0 o negativa)."""
    riqueza = (1 + r).cumprod()
    return riqueza / riqueza.cummax() - 1

def drawdown_maximo(r):
    """Peor caída, con las fechas del pico, del valle y de la recuperación."""
    riqueza = (1 + r).cumprod()
    dd = drawdowns(r)
    valle = dd.idxmin()
    pico = riqueza.loc[:valle].idxmax()
    despues = riqueza.loc[valle:]
    recuperado = despues[despues >= riqueza.loc[pico]]
    return {
        "maximo": dd.min(),
        "pico": pico,
        "valle": valle,
        "recuperacion": recuperado.index[0] if len(recuperado) else None}

def alinear(r, rb):
    """Junta dos series de rentabilidades en las fechas que tienen en común."""
    riqueza = pd.concat([(1 + r).cumprod(), (1 + rb).cumprod()], axis=1, join="inner")
    return riqueza.pct_change().dropna()


def frente_a_benchmark(r, rb):
    a = alinear(r, rb)
    x, b = a.iloc[:, 0], a.iloc[:, 1]
    beta = x.cov(b) / b.var()
    dif = x - b
    te = dif.std() * np.sqrt(DIAS)
    return {
        "beta": beta,
        "correlacion": x.corr(b),
        "tracking_error": te,
        "ratio_informacion": dif.mean() * DIAS / te if te > 0 else np.nan,
    }

def tabla_riesgo(rentabilidades, benchmark, rf_anual=0.02):
    filas = {}
    for nombre, r in rentabilidades.items():
        r = r.dropna()
        filas[nombre] = {
            "rent_anual": rentabilidad_anual(r),
            "vol_anual": volatilidad_anual(r),
            "sharpe": sharpe(r, rf_anual),
            "sortino": sortino(r, rf_anual),
            "max_drawdown": drawdown_maximo(r)["maximo"],
            **frente_a_benchmark(r, benchmark),
        }
    return pd.DataFrame(filas).T

