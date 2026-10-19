"""
Algoritmo genético para la asignación de especies (reforestación CONAFOR).

Coherente con modelo_reforestacion.ipynb (modelo matemático):
  * Mismos datos reales: data/especies.csv, data/inventario.csv (30 polígonos).
  * Mismas cuotas finales R_ps (restos mayores) y compra q_ps = R_ps - n_ps.
  * Misma geometría simulada: rectángulo de área 10^4*A_p, existentes por rechazo
    con separación mínima 3.4 m, nuevas posiciones por selección geométrica.
  * Mismo grafo espacial (radio 6 m, w = max(0, 1 - d/r)), misma matriz C (3/2/1)
    y misma función objetivo J = J_FF + J_FV + J_VV.
  * Las posiciones se fijan ANTES de asignar especies; el AG solo decide especies.

Las secciones marcadas "COPIADO DEL NOTEBOOK" no se modificaron, para que el AG
se evalúe sobre exactamente los mismos escenarios que DSATUR + búsqueda local.
"""
from pathlib import Path
from dataclasses import dataclass, replace, asdict
from time import perf_counter
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

# =====================================================================
# 1) CONFIGURACIÓN
# =====================================================================
@dataclass(frozen=True)
class Config:                       # COPIADO DEL NOTEBOOK (sección 2)
    densidad: float = 658.0
    aspecto: float = 1.0
    paso_malla: float = 3.4
    separacion_min: float = 3.4
    radio: float = 6.0
    semilla: int = 20261014
    escenarios: int = 12
    intentos_local: int = 6000
    max_propuestas_posicion: int = 200000


@dataclass(frozen=True)
class ConfigAG:                     # parámetros propios del algoritmo genético
    poblacion: int = 100
    generaciones: int = 2000
    sin_mejora: int = 300           # paro anticipado
    p_cruce: float = 0.85
    p_mut_gen: float = 0.001        # probabilidad de intercambio por gen
    k_torneo: int = 3
    n_elite: int = 2
    cruce: str = "region"           # "region" (corte espacial) o "uniforme"
    semilla_dsatur: bool = False    # True = incluye la solución DSATUR en la población inicial


class EscenarioNoConstruido(ValueError):   # COPIADO DEL NOTEBOOK
    pass


# =====================================================================
# 2) DATOS REALES  (COPIADO DEL NOTEBOOK, secciones 3-4)
# =====================================================================
def cargar_datos(ruta_especies, ruta_inventario):
    """Lee los CSV desde la ruta directa de cada archivo."""
    ruta_especies, ruta_inventario = Path(ruta_especies), Path(ruta_inventario)
    for r in (ruta_especies, ruta_inventario):
        if not r.is_file():
            raise FileNotFoundError(f"No existe el archivo: {r}")
    especies = pd.read_csv(ruta_especies)
    inventario = pd.read_csv(ruta_inventario)
    S = especies.especie.tolist()
    assert len(S) == 10 and especies.especie.is_unique
    assert especies.objetivo_por_ha.sum() == 658
    assert len(inventario) == 300 and set(inventario.poligono) == set(range(1, 31))
    areas = inventario.groupby("poligono").area_ha.first()
    return especies, inventario, areas, S


def datos_poligono(p, especies, inventario, areas, S, config):
    if p not in areas.index:
        raise ValueError(f"Polígono {p} no disponible.")
    if config.densidad <= 0:
        raise ValueError("La densidad debe ser positiva.")
    n = inventario[inventario.poligono.eq(p)].set_index("especie").loc[S, "existentes"].to_numpy(int)
    total = int(np.floor(areas.loc[p] * config.densidad + 0.5))
    ideal = total * especies.objetivo_por_ha.to_numpy() / especies.objetivo_por_ha.sum()
    R = np.floor(ideal).astype(int)
    orden = np.argsort(-(ideal - R), kind="stable")
    R[orden[:total - int(R.sum())]] += 1
    if np.any(R < n):
        raise ValueError("Inventario superior a una cuota: no se eliminan plantas ni se trunca el faltante.")
    return float(areas.loc[p]), n, R, R - n


# =====================================================================
# 3) GEOMETRÍA SIMULADA  (COPIADO DEL NOTEBOOK, secciones 5-8)
# =====================================================================
def dimensiones(area_ha, config):
    if area_ha <= 0 or config.aspecto <= 0:
        raise ValueError("Área y aspecto deben ser positivos.")
    ancho = np.sqrt(10000 * area_ha * config.aspecto)
    return np.array([ancho, 10000 * area_ha / ancho])


