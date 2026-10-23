"""Fase 8 opcional: DSATUR tolerante, multarranque y composición conjunta acotada."""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from time import perf_counter
import numpy as np
from .algoritmos import validar_C, objetivo
from .experimento import ejecutar_escenario
from .motores import obtener_motor
from .optimizacion_economica import (DatosConCuotas, validar_cuotas,
    desviacion_exacta, unidades_exactas)
from .validacion import validar_solucion


@dataclass(frozen=True)
class Mejoras:
    reinicios: int = 3
    intentos_local: int = 6000
    intentos_conjuntos: int = 0
    margen_desviacion: str = '0'
    tolerancia: float = 1e-10

    def __post_init__(self):
        for k in ('reinicios', 'intentos_local', 'intentos_conjuntos'):
            v = getattr(self, k)
            if type(v) is not int or v < 0:
                raise ValueError(f'{k} debe ser entero no negativo.')
        if not isinstance(self.margen_desviacion, str):
            raise ValueError('Margen debe ser texto decimal exacto.')
        d = Decimal(self.margen_desviacion)
        if not d.is_finite() or d < 0:
            raise ValueError('Margen debe ser finito no negativo.')
        if isinstance(self.tolerancia, bool) or not np.isfinite(self.tolerancia) or self.tolerancia <= 0:
            raise ValueError('Tolerancia debe ser finita positiva.')


def dsatur_estable(fijas, q, g, C, rng, tolerancia=1e-10):
    """Orden DSATUR histórico; sorteo solo entre costos casi mínimos.

    La tolerancia absoluta se expresa en unidades de costo incremental de J.
    Cuotas restantes máximas desempatan antes del sorteo. No cuantiza C.
    """
    validar_C(C)
    if not np.isfinite(tolerancia) or tolerancia <= 0:
        raise ValueError('Tolerancia inválida.')
    nf, N = len(fijas), len(g['U'])
    q = np.asarray(q)
    if q.shape != (len(C),) or not np.isfinite(q).all() or (q < 0).any() or (q % 1).any() or q.sum() != N-nf:
        raise ValueError('Cuotas incompatibles.')
    y = np.full(N, -1, dtype=int); y[:nf] = fijas
    restante = q.astype(int).copy()
    vistos = np.zeros((N, len(C)), dtype=bool)
    coste = np.zeros((N, len(C)))
    grado = np.array([sum(w for _, w in ad) for ad in g['ady']])

    def actualizar(i, s):
        for j, w in g['ady'][i]:
            if y[j] < 0:
                vistos[j, s] = True
                coste[j] += w*C[:, s]

    for i, s in enumerate(fijas):
        actualizar(i, int(s))
    for _ in range(N-nf):
        libres = np.flatnonzero(y < 0)
        i = int(libres[np.lexsort((libres, -grado[libres], -vistos[libres].sum(axis=1)))[0]])
        opciones = np.flatnonzero(restante > 0)
        minimo = coste[i, opciones].min()
        opciones = opciones[coste[i, opciones] <= minimo+tolerancia]
        opciones = opciones[restante[opciones] == restante[opciones].max()]
        s = int(rng.choice(opciones)) if len(opciones) > 1 else int(opciones[0])
        y[i] = s; restante[s] -= 1
        actualizar(i, s)
    return y


def delta_cambio(a, s, y, g, C):
    return sum(w*(C[s, y[j]]-C[y[a], y[j]]) for j, w in g['ady'][a])


