"""Tres o cuatro métodos pareados y ambos motores; carpeta exclusiva.

Desde DSATUR: python scripts/comparar_posiciones.py --referencia resultados/posiciones_FECHA/referencia_previa.json
La referencia es opcional y solo comprueba regresión con la etapa desactivada.
"""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

# Fijar antes de importar NumPy/SciPy.
for variable in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable]='1'
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.experimento import ejecutar_escenario
from reforestacion.optimizacion_economica import DatosConCuotas,planificar,validar_cuotas
from reforestacion.motores import informacion_motor


def huella(*arrays):
    h=hashlib.sha256()
    for a in arrays:h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def ejecutar(args):
    ruta=ROOT/'resultados'/('comparacion_posiciones_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    ruta.mkdir(exist_ok=False)
    cfg=perfil('completo',poligonos=tuple(map(int,args.poligonos.split(','))),escenarios=args.escenarios,
               intentos_posiciones=args.intentos_posiciones)
    datos=Datos(ROOT);C=cargar_competencia(ROOT/'config/competencia.json',datos.S)
    nativas=informacion_motor('cpp')  # cargar antes de cronometrar
    regresion=[];antes=perf_counter()
    if args.referencia:
        ref=json.loads(Path(args.referencia).read_text(encoding='utf-8'))
        for old in ref['filas']:
            f,r=ejecutar_escenario(old['poligono'],old['escenario'],datos,replace(cfg,motor=old['motor']),C)
            assert huella(r['g']['U'],r['fijas'],r['q'])==old['entradas_sha256']
            assert huella(r['final'].astype(np.int64))==old['solucion_sha256']
            dif=max(abs(f[k]-old[k]) for k in ('J_base','J_dsatur','J_final'))
            assert dif<=1e-8
            regresion.append(dict(poligono=old['poligono'],escenario=old['escenario'],motor=old['motor'],max_diferencia=dif))
        pd.DataFrame(regresion).to_csv(ruta/'regresion_desactivada.csv',index=False)
        print(f'Regresión desactivada: {len(regresion)} filas idénticas',flush=True)
    tiempo_regresion=perf_counter()-antes
    t=perf_counter();planes=planificar(datos,cfg,cfg.poligonos);seg_economia=perf_counter()-t
    assert all(p['estado']=='factible_economicamente' for p in planes.values())
    vista=DatosConCuotas(datos,planes)
    (ruta/'planes.json').write_text(json.dumps(planes,indent=2)+'\n',encoding='utf-8')
    metodos=('dsatur','especies','posiciones','mixta') if args.incluir_mixta else ('dsatur','especies','posiciones')
    filas=[];equivalencia=[];ti=perf_counter()
    with (ruta/'escenarios.jsonl').open('w',encoding='utf-8') as stream:
        for p in cfg.poligonos:
            for e in range(cfg.escenarios):
                entradas=None;salidas={};especies={}
                # Orden alternado por escenario; secuencial, sin otras cargas.
                motores=('python','cpp') if e%2==0 else ('cpp','python')
                for motor in motores:
                    for metodo in metodos:
                        conf=replace(cfg,motor=motor,optimizar_posiciones=metodo in ('posiciones','mixta'),
                                     vecindad_posiciones='mixta' if metodo=='mixta' else 'sustituciones',
                                     intentos_local=0 if metodo=='dsatur' else cfg.intentos_local)
                        f,r=ejecutar_escenario(p,e,vista,conf,C)
                        ins=huella(r['g_inicial']['U'],r['fijas'],r['q'])
                        if entradas is None:entradas=ins
                        assert ins==entradas
                        validar_cuotas(planes[p]['R_original'],r['n'],np.bincount(r['final'],minlength=len(C)),
                                      datos.especies.costo_unitario,planes[p]['presupuesto_um'])
                        assert f['cumple_presupuesto']
                        if metodo=='especies':especies[motor]=(r['final'].copy(),f['J_final'],f['costo_um'])
                        if metodo in ('posiciones','mixta'):
                            np.testing.assert_array_equal(especies[motor][0],r['final'])
                            assert f['J_final']<=especies[motor][1]
                            assert f['costo_um']==especies[motor][2]
                        out=huella(r['g']['U'],r['final'])
                        if metodo in salidas:assert salidas[metodo]==out
                        else:salidas[metodo]=out
                        reduccion=f['J_dsatur']-f['J_final']
                        f.update(metodo=metodo,entradas_sha256=ins,solucion_sha256=out,
                                 restricciones_cumplidas=True,reduccion_desde_dsatur=reduccion,
                                 reduccion_desde_dsatur_pct=100*reduccion/f['J_dsatur'] if f['J_dsatur'] else 0.)
                        filas.append(f);stream.write(json.dumps(f)+'\n');stream.flush()
                        # Solo distribución espacial C++: deja una evidencia por escenario.
                        if motor=='cpp' and metodo in ('posiciones','mixta'):
                            sufijo='_mixta' if metodo=='mixta' else ''
                            np.savez_compressed(ruta/f'P{p}_e{e}{sufijo}.npz',U_inicial=r['g_inicial']['U'],U_final=r['g']['U'],
                                etiquetas=r['final'],fijas=r['fijas'],cuotas=r['R'],pool=r['pool'],historia=r['historia_posiciones'])
                equivalencia.append(dict(poligono=p,escenario=e,metodos=len(metodos),entradas_y_soluciones_identicas=True))
            print(f'P{p}: {cfg.escenarios} escenarios × {len(metodos)} métodos × dos motores',flush=True)
    pared=perf_counter()-ti
    tabla=pd.DataFrame(filas);tabla.to_csv(ruta/'escenarios.csv',index=False)
    regresion_previa=[]
    if args.referencia_sustituciones:
        previos=pd.read_csv(Path(args.referencia_sustituciones)/'escenarios.csv')
        claves=['poligono','escenario','motor','metodo']
        nuevos=tabla.loc[tabla.metodo.ne('mixta')]
        pares=nuevos.merge(previos,on=claves,suffixes=('_nuevo','_previo'),validate='one_to_one')
        assert len(pares)==len(nuevos), 'Referencia incompleta para los escenarios solicitados.'
        for _,par in pares.iterrows():
            assert par.entradas_sha256_nuevo==par.entradas_sha256_previo
            assert par.solucion_sha256_nuevo==par.solucion_sha256_previo
            dif=max(abs(par[k+'_nuevo']-par[k+'_previo']) for k in ('J_base','J_dsatur','J_final'))
            assert dif<=1e-8
            regresion_previa.append({**{k:par[k] for k in claves},'max_diferencia_J':dif,'hashes_identicos':True})
        # También conservar la trayectoria de sustituciones, no solo el punto final.
        for p in cfg.poligonos:
            for e in range(cfg.escenarios):
                with np.load(Path(args.referencia_sustituciones)/f'P{p}_e{e}.npz') as old, np.load(ruta/f'P{p}_e{e}.npz') as new:
                    for key in old.files:
                        np.testing.assert_array_equal(old[key],new[key])
        pd.DataFrame(regresion_previa).to_csv(ruta/'regresion_sustituciones.csv',index=False)
    columnas=['J_dsatur','J_local_especies','J_final','reduccion_desde_dsatur','reduccion_desde_dsatur_pct',
              'seg_total','seg_local','seg_posiciones','posiciones_reduccion_absoluta','posiciones_reduccion_pct',
              'posiciones_evaluados','posiciones_factibles','posiciones_aceptados',
              'posiciones_factibles_sustitucion','posiciones_factibles_intercambio',
              'posiciones_aceptados_sustitucion','posiciones_aceptados_intercambio']
    tabla.groupby(['poligono','motor','metodo'])[columnas].agg(['count','mean','min','max','sum']).to_csv(ruta/'resumen.csv')
    pd.DataFrame(equivalencia).to_csv(ruta/'equivalencia.csv',index=False)
    manifiesto=dict(config=asdict(cfg),semillas='SeedSequence([semilla,p,e]) originales; posiciones [semilla,p,e,104729]',
        metodos=metodos,escenarios_pareados=len(equivalencia),ejecuciones=len(tabla),economia_segundos=seg_economia,
        regresion_filas=len(regresion),regresion_sustituciones_filas=len(regresion_previa),
        regresion_segundos=tiempo_regresion,pared_experimentos_segundos=pared,
        presupuesto_sin_tolerancia=True,restricciones_cumplidas=bool(tabla.restricciones_cumplidas.all()),
        motor_cpp=nativas,python=sys.version,plataforma=platform.platform(),cpu=platform.processor(),
        versiones={p:importlib.metadata.version(p) for p in ('numpy','scipy','pandas','networkx')},
        commit_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        fuentes_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for sub in ('src','cpp','data','config','scripts','tests') for p in (ROOT/sub).rglob('*')
            if p.is_file() and '__pycache__' not in str(p)},
        tiempos='Una medición por método/escenario; importaciones, compilación, economía y exportación fuera de seg_total. '
                'seg_posiciones incluye índice, propuestas, núcleo y reconstrucción final; seg_total es inclusivo. '
                'Orden de motores alternado por escenario; métodos en orden dsatur/especies/posiciones[/mixta]. Sin figuras.')
    (ruta/'manifiesto.json').write_text(json.dumps(manifiesto,indent=2)+'\n',encoding='utf-8')
    print(ruta,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--poligonos',default='1,13,5')
    parser.add_argument('--escenarios',type=int,default=12)
    parser.add_argument('--intentos-posiciones',type=int,default=6000)
    parser.add_argument('--referencia',type=Path)
    parser.add_argument('--incluir-mixta',action='store_true',help='Añadir sustituciones + intercambios con el mismo presupuesto')
    parser.add_argument('--referencia-sustituciones',type=Path,help='Carpeta previa del comparador: hashes/J/NPZ de los tres métodos históricos')
    ejecutar(parser.parse_args())
