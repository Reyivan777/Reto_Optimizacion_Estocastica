"""Ejecución económica/espacial independiente y comparación pareada reproducible."""
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import hashlib
import json
import importlib.metadata
import numpy as np
import pandas as pd
from .optimizacion_economica import planificar, DatosConCuotas, validar_cuotas
from .experimento import (ejecutar_escenario, seleccionar_poligonos, LimiteRecursos,
                          guardar_detalle_poligono, guardar_monte_carlo_por_poligono)
from .geometria import EscenarioNoConstruido


def ejecutar(datos, config, C, modo='economico', etapa='ambas', salida=None,
             comparar=True, graficas=True, progreso=None, limite_solver=60.):
    """Cada llamada crea una carpeta exclusiva. No sobrescribe resultados previos.

    etapa='economica' no ejecuta DSATUR. Para etapa espacial independiente,
    cargar planes.json y usar DatosConCuotas con ejecutar_escenario/ejecutar_lote.
    Las comparaciones se calculan de nuevo con idéntica config y versiones.
    Si las cuotas no cambian se reutiliza el resultado fijo de esa misma llamada.
    """
    if modo not in ('fijo','economico') or etapa not in ('economica','ambas'):
        raise ValueError('Modo o etapa desconocido.')
    ids=seleccionar_poligonos(config.poligonos)
    inicio=perf_counter()
    ruta=Path(salida or datos.root/'resultados'/'ejecuciones') / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'_'+modo)
    ruta.mkdir(parents=True,exist_ok=False)
    planes=planificar(datos,config,ids,limite_solver) if modo=='economico' else {}
    (ruta/'planes.json').write_text(json.dumps(planes,ensure_ascii=False,indent=2)+'\n')
    cuotas=[]; economias=[]
    for p in ids:
        a,n,R,q=datos.poligono(p,config); costos=datos.especies.costo_unitario.to_numpy()
        plan=planes.get(p,{})
        x=np.asarray(plan['R_ajustada']) if 'R_ajustada' in plan else (R if modo=='fijo' else None)
        B=a*config.presupuesto_por_ha
        economias.append(dict(poligono=p,presupuesto_um=B,costo_original_um=float(costos@q),
            costo_ajustado_um=float(costos@(x-n)) if x is not None else np.nan,
            ahorro_um=float(costos@(R-x)) if x is not None else np.nan,
            estado_economia=plan.get('estado','cuotas_fijas'),seg_economia=plan.get('seg_economia',0),
            costo_minimo_um=plan.get('costo_minimo_um'),
            certificado_desviacion=plan.get('certificado_desviacion',False),
            certificado_desempate=plan.get('certificado_desempate',False),detalle=plan.get('detalle','')))
        for s,nombre in enumerate(datos.S):
            delta=int(x[s]-R[s]) if x is not None else np.nan
            cuotas.append(dict(poligono=p,especie=nombre,R_original=int(R[s]),existentes=int(n[s]),
                R_ajustada=int(x[s]) if x is not None else np.nan,
                compras=int(x[s]-n[s]) if x is not None else np.nan,
                diferencia=delta,diferencia_absoluta=abs(delta),
                diferencia_pct=100*delta/R[s] if R[s] else (0 if delta==0 else np.nan)))
    economia=pd.DataFrame(economias); economia.to_csv(ruta/'economia.csv',index=False)
    pd.DataFrame(cuotas).to_csv(ruta/'cuotas.csv',index=False)
    filas=[]; originales=[]; diferencias=[]
    vista=DatosConCuotas(datos,planes) if modo=='economico' else datos
    corridas=0
    for p in ids if etapa=='ambas' else []:
        for e in range(config.escenarios):
            f=dict(poligono=p,escenario=e,estado='fallo',estado_factibilidad='error_ejecucion',detalle='')
            d=None
            try:
                if modo=='economico' and planes[p]['estado']!='factible_economicamente':
                    f.update(estado_factibilidad=planes[p]['estado'],detalle=planes[p]['detalle'])
                    if planes[p]['estado']=='omitido_limite_computacional': f['estado']='omitido'
                else:
                    if corridas>=config.max_corridas:
                        raise LimiteRecursos('Límite de escenarios solicitado; comparación auxiliar no cuenta como escenario adicional.')
                    corridas+=1
                    original=od=None
                    if comparar and modo=='economico':
                        original,od=ejecutar_escenario(p,e,datos,config,C)
                        originales.append(original)
                    sin_cambio=original is not None and planes[p]['R_original']==planes[p]['R_ajustada']
                    f,d=(dict(original),od) if sin_cambio else ejecutar_escenario(p,e,vista,config,C)
                    f['reutilizado_fijo']=sin_cambio
                    f['seg_espacial_adicional']=0. if sin_cambio else f['seg_total']
                    if modo=='economico':
                        _,n,R,_=datos.poligono(p,config)
                        asignadas=np.bincount(d['final'],minlength=len(R))
                        validar_cuotas(R,n,asignadas,datos.especies.costo_unitario.to_numpy(),planes[p]['presupuesto_um'])
                        np.testing.assert_array_equal(asignadas-n,planes[p]['compras'])
                    f['estado_factibilidad']='factible_economica_y_espacialmente' if f['cumple_presupuesto'] else 'inviable_economicamente_cuotas_fijas'
                    if original is not None:
                        np.testing.assert_array_equal(d['g']['U'],od['g']['U'])
                        np.testing.assert_array_equal(d['fijas'],od['fijas'])
                        diferencias.append(dict(poligono=p,escenario=e,geometria_identica=True,
                            **{k+'_fijo':original[k] for k in ('J_base','J_dsatur','J_final')},
                            **{k+'_economico':f[k] for k in ('J_base','J_dsatur','J_final')},
                            cambio_J_final=f['J_final']-original['J_final'],
                            cambio_J_final_pct=100*(f['J_final']/original['J_final']-1) if original['J_final'] else np.nan,
                            seg_fijo=original['seg_total'],seg_economico_adicional=f['seg_espacial_adicional']))
            except LimiteRecursos as error:
                d=None; f.update(estado='omitido',estado_factibilidad='omitido_limite_computacional',detalle=str(error))
            except EscenarioNoConstruido as error:
                d=None; f.update(estado='fallo',estado_factibilidad='economica_factible_espacial_no_construida' if modo=='economico' else 'espacial_no_construida',detalle=str(error)+'; no prueba imposibilidad fuera de la malla/límite empleado')
            except Exception as error:
                d=None; f.update(estado='fallo',estado_factibilidad='error_ejecucion',detalle=f'{type(error).__name__}: {error}')
            f['seg_economia']=planes.get(p,{}).get('seg_economia',0.)  # una vez por polígono, no sumar por escenario
            filas.append(f)
            if d is not None and e==0:
                guardar_detalle_poligono(ruta,vista,f,d,C,graficas=graficas)
            if progreso: progreso(f)
    lote=pd.DataFrame(filas)
    if filas:
        lote.to_csv(ruta/'escenarios.csv',index=False)
        guardar_monte_carlo_por_poligono(ruta,lote,guardar_figuras=graficas)
    if originales: pd.DataFrame(originales).to_csv(ruta/'referencia_fija_pareada.csv',index=False)
    pares=pd.DataFrame(diferencias)
    if diferencias: pares.to_csv(ruta/'comparacion_pareada.csv',index=False)
    resumen=economia.copy()
    if filas:
        metricas=['J_base','J_dsatur','J_final','seg_total','seg_espacial_adicional']
        ok=lote.loc[lote.estado.eq('ok')].reindex(columns=['poligono']+metricas)
        medias=ok.groupby('poligono')[metricas].mean().add_suffix('_media')
        medias['escenarios_completados']=ok.groupby('poligono').size()
        resumen=resumen.merge(medias,on='poligono',how='left')
        resumen['escenarios_completados']=resumen.escenarios_completados.fillna(0).astype(int)
        resumen['escenarios_solicitados']=config.escenarios
        estados=lote.groupby('poligono').estado_factibilidad.agg(lambda x:';'.join(sorted(set(x))))
        resumen=resumen.merge(estados,on='poligono',how='left')
    if diferencias:
        resumen=resumen.merge(pares.groupby('poligono')[['cambio_J_final','cambio_J_final_pct']].mean().add_suffix('_media'),on='poligono',how='left')
    resumen.to_csv(ruta/'resumen_por_poligono.csv',index=False)
    fuentes={str(p.relative_to(datos.root)):hashlib.sha256(p.read_bytes()).hexdigest()
             for sub in ('data','config','reforestacion') for p in (datos.root/sub).glob('*') if p.is_file()}
    manifiesto=dict(config=asdict(config),modo=modo,etapa=etapa,matriz_C=C.tolist(),
        orden_especies=datos.S,limite_solver_segundos=limite_solver,
        versiones={s:importlib.metadata.version(s) for s in ('numpy','pandas','scipy','networkx','matplotlib')},
        fuentes_sha256=fuentes,semillas='SeedSequence([semilla,p,escenario]).spawn(3)',
        solicitado=len(ids)*config.escenarios if etapa=='ambas' else 0,
        ejecutado_ok=sum(f['estado']=='ok' for f in filas),
        estados={k:int(v) for k,v in lote.estado_factibilidad.value_counts().items()} if filas else {},
        seg_total=perf_counter()-inicio,
        tiempos='economía una vez por polígono; seg_espacial_adicional excluye reutilizados; seg_total de fila conserva el tiempo de su origen',
        interpretacion='±10% sobre cuotas finales originales; pendiente de confirmación; solo adquisición')
    (ruta/'configuracion.json').write_text(json.dumps(manifiesto,ensure_ascii=False,indent=2)+'\n')
    if graficas:
        graficar_comparacion(ruta,economia,pares)
    return ruta,economia,lote,pares