def simular_existentes(n, limites, config, rng):
    d = config.separacion_min
    if d <= 0:
        raise ValueError("La separación mínima debe ser positiva.")
    puntos, cubetas = [], {}
    for _ in range(config.max_propuestas_posicion):
        if len(puntos) == int(n.sum()):
            break
        z = rng.uniform([0, 0], limites)
        celda = tuple(np.floor(z / d).astype(int))
        vecinos = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                   for j in cubetas.get((celda[0] + dx, celda[1] + dy), [])]
        if any(np.linalg.norm(z - puntos[j]) < d for j in vecinos):
            continue
        cubetas.setdefault(celda, []).append(len(puntos))
        puntos.append(z)
    if len(puntos) != int(n.sum()):
        raise EscenarioNoConstruido(f"Solo se generaron {len(puntos)}/{n.sum()} existentes; límite de intentos.")
    etiquetas = rng.permutation(np.repeat(np.arange(len(n)), n))
    return np.array(puntos).reshape(-1, 2), etiquetas


def flujos(p, escenario, config):
    return [np.random.default_rng(s) for s in
            np.random.SeedSequence([config.semilla, p, escenario]).spawn(3)]


def candidatas(F, limites, cantidad, config):
    paso, minimo = config.paso_malla, config.separacion_min
    if paso < minimo or minimo <= 0:
        raise ValueError("El paso de la malla debe ser >= separación mínima > 0.")
    filas = []
    for j, y in enumerate(np.arange(paso / 2, limites[1], paso * np.sqrt(3) / 2)):
        xs = np.arange(paso / 2 + (j % 2) * paso / 2, limites[0], paso)
        filas.extend((x, y) for x in xs)
    malla = np.array(filas).reshape(-1, 2)
    dist = cKDTree(F).query(malla)[0] if len(F) else np.full(len(malla), np.inf)
    pool = malla[dist >= minimo - 1e-9]
    if len(pool) < cantidad:
        raise EscenarioNoConstruido(f"Capacidad de malla {len(pool)} < demanda {cantidad}.")
    cercano = cKDTree(F).query(pool)[0] if len(F) else np.full(len(pool), np.inf)
    elegidas = []
    for _ in range(cantidad):
        i = int(np.argmax(cercano))
        elegidas.append(i)
        cercano = np.minimum(cercano, np.linalg.norm(pool - pool[i], axis=1))
        cercano[elegidas] = -np.inf
    return pool, pool[np.array(elegidas, dtype=int)]


def construir_grafo(p, F, V, config):
    if config.radio <= 0:
        raise ValueError("Radio debe ser positivo.")
    U = np.vstack([F, V])
    pares = cKDTree(U).query_pairs(config.radio, output_type="ndarray")
    dist = np.linalg.norm(U[pares[:, 0]] - U[pares[:, 1]], axis=1)
    pesos = np.maximum(0, 1 - dist / config.radio)
    ady = [[] for _ in U]
    for (i, j), w in zip(pares, pesos):
        ady[i].append((int(j), float(w)))
        ady[j].append((int(i), float(w)))
    # (el notebook también guarda un grafo NetworkX 'G' solo para dibujo; el AG no lo usa)
    return {"U": U, "pares": pares, "pesos": pesos, "ady": ady, "nf": len(F), "p": p}


# =====================================================================
# 4) COMPETENCIA Y OBJETIVO  (COPIADO DEL NOTEBOOK, secciones 9-10)
# =====================================================================
def matriz_competencia(especies, misma=3., genero=2., distinta=1.):
    generos = especies.genero.to_numpy()
    C = np.where(generos[:, None] == generos[None, :], genero, distinta).astype(float)
    np.fill_diagonal(C, misma)
    return C


def validar_C(C):
    K = len(C)
    if C.shape != (K, K) or not np.isfinite(C).all() or (C < 0).any() or not np.allclose(C, C.T):
        raise ValueError("C debe ser finita, no negativa, simétrica y de tamaño KxK.")


def objetivo(etiquetas, g, C, desglose=False):
    if len(etiquetas) != len(g["U"]) or np.any((etiquetas < 0) | (etiquetas >= len(C))):
        raise ValueError("La función objetivo requiere una asignación completa.")
    i, j = g["pares"].T
    valores = g["pesos"] * C[etiquetas[i], etiquetas[j]]
    if not desglose:
        return float(valores.sum())
    ff = (i < g["nf"]) & (j < g["nf"])
    vv = (i >= g["nf"]) & (j >= g["nf"])
    return {"FF": float(valores[ff].sum()), "FV": float(valores[~(ff | vv)].sum()),
            "VV": float(valores[vv].sum()), "total": float(valores.sum())}