def conjunta(inicial, g, C, R, n, costos, B, limite_D, rng, intentos):
    """Cambios unitarios de especie; cada aceptación conserva factibilidad exacta."""
    y = inicial.copy(); x = np.bincount(y, minlength=len(C))
    validar_cuotas(R, n, x, costos, B)
    if desviacion_exacta(x, R) > limite_D:
        raise ValueError('Incumbente fuera del límite de desviación.')
    c, presupuesto, _ = unidades_exactas(costos, B)
    costo = sum(int(a)*int(b) for a, b in zip(c, x-n))
    lo = np.maximum(n, (90*R+99)//100); hi = 110*R//100
    aceptados = factibles = 0
    movibles = np.arange(g['nf'], len(y))
    for _ in range(intentos if len(movibles) else 0):
        a = int(rng.choice(movibles)); s = int(rng.integers(len(C))); old = y[a]
        if old == s or x[old] <= lo[old] or x[s] >= hi[s]:
            continue
        nuevo_costo = costo+int(c[s])-int(c[old])
        if nuevo_costo > presupuesto:
            continue
        z = x.copy(); z[old] -= 1; z[s] += 1
        if desviacion_exacta(z, R) > limite_D:
            continue
        factibles += 1
        delta = delta_cambio(a, s, y, g, C)
        if delta < -1e-10:
            y[a] = s; x = z; costo = nuevo_costo; aceptados += 1
    validar_cuotas(R, n, x, costos, B)
    assert objetivo(y, g, C) <= objetivo(inicial, g, C)+1e-8
    return y, dict(propuestas=intentos if len(movibles) else 0,
                   factibles=factibles, aceptados=aceptados)


def mejorar(p, e, datos, config, C, plan, opciones=Mejoras()):
    """Incluye siempre la solución histórica; reinicios en el mismo grafo final.

    La etapa conjunta prioriza J dentro de D<=D_referencia+margen y B. No
    certifica ni preserva el desempate económico por costo mínimo.
    """
    inicio = perf_counter()
    vista = DatosConCuotas(datos, {p: plan})
    fila, d = ejecutar_escenario(p, e, vista, config, C)
    area, n, R, _ = datos.poligono(p, config)
    B = float(Decimal(str(area))*Decimal(str(config.presupuesto_por_ha)))
    costos = datos.especies.costo_unitario.to_numpy()
    g = d['g']; mejor = d['final'].copy(); jref = objetivo(mejor, g, C)
    Dref = desviacion_exacta(d['R'], R)
    limite = Dref+Fraction(Decimal(opciones.margen_desviacion))
    motor = obtener_motor(config.motor)
    traza = [dict(etapa='referencia', reinicio=-1, J_candidato=jref, J_incumbente=jref,
                  segundos=fila['seg_total'], aceptados=0)]
    tmejora = perf_counter()
    for k in range(opciones.reinicios):
        t = perf_counter()
        streams = np.random.SeedSequence([config.semilla, 8, p, e, k]).spawn(2)
        y = dsatur_estable(d['fijas'], d['q'], g, C,
                          np.random.default_rng(streams[0]), opciones.tolerancia)
        y, _, st = motor.busqueda_local(y, g, C, np.random.default_rng(streams[1]), opciones.intentos_local)
        j = objetivo(y, g, C)
        if j < objetivo(mejor, g, C)-1e-10:
            mejor = y
        traza.append(dict(etapa='reinicio', reinicio=k, J_candidato=j,
            J_incumbente=objetivo(mejor, g, C), segundos=perf_counter()-t, aceptados=st['aceptados']))
    jreinicios = objetivo(mejor, g, C)
    t = perf_counter()
    mejor, st = conjunta(mejor, g, C, R, n, costos, B, limite,
        np.random.default_rng(np.random.SeedSequence([config.semilla, 8, p, e, 2147483647])),
        opciones.intentos_conjuntos)
    j = objetivo(mejor, g, C)
    traza.append(dict(etapa='conjunta', reinicio=-1, J_candidato=j,
        J_incumbente=j, segundos=perf_counter()-t, **st))
    x = np.bincount(mejor, minlength=len(C))
    validar_solucion(mejor, g, d['fijas'], n, x, d['limites'], config)
    validar_cuotas(R, n, x, costos, B)
    assert desviacion_exacta(x, R) <= limite and j <= jref+1e-8
    c, _, escala = unidades_exactas(costos, B)
    costo = sum(int(a)*int(b) for a, b in zip(c, x-n))/escala
    fila.update(J_referencia=jref, J_reinicios=jreinicios, J_final=j, diferencia_J=j-jref,
        costo_referencia_um=fila['costo_um'], costo_um=costo,
        saldo_um=B-costo, cumple_presupuesto=True,
        presupuesto_utilizado_pct=100*costo/B if B else None,
        mejora_pct=100*(fila['J_base']-j)/fila['J_base'] if fila['J_base'] else None,
        mejora_modificable_pct=100*(fila['J_base']-j)/(fila['J_base']-fila['J_fijo']) if fila['J_base']>fila['J_fijo'] else None,
        desviacion_referencia=float(Dref), desviacion_final=float(desviacion_exacta(x, R)),
        limite_desviacion=str(limite), seg_mejoras=perf_counter()-tmejora,
        seg_total=perf_counter()-inicio, cambios_conjuntos=st['aceptados'])
    d.update(referencia=d['final'].copy(), final=mejor, R_final=x, traza=traza)
    return fila, d
