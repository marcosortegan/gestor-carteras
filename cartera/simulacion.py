import numpy as np
import pandas as pd
from cartera.valoracion import posiciones

def simular_gbm(s0, mu, sigma, T, pasos, n, semilla=None, metodo="exacto", Z=None):
    
    dt = T / pasos
    if Z is None:
        Z = np.random.default_rng(semilla).standard_normal((n, pasos))

    if metodo == "exacto":
        incremento = np.exp((mu-0.5*(sigma**2))*dt+np.sqrt(dt)*Z*sigma)
    elif metodo == "euler":
        incremento = 1+mu*dt+sigma*np.sqrt(dt)*Z         
    else:
        raise ValueError(f"Método «{metodo}» no válido, solo es posible euler o exacto")

    S = s0 * np.cumprod(incremento, axis=1)
    return np.hstack([np.full((Z.shape[0], 1), s0), S])

                        

#print(final.mean())                      
#print(np.percentile(final, [5, 50, 95]))  
#print((final < 100).mean())   


def conv_orden_fuerte(s0, mu, sigma, T,n=20000,semilla=0,niveles=(8, 16, 32, 64, 128, 256, 512)):
    
    rng = np.random.default_rng(semilla)
    fino = niveles[-1]
    Z_fino = rng.standard_normal((n,fino))
    S_exacto = s0*np.exp((mu - 0.5 * sigma**2)*T+sigma*np.sqrt(T/fino) * Z_fino.sum(axis=1))

    errores = []
    for pasos in niveles:
        k=fino//pasos
        Z = Z_fino.reshape(n,pasos,k).sum(axis=2)/np.sqrt(k)
        S_euler = simular_gbm(s0, mu, sigma, T, pasos, n, metodo="euler", Z=Z)[:, -1]
        errores.append(np.abs(S_exacto-S_euler).mean())

    dts = T / np.array(niveles)
    pendiente = np.polyfit(np.log(dts), np.log(errores), 1)[0]
    return pd.Series(errores, index=dts), pendiente


def simular_cartera(valores_iniciales,rlog,dias=252, n=10000, semilla=None, antiteticas=False):
    m = rlog.mean().values
    L = np.linalg.cholesky(rlog.cov().values)
    rng = np.random.default_rng(semilla)
    k = len(m)

    if antiteticas:
        Z = rng.standard_normal((n // 2, dias, k))
        Z = np.concatenate([Z, -Z])
    else:
        Z = rng.standard_normal((n, dias, k))

    X = m+ Z@L.T
    crecimiento = np.exp(np.cumsum(X, axis=1))          # (n, dias, k)
    V = (crecimiento * np.asarray(valores_iniciales)).sum(axis=2)
    V0 = np.full((V.shape[0], 1), float(np.sum(valores_iniciales)))
    return np.hstack([V0, V])


def valores_actuales_eur(conn, cartera_id):
    pos = posiciones(conn, cartera_id)
    valores = {}
    for ticker, fila in pos.iterrows():
        precio = conn.execute("SELECT cierre FROM precios_diarios WHERE ticker = ? ORDER BY fecha DESC LIMIT 1", (ticker,)).fetchone()[0]
        divisa = conn.execute("SELECT divisa FROM activos WHERE ticker = ?", (ticker,)).fetchone()[0]
        tasa = 1
        if divisa != "EUR":
            tasa = conn.execute("SELECT tasa FROM tipos_cambio WHERE divisa = ? ORDER BY fecha DESC LIMIT 1", (divisa,)).fetchone()[0]
        valores[ticker] = fila["acciones"] * precio / tasa
    return pd.Series(valores)



def trayectorias_cartera(rlog, valores, dias=252, n=10_000, semilla=None):
    rlog = rlog[valores.index]
    rng = np.random.default_rng(semilla)
    L = np.linalg.cholesky(rlog.cov().values)
    Z = rng.standard_normal((n, dias, len(valores)))
    sim = rlog.mean().values + Z @ L.T
    V = (valores.values * np.exp(np.cumsum(sim, axis=1))).sum(axis=2)
    return np.hstack([np.full((n, 1), valores.sum()), V])







