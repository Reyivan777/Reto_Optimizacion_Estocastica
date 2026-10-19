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


def ejecutar_lote(datos, config, C):
    validar_C(C)
    ids = seleccionar_poligonos(config.poligonos)
    filas = []
    for p in ids:
        for e in range(config.escenarios):
            try:
                if len(filas) >= config.max_corridas:
                    raise LimiteRecursos('Presupuesto máximo de corridas del lote agotado.')
                fila,_ = ejecutar_escenario(p,e,datos,config,C)
            except LimiteRecursos as error:
                fila = dict(poligono=p,escenario=e,estado='omitido',detalle=str(error))
            except (ValueError, AssertionError) as error:
                fila = dict(poligono=p,escenario=e,estado='fallo',detalle=f'{type(error).__name__}: {error}')
            filas.append(fila)
    return pd.DataFrame(filas)


def agregar(lote):
    """No sumar escenarios como si fueran un solo terreno: totales por escenario."""
    ok = lote.loc[lote.estado.eq('ok')]
    if ok.empty:
        return pd.DataFrame(columns=['escenario','existentes','nuevas','total','J_base','J_dsatur','J_final','costo_um','poligonos_completados','mejora_pct'])
    out = ok.groupby('escenario')[['existentes','nuevas','total','J_base','J_dsatur','J_final','costo_um']].sum()
    out['poligonos_completados'] = ok.groupby('escenario').size()
    out['mejora_pct'] = 100*(out.J_base-out.J_final)/out.J_base.replace(0,np.nan)
    return out.reset_index()


def guardar_ejecucion(carpeta, datos, config, C, lote):
    carpeta = Path(carpeta); carpeta.mkdir(parents=True,exist_ok=True)
    lote.to_csv(carpeta/'escenarios.csv',index=False)
    agregar(lote).to_csv(carpeta/'agregado.csv',index=False)
    datos.resumen(config).to_csv(carpeta/'cuotas_30.csv',index=False)
    versiones = {x:importlib.metadata.version(x) for x in ['numpy','pandas','scipy','networkx','matplotlib','nbformat','nbclient']}
    (carpeta/'configuracion.json').write_text(json.dumps(dict(config=asdict(config),matriz_C=C.tolist(),
        versiones=versiones,python=platform.python_version(),solicitados=len(lote),
        estados=lote.estado.value_counts().to_dict()),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
