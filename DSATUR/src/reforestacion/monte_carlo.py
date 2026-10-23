"""Monte Carlo espacial: muestras fijas, sin parada opcional por precisión.

No modifica los generadores ni la economía. Los IC describen la media
condicional a construcciones válidas, no supervivencia ni error del modelo.
"""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import math
import multiprocessing
import numpy as np
from scipy.stats import t


def estadisticas(valores, solicitados, confianza=0.95):
    if not 0 < confianza < 1:
        raise ValueError('confianza debe estar entre cero y uno.')
    x = np.asarray(valores, dtype=float)
    if x.ndim != 1 or solicitados < len(x):
        raise ValueError('Vector y denominador incompatibles.')
    x = x[np.isfinite(x)]
    n = len(x)
    media = float(x.mean()) if n else None
    sd = float(x.std(ddof=1)) if n > 1 else None
    se = sd / math.sqrt(n) if n > 1 else None
    h = float(t.ppf((1 + confianza) / 2, n - 1) * se) if n > 1 else None
    return dict(solicitados=solicitados, validos=n, excluidos=solicitados-n,
                media=media, desviacion=sd, error_estandar=se, confianza=confianza,
                semiancho_ic=h, ic_inferior=media-h if h is not None else None,
                ic_superior=media+h if h is not None else None,
                semiancho_relativo=h/abs(media) if h is not None and media else None,
                **{f'p{q:02d}':float(np.percentile(x,q,method='linear')) if n else None
                   for q in (5,25,50,75,95)})


def plan_muestra(piloto, relativo=0.0025, absoluto=1., minimo=100,
                 maximo=1000, confianza=0.95):
    """Estimación conservadora con t del piloto; confirmación independiente.

    El tamaño se fija antes de observar confirmación. Si excede el máximo se
    informa el truncamiento; no se declara precisión por el tamaño solamente.
    """
    if (not np.isfinite([relativo,absoluto]).all() or relativo <= 0 or absoluto <= 0
            or not isinstance(minimo,int) or not isinstance(maximo,int)
            or minimo < 2 or maximo < minimo):
        raise ValueError('Precisión positiva y límites enteros 2 <= mínimo <= máximo requeridos.')
    s = estadisticas(piloto, len(piloto), confianza)
    if s['validos'] < 2:
        raise ValueError('Piloto requiere al menos dos realizaciones válidas.')
    tolerancia = max(absoluto, relativo * abs(s['media']))
    n_precision = math.ceil((t.ppf((1+confianza)/2,s['validos']-1)
                            * s['desviacion']/tolerancia)**2)
    requerido = max(minimo,n_precision)
    return dict(n_estimado=requerido, n_confirmacion=min(requerido,maximo),
                n_precision_estimado=n_precision, minimo_preestablecido=minimo,
                limitado=requerido>maximo, tolerancia_absoluta=tolerancia,
                relativo=relativo, absoluto=absoluto, piloto=s)


def _huella(*arrays):
    h = hashlib.sha256()
    for a in arrays:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def realizar(tarea):
    """Solo devuelve escalares y hashes; libera el grafo dentro del trabajador."""
    from .experimento import ejecutar_escenario, LimiteRecursos
    from .geometria import EscenarioNoConstruido
    from .optimizacion_economica import validar_cuotas, DatosConCuotas
    p,e,datos,cfg,C,plan = tarea
    # La vista económica delega atributos y no es serializable con spawn.
    # Transferir Datos y el plan; reconstruir la vista dentro del proceso.
    if plan is not None:
        datos = DatosConCuotas(datos,{p:plan})
    try:
        f,r = ejecutar_escenario(p,e,datos,cfg,C)
        if plan is not None:
            validar_cuotas(plan['R_original'],r['n'],np.bincount(r['final'],minlength=len(C)),
                           datos.especies.costo_unitario,plan['presupuesto_um'])
            if not f['cumple_presupuesto']:
                raise AssertionError('Presupuesto incumplido.')
            f['estado_factibilidad'] = 'factible_economica_y_espacialmente'
        f.update(entradas_sha256=_huella(r['g_inicial']['U'],r['fijas'],r['q']),
                 solucion_sha256=_huella(r['g']['U'],r['final']))
        return f
    except EscenarioNoConstruido as error:
        return dict(poligono=p,escenario=e,estado='no_construido',detalle=str(error))
    except LimiteRecursos as error:
        return dict(poligono=p,escenario=e,estado='omitido',detalle=str(error))
    # Errores técnicos/invariantes se propagan: no son escenarios aleatorios fallidos.


def filas(tareas, workers=1):
    """Orden determinista; máximo 2*workers futuros y ningún grafo en el padre."""
    if not isinstance(workers,int) or isinstance(workers,bool) or workers < 1:
        raise ValueError('workers debe ser entero positivo.')
    if workers == 1:
        yield from map(realizar,tareas)
        return
    with ProcessPoolExecutor(max_workers=workers,
                             mp_context=multiprocessing.get_context('spawn')) as pool:
        it = iter(tareas)
        pendientes = []
        for _ in range(2*workers):
            tarea = next(it,None)
            if tarea is None: break
            pendientes.append(pool.submit(realizar,tarea))
        while pendientes:
            yield pendientes.pop(0).result()
            tarea = next(it,None)
            if tarea is not None:
                pendientes.append(pool.submit(realizar,tarea))