def base_aleatoria(fijas, q, rng):
    return np.r_[fijas, rng.permutation(np.repeat(np.arange(len(q)), q))]


# =====================================================================
# 5) MÉTODOS DE REFERENCIA DEL MATEMÁTICO  (COPIADO DEL NOTEBOOK, secciones 11-12)
# =====================================================================
def dsatur(fijas, q, g, C):
    validar_C(C)
    nf, N = len(fijas), len(g["U"])
    if len(q) != len(C) or np.any(q < 0) or np.any(q % 1) or int(q.sum()) != N - nf:
        raise ValueError("Cuotas inválidas o incompatibles con el número de posiciones.")
    y = np.full(N, -1, dtype=int)
    y[:nf] = fijas
    restante = q.astype(int).copy()
    vistos = np.zeros((N, len(C)), dtype=bool)
    coste = np.zeros((N, len(C)))
    grado = np.array([sum(w for _, w in ad) for ad in g["ady"]])

    def actualizar(i, s):
        for j, w in g["ady"][i]:
            if y[j] < 0:
                vistos[j, s] = True
                coste[j] += w * C[:, s]
    for i, s in enumerate(fijas):
        actualizar(i, int(s))
    for _ in range(N - nf):
        libres = np.flatnonzero(y < 0)
        saturacion = vistos[libres].sum(axis=1)
        i = int(libres[np.lexsort((libres, -grado[libres], -saturacion))[0]])
        factibles = np.flatnonzero(restante > 0)
        if not len(factibles):
            raise ValueError("No queda especie factible.")
        s = int(min(factibles, key=lambda s: (coste[i, s], -restante[s], s)))
        y[i] = s
        restante[s] -= 1
        actualizar(i, s)
    assert not restante.any()
    return y


def delta_intercambio(a, b, y, g, C):
    sa, sb = int(y[a]), int(y[b])
    return sum(w * (C[sb, y[j]] - C[sa, y[j]]) for j, w in g["ady"][a] if j != b) + sum(
        w * (C[sa, y[j]] - C[sb, y[j]]) for j, w in g["ady"][b] if j != a)


def busqueda_local(inicial, g, C, rng, intentos):
    y = inicial.copy()
    valor = objetivo(y, g, C)
    historia = [(0, valor)]
    movibles = np.arange(g["nf"], len(y))
    if len(movibles) < 2:
        return y, np.array(historia)
    for intento in range(1, intentos + 1):
        a, b = rng.choice(movibles, 2, replace=False)
        if y[a] == y[b]:
            continue
        delta = delta_intercambio(a, b, y, g, C)
        if delta < -1e-10:
            y[a], y[b] = y[b], y[a]
            valor += delta
            historia.append((intento, valor))
    assert np.isclose(valor, objetivo(y, g, C), atol=1e-7)
    return y, np.array(historia)


def validar_solucion(y, g, fijas, n, R, limites, config):
    K = len(n)
    U = g["U"]
    assert y.shape == (len(U),) and np.all((y >= 0) & (y < K))
    assert np.array_equal(y[:len(fijas)], fijas)
    assert np.array_equal(np.bincount(y[:len(fijas)], minlength=K), n)
    assert np.array_equal(np.bincount(y, minlength=K), R)
    assert len(U) == int(R.sum())
    assert np.all(U >= 0) and np.all(U <= limites)
    assert len(np.unique(U, axis=0)) == len(U)
    assert len(cKDTree(U).query_pairs(config.separacion_min - 1e-8)) == 0
    return True