def graficar_comparacion(ruta,economia,pares):
    """Figuras regenerables desde CSV sin repetir ninguna simulación."""
    import matplotlib.pyplot as plt
    ruta=Path(ruta)
    fig,axes=plt.subplots(2,1,figsize=(12,8),layout='constrained')
    ax=axes[0]
    ax.plot(economia.poligono,economia.presupuesto_um,'s',label='Presupuesto',color='black')
    ax.plot(economia.poligono,economia.costo_original_um,'o',label='Cuotas fijas')
    ax.plot(economia.poligono,economia.costo_ajustado_um,'x',label='Cuotas aplicadas')
    ax.set(ylabel='Adquisición (u.m.)',title='Presupuesto individual y adquisición');ax.legend()
    ax=axes[1]
    ax.bar(economia.poligono-.18,economia.presupuesto_um-economia.costo_original_um,width=.35,label='Saldo con cuotas fijas')
    ax.bar(economia.poligono+.18,economia.presupuesto_um-economia.costo_ajustado_um,width=.35,label='Saldo con cuotas aplicadas')
    ax.axhline(0,color='black',lw=1)
    ax.set(xlabel='Polígono',ylabel='Presupuesto − adquisición (u.m.)',title='Saldo individual: negativo indica déficit');ax.legend()
    for ax in axes: ax.set_xticks(economia.poligono,[f'P{p}' for p in economia.poligono],fontsize=8)
    fig.savefig(ruta/'economia.png',dpi=140);plt.close(fig)
    if not pares.empty:
        medias=pares.groupby('poligono').cambio_J_final.agg(['mean','count'])
        fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
        ax.bar([f'P{p}\nn={int(row["count"])}' for p,row in medias.iterrows()],medias['mean'])
        ax.axhline(0,color='black',lw=.7)
        ax.set(ylabel='J económico − J fijo (media pareada)',title='Cambio de competencia: positivo implica aumento');ax.tick_params(axis='x',labelsize=7)
        fig.savefig(ruta/'cambio_competencia.png',dpi=140);plt.close(fig)
