import numpy as np
import pandas as pd
from scipy import stats

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



def var_historico(r,nivel=0.99):
    return -r.quantile(1-nivel)

def cvar_historico(r,nivel=0.99):
    var = var_historico(r,nivel)
    return -r[r <= -var].mean()

def var_normal(r,nivel=0.99,mu=None,sigma=None):
    mu = r.mean() if mu is None else mu
    sigma = r.std() if sigma is None else sigma
    return -(mu+sigma*stats.norm.ppf(1-nivel))

def cvar_normal(r,nivel=0.99,mu=None,sigma=None):
    mu = r.mean() if mu is None else mu
    sigma = r.std() if sigma is None else sigma
    z = stats.norm.ppf(1-nivel)
    return -(mu - sigma * stats.norm.pdf(z) / (1 - nivel))


def ajustar_tStudent(r):
    return stats.t.fit(r.dropna())

def var_tStudent(r,nivel=0.99):
    df, loc, escala= ajustar_tStudent(r)
    return -(loc + escala * stats.t.ppf(1 - nivel, df))

def cvar_tStudent(r,nivel=0.99):
    df, loc, escala= ajustar_tStudent(r)
    x = stats.t.ppf(1-nivel,df)
    return -(loc-escala*(df+x**2)/(df - 1)*stats.t.pdf(x, df)/(1 - nivel))


def tabla_var_cvar(rentabilidades, nivel=0.99):
    filas = {}
    for nombre, r in rentabilidades.items():
        r = r.dropna()
        filas[nombre] = {
            "var_historico": var_historico(r, nivel),
            "var_normal": var_normal(r, nivel),
            "var_t": var_tStudent(r, nivel),
            "cvar_historico": cvar_historico(r, nivel),
            "cvar_normal": cvar_normal(r, nivel),
            "cvar_t": cvar_tStudent(r, nivel),
            "grados_libertad": ajustar_tStudent(r)[0],
        }
    return pd.DataFrame(filas).T



def backtest_var(r,nivel=0.99,ventana=250,metodo="historico"):

    if metodo=="historico":
        prevision = -r.rolling(ventana).quantile(1-nivel).shift(1)
    elif metodo == "ewma":
        sigma =volatilidad_ewma(r)/np.sqrt(DIAS)
        prevision = -sigma*stats.norm.ppf(1-nivel)
    else:
        raise ValueError(f"Método {metodo} no válido, solo histórico o ewma")

    d = pd.DataFrame({"r": r, "var": prevision}).dropna()
    d["excepcion"] = -d["r"] > d["var"]
    return d

def kupiec(excepciones,n,nivel=0.99):
    p = 1-nivel
    x = excepciones

    def log_ver(q):
        a = (n-x)*np.log(1 - q) if x < n else 0.0
        b = x*np.log(q) if x > 0 else 0.0
        return a+b
    lr = -2 * (log_ver(p) - log_ver(x / n))
    return {"excepciones": x, "esperadas": n * p, "lr": lr, "p_valor": stats.chi2.sf(lr, 1)}

def semaforo_basilea(r,ventana=250,metodo="historico"):
    
    d = backtest_var(r,0.99,ventana,metodo)
    d["exc_250"] = d["excepcion"].rolling(250).sum()
    d["semaforo"] = pd.cut(d["exc_250"], bins=[-1, 4, 9, 250],labels=["verde", "amarillo", "rojo"])
    return {"hoy": d["semaforo"].iloc[-1],"excepciones_250": d["exc_250"].iloc[-1],
        "dias_por_color": d["semaforo"].value_counts(),"detalle": d}
    
def tabla_backtest(rentabilidades, metodos=("historico", "ewma"), ventana=250):
    filas = {}
    for nombre, r in rentabilidades.items():
        r = r.dropna()
        for metodo in metodos:
            s = semaforo_basilea(r, ventana, metodo)
            d = s["detalle"]
            k = kupiec(int(d["excepcion"].sum()), len(d))
            filas[(nombre, metodo)] = {
                "dias": len(d),
                "excepciones": k["excepciones"],
                "esperadas": k["esperadas"],
                "p_kupiec": k["p_valor"],
                "exc_ultimos_250": s["excepciones_250"],
                "color": s["hoy"],
            }
    return pd.DataFrame(filas).T