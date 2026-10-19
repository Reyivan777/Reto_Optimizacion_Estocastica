"""Orquestación acotada; cada fila conserva polígono, escenario y estado."""
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
import json, platform, importlib.metadata
import numpy as np
import pandas as pd
from .geometria import (dimensiones, flujos, simular_existentes, candidatas,
                        construir_grafo, EscenarioNoConstruido)
from .algoritmos import validar_C, base_aleatoria, dsatur, busqueda_local, objetivo
from .validacion import validar_solucion
from .economia import presupuesto_poligono

class LimiteRecursos(ValueError):
    pass

def ejecutar_escenario(p, escenario, datos, config, C):
    validar_C(C)
    inicio=perf_counter()
    area,n,R,q=datos.poligono(p,config)
    if R.sum() > config.max_plantas:
        raise LimiteRecursos(f'{R.sum()} plantas exceden límite {config.max_plantas}.')
    limites=dimensiones(area,config)
    rp,rb,rl=flujos(p,escenario,config)
    F,fijas=simular_existentes(n,limites,config,rp)
    pool,V=candidatas(F,limites,int(q.sum()),config)
    g=construir_grafo(p,F,V,config)
    tiempo_geometria=perf_counter()-inicio
    t=perf_counter(); base=base_aleatoria(fijas,q,rb); tb=perf_counter()-t
    t=perf_counter(); ds=dsatur(fijas,q,g,C); td=perf_counter()-t
    t=perf_counter(); final,h,stats=busqueda_local(ds,g,C,rl,config.intentos(int(q.sum()))); tl=perf_counter()-t
    for y in [base,ds,final]:
        validar_solucion(y,g,fijas,n,R,limites,config)
    assert np.array_equal(g['U'][:len(F)],F)
    jb,jd,jf=[objetivo(y,g,C) for y in [base,ds,final]]
    fijo=objetivo(final,g,C,True)['FF']
    assert jf<=jd+1e-8
    fila={'poligono':p,'escenario':escenario,'estado':'ok','detalle':'',
        'existentes':int(n.sum()),'nuevas':int(q.sum()),'total':int(R.sum()),
        'candidatas':len(pool),'J_base':jb,'J_dsatur':jd,'J_final':jf,'J_fijo':fijo,
        'mejora_pct':100*(jb-jf)/jb if jb else np.nan,
        'mejora_modificable_pct':100*(jb-jf)/(jb-fijo) if jb>fijo else np.nan,
        'costo_um':float(q@datos.especies.costo_unitario.to_numpy()),
        'seg_geometria':tiempo_geometria,'seg_base':tb,'seg_dsatur':td,'seg_local':tl,
        'seg_total':perf_counter()-inicio, **{'local_'+k:v for k,v in stats.items()}}
    fila.update(presupuesto_poligono(datos,p,config))
    return fila,{'g':g,'base':base,'dsatur':ds,'final':final,'historia':h,'F':F,'fijas':fijas,'V':V,'limites':limites,'n':n,'R':R,'q':q,'stats':stats}


def seleccionar_poligonos(seleccion):
    if isinstance(seleccion, str) and seleccion == 'todos':
        return list(range(1,31))
    if isinstance(seleccion, (int, np.integer)):
        seleccion = [seleccion]
    ids = list(seleccion)
    if not ids or any(not isinstance(p, (int,np.integer)) or isinstance(p,bool) or p not in range(1,31) for p in ids) or len(set(ids)) != len(ids):
        raise ValueError('Use un ID 1–30, una lista sin duplicados o "todos".')
    return [int(p) for p in ids]


