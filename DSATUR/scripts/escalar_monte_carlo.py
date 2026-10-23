"""Fase 5: piloto independiente, confirmación fija y evaluación de procesos.

Desde DSATUR: python scripts/escalar_monte_carlo.py --motor cpp --workers 2
"""
import os
for _nombre in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_nombre] = '1'
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.experimento import agregar,seleccionar_poligonos
from reforestacion.optimizacion_economica import planificar
from reforestacion.motores import informacion_motor
from reforestacion.monte_carlo import filas,estadisticas,plan_muestra


def guardar_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def resumir(tabla,solicitados,confianza):
    ok = tabla.loc[tabla.estado.isin(['ok','completo'])].copy()
    if 'J_base' in ok:
        ok['reduccion_absoluta'] = ok.J_base-ok.J_final
    return [dict(metrica=k,**estadisticas(ok[k].to_numpy() if k in ok else [],solicitados,confianza))
            for k in ('J_base','J_dsatur','J_local_especies','J_final','reduccion_absoluta','mejora_pct')]


def ejecutar(args):
    ids = seleccionar_poligonos(tuple(map(int,args.poligonos.split(','))))
    if args.piloto < 2 or args.benchmark < 1:
        raise ValueError('Piloto >= 2 y benchmark >= 1 requeridos.')
    # Validar antes de crear resultados o ejecutar simulaciones.
    plan_muestra([1.,2.],args.relativo,args.absoluto,args.minimo,args.maximo,args.confianza)
    if args.workers < 1: raise ValueError('workers debe ser positivo.')
    cfg = perfil('completo',motor=args.motor,poligonos=tuple(ids),
                 escenarios=args.maximo,max_corridas=len(ids)*(args.piloto+args.maximo),
                 optimizar_posiciones=args.optimizar_posiciones,
                 vecindad_posiciones=args.vecindad_posiciones,semilla=args.semilla)
    native = informacion_motor(cfg.motor)
    datos = Datos(ROOT)
    C = cargar_competencia(ROOT/'config/competencia.json',datos.S)
    salida = ROOT/'resultados'/('monte_carlo_fase5_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    salida.mkdir(exist_ok=False)
    t0 = perf_counter()
    planes = planificar(datos,cfg,ids)
    guardar_json(salida/'planes.json',planes)
    if any(p['estado']!='factible_economicamente' for p in planes.values()):
        raise ValueError(f'Plan no factible; consultar {salida}/planes.json')
    tiempos = {}
    def correr(nombre,indices,workers):
        inicio = perf_counter(); registros = []
        tareas = ((p,e,datos,cfg,C,planes[p]) for e in indices for p in ids)
        with (salida/(nombre+'.jsonl')).open('w',encoding='utf-8') as archivo:
            for f in filas(tareas,workers):
                archivo.write(json.dumps(f)+'\n'); archivo.flush()
                registros.append(f)
                if len(registros) % (25*len(ids)) == 0:
                    print(f'{nombre}: {len(registros)} realizaciones',flush=True)
        tiempos[nombre] = perf_counter()-inicio
        tabla = pd.DataFrame(registros)
        tabla.to_csv(salida/(nombre+'.csv'),index=False)
        return tabla
    piloto = correr('piloto',range(args.piloto),args.workers)
    planes_n = {}
    for p in ids:
        grupo = piloto.loc[piloto.poligono.eq(p)]
        valores = grupo.reindex(columns=['J_final'])['J_final'].where(grupo.estado.eq('ok')).to_numpy()
        planes_n[p] = plan_muestra(valores,args.relativo,args.absoluto,args.minimo,args.maximo,args.confianza)
    n = max(x['n_confirmacion'] for x in planes_n.values())
    # Tamaño común garantiza agregados por índice pareados; no suma medias marginales.
    guardar_json(salida/'diseno.json',dict(por_poligono=planes_n,n_comun=n,
        piloto_indices=[0,args.piloto-1],confirmacion_indices=[args.piloto,args.piloto+n-1],
        confianza=args.confianza,regla='Tamaño fijado por piloto; sin parada opcional; IC finales puntuales.',
        objetivo_precision='Media J_final; tolerancia max(absoluto, relativo*abs(media piloto)).'))
    tabla = correr('confirmacion',range(args.piloto,args.piloto+n),args.workers)
    resumen = []; convergencia = []
    for p in ids:
        grupo = tabla.loc[tabla.poligono.eq(p)]
        for f in resumir(grupo,n,args.confianza):
            f['poligono'] = p
            h = f['semiancho_ic']
            f['precision_J_final_alcanzada'] = (h is not None and h<=planes_n[p]['tolerancia_absoluta']) if f['metrica']=='J_final' else None
            resumen.append(f)
        for k in sorted({min(n,x) for x in (12,30,100,300,1000,n)}):
            prefijo = grupo.loc[grupo.escenario < args.piloto+k]
            for f in resumir(prefijo,k,args.confianza):
                convergencia.append(dict(poligono=p,prefijo_solicitado=k,**f))
    pd.DataFrame(resumen).to_csv(salida/'estadisticas.csv',index=False)
    pd.DataFrame(convergencia).to_csv(salida/'convergencia.csv',index=False)
    agregado = agregar(tabla,ids)  # todos los índices incluyen una fila por polígono
    agregado.to_csv(salida/'agregado.csv',index=False)
    pd.DataFrame(resumir(agregado,n,args.confianza)).to_csv(salida/'estadisticas_agregadas.csv',index=False)
    # Benchmark separado: mismos índices del piloto; no amplía denominadores.
    indices = range(min(args.benchmark,args.piloto))
    serial = correr('benchmark_serial',indices,1)
    paralelo = correr('benchmark_paralelo',indices,max(2,args.workers))
    claves = ['poligono','escenario']
    a,b = [x.sort_values(claves).reset_index(drop=True) for x in (serial,paralelo)]
    columnas = claves+['estado','detalle','entradas_sha256','solucion_sha256','J_base','J_dsatur','J_final']
    pd.testing.assert_frame_equal(a.reindex(columns=columnas),b.reindex(columns=columnas),check_exact=True)
    guardar_json(salida/'benchmark.json',dict(escenarios_por_poligono=len(indices),poligonos=ids,
        workers_serial=1,workers_paralelo=max(2,args.workers),
        serial_s=tiempos['benchmark_serial'],paralelo_s=tiempos['benchmark_paralelo'],
        razon_serial_paralelo=tiempos['benchmark_serial']/tiempos['benchmark_paralelo'],
        hashes_y_objetivos_identicos=True,
        alcance='Una repetición; serial seguido de paralelo. Incluye arranque spawn, validación y exportación; excluye economía. No garantiza aceleración.'))
    guardar_json(salida/'manifiesto.json',dict(config=asdict(cfg),argumentos=vars(args),
        commit_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        python=sys.version,plataforma=platform.platform(),motor=native,
        versiones={p:importlib.metadata.version(p) for p in ('numpy','pandas','scipy','networkx')},
        semillas='SeedSequence([semilla,p,e]).spawn(3); posiciones [semilla,p,e,104729]; independientes de workers.',
        tiempos_s=tiempos,pared_hasta_manifiesto_s=perf_counter()-t0,
        estados=tabla.estado.value_counts().to_dict(),n_confirmacion_por_poligono=n,
        retencion='2*workers futuros; un grafo por proceso activo; solo filas escalares en padre O(P*n).',
        alcance='Inventario y compras conocidos/fijos; incertidumbre espacial simulada y búsqueda local. Rectángulos; sin mortalidad.',
        fuentes_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for sub in ('src','cpp','data','config','scripts','tests') for p in (ROOT/sub).rglob('*')
            if p.is_file() and '__pycache__' not in str(p)}))
    print(salida,flush=True)
    return salida


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--poligonos',default='1,13,5')
    p.add_argument('--motor',choices=('python','cpp'),default='python')
    p.add_argument('--workers',type=int,default=1)
    p.add_argument('--piloto',type=int,default=30)
    p.add_argument('--minimo',type=int,default=100)
    p.add_argument('--maximo',type=int,default=1000)
    p.add_argument('--relativo',type=float,default=.0025)
    p.add_argument('--absoluto',type=float,default=1.)
    p.add_argument('--confianza',type=float,default=.95)
    p.add_argument('--semilla',type=int,default=20261014)
    p.add_argument('--benchmark',type=int,default=12)
    p.add_argument('--optimizar-posiciones',action='store_true')
    p.add_argument('--vecindad-posiciones',choices=('sustituciones','mixta'),default='sustituciones')
    return p


if __name__=='__main__':
    ejecutar(parser().parse_args())