# =====================================================================
# 6) ALGORITMO GENÉTICO (aportación nueva)
# =====================================================================
class AlgoritmoGenetico:
    """
    Cromosoma: vector de enteros (0..K-1) de longitud |V| = sum(q): especie de cada
    posición NUEVA (las posiciones V ya están fijadas; las existentes F no se tocan).
    Cuotas exactas: cada individuo contiene exactamente q_s genes de la especie s.
    Fitness (se minimiza): J(y) = J_FF + J_FV + J_VV con y = (fijas, cromosoma).
    J_FF es constante, así que ordena igual que la parte modificable J_FV + J_VV.
    """

    def __init__(self, fijas, q, g, C, rng, cfg_ag=ConfigAG()):
        self.fijas = np.asarray(fijas, dtype=int)
        self.q = np.asarray(q, dtype=int)
        self.g, self.C, self.rng, self.cfg = g, C, rng, cfg_ag
        self.nf = len(self.fijas)
        self.L = int(self.q.sum())
        self.K = len(self.q)
        self.coords_V = g["U"][self.nf:]
        self.pi, self.pj = g["pares"].T
        self.w = g["pesos"]

    # ---- fitness ----
    def fitness(self, cromosoma):
        y = np.r_[self.fijas, cromosoma]
        return float((self.w * self.C[y[self.pi], y[self.pj]]).sum())

    # ---- población inicial: permutaciones aleatorias del multiconjunto de cuotas ----
    def nuevo_individuo(self):
        return self.rng.permutation(np.repeat(np.arange(self.K), self.q))

    # ---- selección por torneo ----
    def torneo(self, pob, fit):
        idx = self.rng.integers(0, len(pob), self.cfg.k_torneo)
        return pob[idx[np.argmin(fit[idx])]]

    # ---- cruce ----
    def cruce(self, p1, p2):
        if self.cfg.cruce == "uniforme":
            mascara = self.rng.random(self.L) < 0.5
        else:   # "region": un padre aporta un semiplano del polígono y el otro el resto
            ang = self.rng.uniform(0, np.pi)
            proy = self.coords_V @ np.array([np.cos(ang), np.sin(ang)])
            corte = self.rng.uniform(proy.min(), proy.max())
            mascara = proy < corte
        return np.where(mascara, p1, p2), np.where(mascara, p2, p1)

    # ---- reparación: restituye las cuotas exactas q ----
    def reparar(self, hijo):
        n = np.bincount(hijo, minlength=self.K)
        exceso = n - self.q
        if not exceso.any():
            return hijo
        for s in np.flatnonzero(exceso > 0):
            pos = self.rng.choice(np.flatnonzero(hijo == s), exceso[s], replace=False)
            hijo[pos] = -1
        vacios = np.flatnonzero(hijo == -1)
        faltan = np.repeat(np.arange(self.K), np.maximum(0, -exceso))
        hijo[vacios] = self.rng.permutation(faltan)
        return hijo

    # ---- mutación: intercambio de pares (conserva cuotas) ----
    def mutar(self, ind):
        for _ in range(self.rng.binomial(self.L, self.cfg.p_mut_gen)):
            a, b = self.rng.integers(0, self.L, 2)
            ind[a], ind[b] = ind[b], ind[a]
        return ind

    # ---- ciclo evolutivo ----
    def ejecutar(self, semillas=()):
        c = self.cfg
        pob = [self.nuevo_individuo() for _ in range(c.poblacion)]
        for k, s in enumerate(semillas):
            pob[k] = np.asarray(s, dtype=int).copy()
        pob = np.array(pob)
        fit = np.array([self.fitness(x) for x in pob])
        mejor_hist, media_hist = [fit.min()], [fit.mean()]
        sin_mejora = 0
        self.evaluaciones = len(pob)
        for gen in range(1, c.generaciones + 1):
            orden = np.argsort(fit)
            nueva = [pob[i].copy() for i in orden[:c.n_elite]]
            while len(nueva) < c.poblacion:
                p1, p2 = self.torneo(pob, fit), self.torneo(pob, fit)
                if self.rng.random() < c.p_cruce:
                    h1, h2 = self.cruce(p1, p2)
                    h1, h2 = self.reparar(h1.copy()), self.reparar(h2.copy())
                else:
                    h1, h2 = p1.copy(), p2.copy()
                nueva.append(self.mutar(h1))
                nueva.append(self.mutar(h2))
            pob = np.array(nueva[:c.poblacion])
            fit = np.array([self.fitness(x) for x in pob])
            self.evaluaciones += len(pob)
            mejor_hist.append(fit.min())
            media_hist.append(fit.mean())
            sin_mejora = 0 if mejor_hist[-1] < mejor_hist[-2] - 1e-9 else sin_mejora + 1
            if sin_mejora >= c.sin_mejora:
                break
        self.mejor = pob[np.argmin(fit)].copy()
        self.historia = np.array([mejor_hist, media_hist]).T
        return np.r_[self.fijas, self.mejor]   # asignación completa (fijas + nuevas)