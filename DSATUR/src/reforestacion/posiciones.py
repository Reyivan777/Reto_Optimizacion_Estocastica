"""Movimientos discretos de candidatas; etiquetas y existentes inmutables."""
from dataclasses import dataclass
from typing import Protocol
from time import perf_counter
import numpy as np
from scipy.spatial import cKDTree
from .algoritmos import objetivo, validar_C
from .geometria import construir_grafo


class Terreno(Protocol):
    """Adaptador futuro: máscara booleana (n,) para puntos métricos (n,2).

    El proveedor decide pertenencia a contornos/agujeros. No genera geometrías.
    """
    def contiene(self, puntos: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True)
class Rectangulo:
    limites: tuple

    def contiene(self, puntos):
        limites = np.asarray(self.limites, dtype=float)
        if limites.shape != (2,) or not np.isfinite(limites).all() or (limites <= 0).any():
            raise ValueError('Límites inválidos.')
        return np.all((puntos >= 0) & (puntos <= limites), axis=1)


def _puntos(x):
    x = np.ascontiguousarray(x, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError('Coordenadas finitas de forma (n,2) requeridas.')
    return x


def preparar(g, pool, terreno, config):
    """Índice estático de sitios; solo cambia ocupación, nunca una matriz N²."""
    U, pool = _puntos(g['U']), _puntos(pool)
    nf = g['nf']
    if not isinstance(nf, (int, np.integer)) or not 0 <= nf <= len(U):
        raise ValueError('Número de existentes inválido.')
    if len(np.unique(pool, axis=0)) != len(pool):
        raise ValueError('Candidatas duplicadas.')
    validos = np.asarray(terreno.contiene(pool))
    dentro = np.asarray(terreno.contiene(U))
    if validos.shape != (len(pool),) or validos.dtype != bool or dentro.shape != (len(U),) or dentro.dtype != bool:
        raise ValueError('El terreno debe devolver máscaras booleanas (n,).')
    if not dentro.all() or len(np.unique(U, axis=0)) != len(U):
        raise ValueError('Solución inicial fuera del terreno o duplicada.')
    if cKDTree(U).query_pairs(config.separacion_min - 1e-8):
        raise ValueError('Solución inicial incumple separación mínima.')
    lookup = {tuple(z): nf+i for i, z in enumerate(pool)}
    try:
        sitios = np.array(list(range(nf)) + [lookup[tuple(z)] for z in U[nf:]], dtype=np.int64)
    except KeyError as error:
        raise ValueError('Cada posición nueva debe pertenecer al conjunto candidato.') from error
    xy = np.vstack([U[:nf], pool])
    ocupantes = np.full(len(xy), -1, dtype=np.int64)
    ocupantes[sitios] = np.arange(len(U))
    # Dos entradas por pareja. Orden explícito común a Python y C++.
    pares = cKDTree(xy).query_pairs(max(config.radio, config.separacion_min), output_type='ndarray')
    if len(pares):
        dist = np.linalg.norm(xy[pares[:, 0]] - xy[pares[:, 1]], axis=1)
        a = np.r_[pares[:, 0], pares[:, 1]]
        b = np.r_[pares[:, 1], pares[:, 0]]
        dist = np.r_[dist, dist]
        orden = np.lexsort((b, a)); a, b, dist = a[orden], b[orden], dist[orden]
    else:
        a = b = np.empty(0, dtype=np.int64); dist = np.empty(0)
    off = np.r_[0, np.cumsum(np.bincount(a, minlength=len(xy)))].astype(np.int64)
    return dict(xy=xy, sitios=sitios, ocupantes=ocupantes, validos=validos,
                off=off, adj=np.ascontiguousarray(b, dtype=np.int64),
                pesos=np.maximum(0., 1-dist/config.radio),
                bloquea=np.ascontiguousarray(dist < config.separacion_min-1e-9, dtype=np.int64), nf=nf)


def evaluar(a, destino, y, estado, intercambios=False):
    """Delta incidente sin mutación; None indica propuesta inválida.

    Con intercambios=True, un destino ocupado por otra nueva permuta posiciones.
    El conjunto de sitios ocupados no cambia: conserva pertenencia/separación.
    """
    off, adj, w = (estado[k] for k in ('off', 'adj', 'pesos'))
    ocupantes = estado['ocupantes']; origen = estado['sitios'][a]
    b = ocupantes[destino]
    if b >= 0:
        if not intercambios or b < estado['nf'] or a == b:
            return None
        # La arista a-b conserva peso y C simétrica; se excluye de ambas sumas.
        da = db = 0.
        C = estado['C']
        for e in range(off[origen], off[origen+1]):
            j = ocupantes[adj[e]]
            if j >= 0 and j != b:
                da += w[e]*(C[y[b], y[j]]-C[y[a], y[j]])
        for e in range(off[destino], off[destino+1]):
            j = ocupantes[adj[e]]
            if j >= 0 and j != a:
                db += w[e]*(C[y[a], y[j]]-C[y[b], y[j]])
        return da+db
    nuevo = 0.
    C = estado['C']
    for e in range(off[destino], off[destino+1]):
        j = ocupantes[adj[e]]
        if j < 0 or j == a:
            continue
        if estado['bloquea'][e]:
            return None
        nuevo += w[e]*C[y[a], y[j]]
    previo = 0.
    for e in range(off[origen], off[origen+1]):
        j = ocupantes[adj[e]]
        if j >= 0:
            previo += w[e]*C[y[a], y[j]]
    return nuevo-previo


def aplicar(a, destino, estado):
    """Actualiza únicamente ocupación y sitios de una propuesta ya validada."""
    origen = estado['sitios'][a]
    b = estado['ocupantes'][destino]
    estado['ocupantes'][origen] = b
    estado['ocupantes'][destino] = a
    estado['sitios'][a] = destino
    if b >= 0:
        estado['sitios'][b] = origen


def optimizar_posiciones(y, g, pool, C, terreno, config, rng=None, propuestas=None):
    """Pase acotado de sustituciones y, en vecindad mixta, intercambios.

    propuestas opcional: (índice global de planta nueva, índice de pool).
    Historia: (paso, planta, candidata, delta); el ocupante actual de la
    candidata identifica la segunda planta del intercambio al reproducirla.
    El RNG separado nunca consume los tres flujos históricos.
    """
    inicio = perf_counter(); validar_C(C)
    y = np.asarray(y)
    if y.shape != (len(g['U']),) or not np.issubdtype(y.dtype, np.integer) or ((y < 0) | (y >= len(C))).any():
        raise ValueError('Asignación completa entera requerida.')
    if config.motor not in ('python', 'cpp'):
        raise ValueError('Motor inválido.')
    y = np.ascontiguousarray(y, dtype=np.int64)
    estado = preparar(g, pool, terreno, config)
    estado['C'] = np.ascontiguousarray(C, dtype=float)
    if propuestas is None:
        m = config.intentos_posiciones if len(y) > g['nf'] and len(pool) else 0
        rng = rng if rng is not None else np.random.default_rng(config.semilla)
        propuestas = np.column_stack([rng.integers(g['nf'], len(y), m), rng.integers(0, len(pool), m)]) if m else np.empty((0, 2), dtype=np.int64)
    propuestas = np.asarray(propuestas)
    if propuestas.ndim != 2 or propuestas.shape[1] != 2 or not np.issubdtype(propuestas.dtype, np.integer):
        raise ValueError('Propuestas enteras (n,2) requeridas.')
    if ((propuestas[:, 0] < g['nf']) | (propuestas[:, 0] >= len(y))).any() or ((propuestas[:, 1] < 0) | (propuestas[:, 1] >= len(pool))).any():
        raise ValueError('Solo se permiten plantas nuevas e índices candidatos válidos.')
    propuestas = np.ascontiguousarray(propuestas, dtype=np.int64)
    t = perf_counter(); historia = []; factibles = 0
    mixta = config.vecindad_posiciones == 'mixta'
    tipos = dict(factibles_sustitucion=0, factibles_intercambio=0,
                 aceptados_sustitucion=0, aceptados_intercambio=0)
    if config.motor == 'cpp':
        from .motor_cpp import sustituir, intercambiar_posiciones
        if mixta:
            historia, factibles, tipos = intercambiar_posiciones(y, estado, propuestas)
        else:
            historia, factibles = sustituir(y, estado, propuestas)
            tipos.update(factibles_sustitucion=factibles, aceptados_sustitucion=len(historia))
    else:
        for k, (a, c) in enumerate(propuestas):
            if not estado['validos'][c]:
                continue
            destino = g['nf']+c
            delta = evaluar(a, destino, y, estado, intercambios=mixta)
            if delta is None:
                continue
            factibles += 1
            tipo = 'intercambio' if estado['ocupantes'][destino] >= 0 else 'sustitucion'
            tipos['factibles_'+tipo] += 1
            if delta < -1e-10:
                aplicar(a, destino, estado)
                tipos['aceptados_'+tipo] += 1
                historia.append((k+1, int(a), int(c), delta))
    nucleo = perf_counter()-t
    anterior = objetivo(y, g, C)
    nuevo = g
    if historia:
        U = estado['xy'][estado['sitios']]
        nuevo = construir_grafo(g['p'], U[:g['nf']], U[g['nf']:], config)
    final = objetivo(y, nuevo, C)
    incremental = anterior + sum(float(h[3]) for h in historia)
    if not np.isclose(incremental, final, rtol=0, atol=1e-7):
        raise AssertionError('Delta espacial inconsistente con el objetivo completo.')
    # Garantía de salida estricta incluso ante cancelación flotante extrema.
    revertido = bool(historia and final >= anterior)
    if revertido:
        nuevo = g; final = anterior; historia = []
        tipos.update(aceptados_sustitucion=0, aceptados_intercambio=0)
    if not np.array_equal(nuevo['U'][:g['nf']], g['U'][:g['nf']]):
        raise AssertionError('Se movieron plantas existentes.')
    stats = dict(propuestas=len(propuestas), evaluados=len(propuestas), factibles=int(factibles),
        aceptados=len(historia), rechazados=len(propuestas)-len(historia), revertido=revertido,
        J_inicial=anterior, J_final=final, reduccion_absoluta=anterior-final,
        reduccion_pct=100*(anterior-final)/anterior if anterior else 0.,
        vecindad=config.vecindad_posiciones, **tipos,
        seg_nucleo=nucleo, segundos=perf_counter()-inicio)
    return nuevo, np.asarray(historia, dtype=float).reshape(-1, 4), stats
