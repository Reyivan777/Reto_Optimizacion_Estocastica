"""Validación pareada completa, paralelizada por polígono (no altera semillas).

Ejemplo: python validar_lote_economico.py --escenarios 12 --workers 6
Cada trabajador usa el ejecutor público y una carpeta exclusiva. El índice de
validación reúne sus tablas; solo suma J de escenarios con todos los polígonos.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import json
import numpy as np
import pandas as pd
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.dos_etapas import ejecutar


def trabajador(args):
    p,escenarios,salida=args
    d=Datos(ROOT);C=cargar_competencia(ROOT/'config/competencia.json',d.S)
    cfg=perfil('completo',poligonos=(p,),escenarios=escenarios)
    ruta,_,_,_=ejecutar(d,cfg,C,salida=salida,graficas=False)
    return p,str(ruta)


def validar(escenarios=12,workers=6):
    inicio=perf_counter()
    ruta=ROOT/'resultados'/'ejecuciones'/('validacion_30_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    ruta.mkdir(parents=True,exist_ok=False)
    carpetas={}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        trabajos=[pool.submit(trabajador,(p,escenarios,str(ruta/'poligonos'))) for p in range(1,31)]
        for job in as_completed(trabajos):
            p,carpeta=job.result();carpetas[p]=carpeta
            print(f'P{p}: {len(carpetas)}/30 polígonos terminados',flush=True)
    tablas={}
    for nombre in ('economia','cuotas','resumen_por_poligono','escenarios','referencia_fija_pareada','comparacion_pareada'):
        tabla=pd.concat([pd.read_csv(Path(carpetas[p])/(nombre+'.csv')) for p in range(1,31)],ignore_index=True)
        tabla.to_csv(ruta/(nombre+'.csv'),index=False);tablas[nombre]=tabla
    historial=pd.concat([pd.read_csv(ROOT/'resultados'/f'P{p}'/'monte_carlo.csv') for p in range(1,31)])
    nueva=tablas['referencia_fija_pareada']
    comparada=nueva.merge(historial,on=['poligono','escenario'],suffixes=('_nueva','_historica'),validate='one_to_one')
    errores={k:float(abs(comparada[k+'_nueva']-comparada[k+'_historica']).max()) for k in ('J_base','J_dsatur','J_final')}
    assert len(comparada)==30*escenarios, 'Faltan referencias históricas para escenarios solicitados.'
    assert max(errores.values())<1e-8, 'Regresión histórica fuera de tolerancia.'
    lote=tablas['escenarios'];pares=tablas['comparacion_pareada'];economia=tablas['economia']
    assert len(lote)==30*escenarios and lote.estado.eq('ok').all()
    assert lote.estado_factibilidad.eq('factible_economica_y_espacialmente').all()
    assert (lote.J_final<=lote.J_dsatur+1e-8).all()
    assert pares.geometria_identica.all() and len(pares)==30*escenarios
    assert economia.certificado_desviacion.all() and economia.certificado_desempate.all()
    assert (economia.costo_ajustado_um<=economia.presupuesto_um).all()
    globales=[]
    for e,g in pares.groupby('escenario'):
        completo=len(g)==30 and g.poligono.nunique()==30
        globales.append(dict(escenario=int(e),completo=completo,n_poligonos=len(g),
            J_fijo=g.J_final_fijo.sum() if completo else np.nan,
            J_economico=g.J_final_economico.sum() if completo else np.nan,
            cambio_J=g.cambio_J_final.sum() if completo else np.nan))
    globales=pd.DataFrame(globales)
    globales['cambio_pct']=100*(globales.J_economico/globales.J_fijo-1)
    globales.to_csv(ruta/'comparacion_global.csv',index=False)
    evidencia=dict(base_git='75a54abc199563471bec29bba051da3d1d483e8b',workers=workers,
        escenarios_por_poligono=escenarios,pares_verificados=len(pares),
        escenarios_economicos_validos=int(lote.estado.eq('ok').sum()),
        ejecuciones_espaciales_fijas=len(nueva),
        ejecuciones_espaciales_economicas_adicionales=int((~lote.reutilizado_fijo).sum()),
        reutilizados=int(lote.reutilizado_fijo.sum()),regresion_historica_max_abs=errores,
        seg_pared=perf_counter()-inicio,seg_economia=float(economia.seg_economia.sum()),
        seg_espacial_fijo_acumulado=float(nueva.seg_total.sum()),
        seg_espacial_economico_adicional_acumulado=float(lote.seg_espacial_adicional.sum()),
        media_J_fijo=float(globales.J_fijo.mean()),media_J_economico=float(globales.J_economico.mean()),
        media_cambio_pct=float(globales.cambio_pct.mean()),std_cambio_pct=float(globales.cambio_pct.std(ddof=1)),
        ahorro_um=float(economia.ahorro_um.sum()),
        carpetas={str(p):str(Path(c).relative_to(ruta)) for p,c in sorted(carpetas.items())},
        nota='Tiempo de pared hasta tablas; tiempos acumulados de procesos concurrentes no equivalen a tiempo de pared. Sin PNG individuales; distribuciones escenario 0 guardadas.')
    (ruta/'validacion.json').write_text(json.dumps(evidencia,ensure_ascii=False,indent=2)+'\n')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    axes[0].plot(globales.escenario,globales.J_fijo,'o-',label='Cuotas fijas')
    axes[0].plot(globales.escenario,globales.J_economico,'x-',label='Cuotas económicas')
    axes[0].set(xlabel='Escenario conjunto (30 polígonos)',ylabel='J final agregado',title='Comparación pareada');axes[0].legend()
    axes[1].bar(globales.escenario,globales.cambio_pct)
    axes[1].axhline(0,color='black',lw=.7)
    axes[1].set(xlabel='Escenario conjunto (30 polígonos)',ylabel='Cambio frente a cuotas fijas (%)',title='Negativo = menor competencia')
    fig.savefig(ruta/'comparacion_global.png',dpi=140);plt.close(fig)
    print(ruta,flush=True)
    return ruta

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--escenarios',type=int,default=12)
    parser.add_argument('--workers',type=int,default=6)
    args=parser.parse_args()
    if args.workers<1 or not 1<=args.escenarios<=12: parser.error('workers >=1; escenarios entre 1 y 12 para comparación histórica.')
    validar(args.escenarios,args.workers)