def ejecutar_lote(datos, config, C, salida_detalles=None, graficas=True, progreso=None):
    validar_C(C)
    ids = seleccionar_poligonos(config.poligonos)
    filas = []
    for p in ids:
        for e in range(config.escenarios):
            detalle = None
            try:
                if len(filas) >= config.max_corridas:
                    raise LimiteRecursos('Presupuesto máximo de corridas del lote agotado.')
                fila,detalle = ejecutar_escenario(p,e,datos,config,C)
            except LimiteRecursos as error:
                fila = dict(poligono=p,escenario=e,estado='omitido',detalle=str(error))
            except (ValueError, AssertionError) as error:
                fila = dict(poligono=p,escenario=e,estado='fallo',detalle=f'{type(error).__name__}: {error}')
            if detalle is not None and e == 0 and salida_detalles is not None:
                guardar_detalle_poligono(salida_detalles, datos, fila, detalle, C, graficas=graficas)
            if e == 0 and detalle is None and salida_detalles is not None:
                ruta = Path(salida_detalles)/f'P{p}'
                for nombre in ('distribucion.csv','comparacion.csv','graficas/01_existentes.png','graficas/02_final.png','graficas/03_comparacion.png'):
                    (ruta/nombre).unlink(missing_ok=True)
            filas.append(fila)
            if progreso is not None:
                progreso(fila)
    return pd.DataFrame(filas)


def agregar(lote, poligonos_esperados=None, escenarios_esperados=None):
    """Solo publica sumas de escenarios completos respecto al conjunto solicitado.

    Por defecto exige P1–P30. Un reporte de un solo polígono debe pasarlo
    explícitamente como conjunto esperado. No se mezclan escenarios.
    """
    ids = seleccionar_poligonos('todos' if poligonos_esperados is None else poligonos_esperados)
    if lote.duplicated(['poligono','escenario']).any():
        raise ValueError('Hay escenarios duplicados por polígono.')
    if not set(lote.poligono).issubset(ids):
        raise ValueError('El lote contiene polígonos no solicitados.')
    escenarios = sorted(lote.escenario.unique()) if escenarios_esperados is None else list(range(escenarios_esperados))
    metricas = ['existentes','nuevas','total','J_base','J_dsatur','J_final','costo_um','presupuesto_um','saldo_um']
    filas = []
    for e in escenarios:
        tabla = lote.loc[lote.escenario.eq(e)]
        ok = tabla.loc[tabla.estado.eq('ok')]
        completos = sorted(ok.poligono.tolist()) == sorted(ids)
        fila = dict(escenario=e, estado='completo' if completos else 'incompleto',
            poligonos_esperados=len(ids), poligonos_completados=len(ok),
            poligonos_faltantes=','.join(map(str,sorted(set(ids)-set(ok.poligono)))))
        for col in metricas:
            fila[col] = float(ok[col].sum()) if completos and col in ok else np.nan
        fila['mejora_pct'] = 100*(fila['J_base']-fila['J_final'])/fila['J_base'] if completos and fila['J_base'] > 0 else np.nan
        fila['poligonos_fuera_presupuesto'] = int((~ok.cumple_presupuesto.eq(True)).sum()) if completos and 'cumple_presupuesto' in ok else np.nan
        fila['cumplen_todos_presupuesto'] = bool(ok.cumple_presupuesto.all()) if completos and 'cumple_presupuesto' in ok else None
        filas.append(fila)
    return pd.DataFrame(filas)


