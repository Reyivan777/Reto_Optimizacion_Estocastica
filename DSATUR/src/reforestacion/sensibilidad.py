"""Sensibilidad de C: hipótesis explícitas y evaluación bajo una métrica común.

Los indicadores taxonómicos no son medidas de agua, nutrientes ni raíces.
No cambia los motores, el modelo económico ni los flujos de escenarios.
"""
import json
import re
from pathlib import Path
import numpy as np
from .algoritmos import validar_C, objetivo
from .experimento import ejecutar_escenario
from .geometria import EscenarioNoConstruido
from .experimento import LimiteRecursos
from .monte_carlo import _huella
from .optimizacion_economica import validar_cuotas


def matriz_taxonomica(especies, fondo, genero, identidad):
    """C_ab = fondo + genero*[mismo género] + identidad*[misma especie]."""
    pesos = (fondo, genero, identidad)
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in pesos):
        raise ValueError('Pesos numéricos requeridos.')
    if not np.isfinite(pesos).all() or min(pesos) < 0:
        raise ValueError('Pesos finitos no negativos requeridos.')
    if len(set(especies)) != len(especies) or any(len(s.split()) < 2 for s in especies):
        raise ValueError('Catálogo taxonómico inválido.')
    generos = np.array([s.split()[0] for s in especies])
    C = fondo*np.ones((len(especies),len(especies)))
    C += genero*(generos[:,None] == generos[None,:]) + identidad*np.eye(len(especies))
    validar_C(C, len(especies))
    return C


def cargar_hipotesis(path, especies, original):
    """Siempre incluye original; admite pesos o matriz explícita, nunca ambos."""
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    if raw['especies'] != especies or raw.get('version') != 1:
        raise ValueError('Versión u orden de especies incompatible.')
    validar_C(original, len(especies))
    matrices = {'original': np.array(original, copy=True)}
    if not isinstance(raw.get('hipotesis'), list) or not raw['hipotesis']:
        raise ValueError('Se requiere al menos una hipótesis alternativa.')
    for h in raw['hipotesis']:
        nombre = h['nombre']
        if not isinstance(nombre,str) or not re.fullmatch(r'[a-z][a-z0-9_]*',nombre) or nombre in matrices:
            raise ValueError('Nombre inválido, reservado o duplicado.')
        if h.get('naturaleza') != 'heuristica_no_calibrada' or not h.get('justificacion'):
            raise ValueError('Identificar naturaleza y justificación heurísticas.')
        if ('pesos' in h) == ('matriz' in h):
            raise ValueError('Elegir exactamente pesos o matriz.')
        if 'pesos' in h:
            if set(h['pesos']) != {'fondo','genero','identidad'}:
                raise ValueError('Pesos incompletos o desconocidos.')
            C = matriz_taxonomica(especies, **h['pesos'])
        else:
            C = np.asarray(h['matriz'], dtype=float)
            validar_C(C, len(especies))
        matrices[nombre] = C
    return matrices, raw


def comparar(p, e, datos, cfg, matrices, plan=None):
    """Retiene solo una pareja (polígono, índice); errores técnicos se propagan.

    Diferencias firmadas bajo C evaluadora frente a solución original; negativo
    favorece la alternativa. No se comparan objetivos de distintas matrices.
    """
    if 'original' not in matrices:
        raise ValueError('Falta referencia original.')
    for C in matrices.values():
        validar_C(C, len(datos.S))
    filas, soluciones = [], {}
    for nombre, C in matrices.items():
        try:
            f, r = ejecutar_escenario(p,e,datos,cfg,C)
        except (EscenarioNoConstruido, LimiteRecursos) as error:
            filas.append(dict(poligono=p,escenario=e,motor=cfg.motor,matriz=nombre,
                              estado='omitido' if isinstance(error,LimiteRecursos) else 'no_construido',
                              detalle=str(error)))
            continue
        if plan is not None:
            validar_cuotas(plan['R_original'],r['n'],
                np.bincount(r['final'],minlength=len(C)),
                datos.especies.costo_unitario.to_numpy(),plan['presupuesto_um'])
            if not f['cumple_presupuesto']:
                raise AssertionError('Plan económico fuera de presupuesto.')
        f.update(matriz=nombre,
            entradas_sha256=_huella(r['g_inicial']['U'],r['fijas'],r['q'],r['base']),
            solucion_sha256=_huella(r['g']['U'],r['final']))
        # Estadístico suficiente para recalcular J bajo cualquier C simétrica.
        # Una masa por par no ordenado; no es volumen radicular observado.
        etiquetas = r['final'][r['g']['pares']]
        a,b = np.sort(etiquetas,axis=1).T
        masa = np.bincount(a*len(C)+b,weights=r['g']['pesos'],minlength=len(C)**2)
        f.update({f'peso_{i}_{j}':float(masa[i*len(C)+j])
                  for i in range(len(C)) for j in range(i,len(C))})
        filas.append(f)
        soluciones[nombre] = r
    if len({f['entradas_sha256'] for f in filas if f['estado']=='ok'}) > 1:
        raise AssertionError('Entradas no pareadas.')
    cruzadas = []
    ref = soluciones.get('original')
    for evaluadora, C in matrices.items():
        jref = objetivo(ref['final'],ref['g'],C) if ref is not None else None
        for nombre, r in soluciones.items():
            j = objetivo(r['final'],r['g'],C)
            diferencia = j-jref if jref is not None else None
            cruzadas.append(dict(poligono=p,escenario=e,motor=cfg.motor,
                matriz_solucion=nombre,matriz_evaluadora=evaluadora,J=j,J_referencia=jref,
                diferencia_vs_original=diferencia,
                diferencia_pct=100*diferencia/jref if jref else None,
                fraccion_etiquetas_nuevas_distintas=float(np.mean(r['final'][len(r['F']):]
                    !=ref['final'][len(ref['F']):])) if ref is not None and len(r['final'])>len(r['F']) else None,
                posiciones_finales_iguales=bool(np.array_equal(r['g']['U'],ref['g']['U'])) if ref is not None else None))
    return filas, cruzadas