def guardar_ejecucion(carpeta, datos, config, C, lote, organizado=False):
    carpeta = Path(carpeta); carpeta.mkdir(parents=True,exist_ok=True)
    if organizado:
        from .reportes import guardar_modelo_completo
        return guardar_modelo_completo(carpeta,datos,config,C,lote)
    else:
        lote.to_csv(carpeta/'escenarios.csv',index=False)
        agregar(lote, seleccionar_poligonos(config.poligonos), config.escenarios).to_csv(carpeta/'agregado.csv',index=False)
    datos.resumen(config).to_csv(carpeta/'cuotas_30.csv',index=False)
    versiones = {x:importlib.metadata.version(x) for x in ['numpy','pandas','scipy','networkx','matplotlib','nbformat','nbclient']}
    (carpeta/'configuracion.json').write_text(json.dumps(dict(config=asdict(config),matriz_C=C.tolist(),
        versiones=versiones,python=platform.python_version(),solicitados=len(lote),
        estados=lote.estado.value_counts().to_dict()),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def guardar_detalle_poligono(raiz, datos, fila, detalle, C, graficas=True):
    """Guarda especies y coordenadas simuladas del escenario 0."""
    import matplotlib.pyplot as plt
    from . import visualizacion as vis
    p = int(fila['poligono'])
    ruta = Path(raiz)/f'P{p}'
    ruta.mkdir(parents=True, exist_ok=True)
    g, F = detalle['g'], detalle['F']
    U, nf = g['U'], len(F)
    y = detalle['final']
    pd.DataFrame({
        'indice': np.arange(len(y)), 'x_m': U[:, 0], 'y_m': U[:, 1],
        'existente': np.arange(len(y)) < nf,
        'especie': [datos.S[int(s)] for s in y]
    }).to_csv(ruta/'distribucion.csv', index=False)
    tabla = pd.DataFrame([
        {'metodo': nombre, 'J': objetivo(etiquetas, g, C),
         **objetivo(etiquetas, g, C, True), 'segundos_asignacion': tiempo}
        for nombre, etiquetas, tiempo in [
            ('Aleatoria', detalle['base'], fila['seg_base']),
            ('DSATUR', detalle['dsatur'], fila['seg_dsatur']),
            ('DSATUR + local', y, fila['seg_dsatur'] + fila['seg_local'])
        ]
    ])
    for clave in ('presupuesto_um','costo_um','saldo_um','presupuesto_utilizado_pct','cumple_presupuesto'):
        tabla[clave] = fila[clave]
    tabla['escenario'] = 0
    tabla.to_csv(ruta/'comparacion.csv', index=False)
    if graficas:
        carpeta = ruta/'graficas'
        carpeta.mkdir(exist_ok=True)
        figuras = [
            ('01_existentes.png', vis.mapa(F, detalle['fijas'], datos.S,
                detalle['limites'], f'P{p}: plantas existentes simuladas')),
            ('02_final.png', vis.mapa(U, y, datos.S, detalle['limites'],
                f'P{p}: distribución optimizada', nf=nf)),
            ('03_comparacion.png', vis.comparacion(tabla,
                f'P{p}: aleatoria frente a DSATUR + búsqueda local')),
        ]
        for nombre, fig in figuras:
            try:
                fig.savefig(carpeta/nombre, dpi=140, bbox_inches='tight')
            finally:
                plt.close(fig)
    return ruta

def guardar_monte_carlo_por_poligono(raiz, lote, guardar_figuras=True):
    """Un CSV, resumen estadístico y figura por polígono para escenarios espaciales."""
    from . import visualizacion as vis
    import matplotlib.pyplot as plt
    raiz = Path(raiz)
    for poligono, tabla in lote.groupby('poligono', sort=True):
        ruta = raiz/f'P{int(poligono)}'
        ruta.mkdir(parents=True, exist_ok=True)
        tabla.to_csv(ruta/'monte_carlo.csv', index=False)
        ok = tabla.loc[tabla.estado.eq('ok')]
        if not ok.empty:
            estadisticas = ok[['J_base','J_dsatur','J_final','mejora_pct']].agg(
                ['count','mean','std','min','max']).T
            estadisticas['error_estandar_media'] = (
                estadisticas['std']/np.sqrt(estadisticas['count']))
            estadisticas['escenarios_solicitados'] = len(tabla)
            estadisticas['escenarios_completados'] = len(ok)
            estadisticas['escenarios_excluidos'] = len(tabla)-len(ok)
            estadisticas.to_csv(ruta/'estadisticas_mc.csv')
        else:
            pd.DataFrame(columns=['metrica','count','mean','std','min','max']).to_csv(ruta/'estadisticas_mc.csv',index=False)
        if guardar_figuras:
            figuras = ruta/'graficas'
            figuras.mkdir(exist_ok=True)
            fig = vis.monte_carlo(tabla, f'P{int(poligono)}: escenarios espaciales')
            try:
                fig.savefig(figuras/'04_monte_carlo.png', dpi=140, bbox_inches='tight')
            finally:
                plt.close(fig)

