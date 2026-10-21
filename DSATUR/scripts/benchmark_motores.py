"""Serial, fresh-process paired benchmarks; streaming scenarios, bounded memory.

Run from DSATUR: python scripts/benchmark_motores.py --progresivo
10000 means ONE polygon, not 30*10000. Budget governs scheduling only.
"""
import argparse
from dataclasses import asdict
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
import ctypes as ct

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))

def memoria():
    """Process resident high-water mark, includes Python and native allocations."""
    if sys.platform=='win32':
        from ctypes import wintypes as w
        class Counters(ct.Structure):
            _fields_=[('cb',w.DWORD),('PageFaultCount',w.DWORD)]+[(s,ct.c_size_t) for s in
                ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
                 'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        c=Counters();c.cb=ct.sizeof(c)
        kernel=ct.WinDLL('kernel32'); kernel.GetCurrentProcess.restype=w.HANDLE
        psapi=ct.WinDLL('psapi'); psapi.GetProcessMemoryInfo.argtypes=[w.HANDLE,ct.POINTER(Counters),w.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ct.byref(c),c.cb): raise ct.WinError()
        return dict(rss_bytes=c.WorkingSetSize,peak_rss_bytes=c.PeakWorkingSetSize)
    import resource
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return dict(rss_bytes=None,peak_rss_bytes=int(peak*(1 if sys.platform=='darwin' else 1024)))

def worker(args):
    import numpy as np
    import pandas as pd
    from reforestacion.config import perfil
    from reforestacion.datos import Datos,cargar_competencia
    from reforestacion.experimento import ejecutar_escenario
    from reforestacion.motores import informacion_motor
    datos=Datos(ROOT);cfg=perfil('completo',poligonos=(args.poligono,),escenarios=args.escenarios,
        max_corridas=max(360,args.escenarios),motor=args.motor)
    C=cargar_competencia(ROOT/'config/competencia.json',datos.S)
    native=informacion_motor(args.motor)  # Load library before measured workload.
    folder=Path(args.salida);folder.mkdir(parents=True,exist_ok=False)
    historical=pd.read_csv(ROOT/f'resultados/P{args.poligono}/monte_carlo.csv').set_index('escenario')
    ins=hashlib.sha256(); outs=hashlib.sha256(); maxdiff=0.; stages={}
    mem0=memoria();t0=perf_counter();export=0.
    with (folder/'escenarios.jsonl').open('w',encoding='utf-8') as stream:
        for e in range(args.escenarios):
            f,r=ejecutar_escenario(args.poligono,e,datos,cfg,C)
            for arr in (r['g']['U'],r['fijas'],r['q']): ins.update(np.ascontiguousarray(arr).tobytes())
            for key in ('dsatur','final'): outs.update(np.ascontiguousarray(r[key],dtype=np.int64).tobytes())
            if e in historical.index:
                diff=max(abs(f[k]-historical.loc[e,k]) for k in ('J_base','J_dsatur','J_final'))
                maxdiff=max(maxdiff,diff)
                if diff>1e-8: raise AssertionError(f'Regresión P{args.poligono} e{e}: {diff}')
            t=perf_counter()
            # Measure real disk CSV export, retaining only the latest distribution.
            pd.DataFrame(dict(x=r['g']['U'][:,0],y=r['g']['U'][:,1],especie=r['final'])).to_csv(folder/'ultima_distribucion.csv',index=False)
            f['seg_exportacion']=perf_counter()-t;export+=f['seg_exportacion']
            f.update(memoria());stream.write(json.dumps(f)+'\n');stream.flush()
            for k,v in f.items():
                if k.startswith('seg_'):stages[k]=stages.get(k,0.)+v
            del r
    elapsed=perf_counter()-t0
    summary=dict(motor=args.motor,poligono=args.poligono,escenarios=args.escenarios,config=asdict(cfg),
        pared_s=elapsed,etapas_acumuladas_s=stages,memoria_inicial=mem0,memoria_final=memoria(),
        entradas_sha256=ins.hexdigest(),asignaciones_sha256=outs.hexdigest(),max_diferencia_historica=maxdiff,
        retencion='Solo una distribución; filas JSONL en disco; no se acumulan grafos',motor_info=native)
    (folder/'resumen.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')

def main(args):
    folder=ROOT/'resultados/benchmarks'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    folder.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    tasks=[(p,n) for n in (1,12) for p in (1,13,5)] if args.progresivo else [(args.poligono,args.escenarios)]
    if args.progresivo:tasks.extend((1,n) for n in (100,1000,10000))
    results=[];skips=[];start=perf_counter();last_p1=None
    for p,n in tasks:
        if n>=1000 and last_p1:
            estimated=sum(x['pared_s'] for x in last_p1)*n/last_p1[0]['escenarios']
            if estimated>args.presupuesto_segundos-(perf_counter()-start):
                skips.append(dict(poligono=p,escenarios=n,motivo='Presupuesto de pared restante insuficiente',
                    estimacion_solo_para_programar_s=estimated));continue
        pair=[]
        for engine in ('python','cpp'):
            dest=folder/f'P{p}_{n}_{engine}'
            subprocess.run([sys.executable,__file__,'--worker','--motor',engine,'--poligono',str(p),
                '--escenarios',str(n),'--salida',str(dest)],check=True,env=env)
            pair.append(json.loads((dest/'resumen.json').read_text(encoding='utf-8')))
        if pair[0]['entradas_sha256']!=pair[1]['entradas_sha256'] or pair[0]['asignaciones_sha256']!=pair[1]['asignaciones_sha256']:
            raise AssertionError(f'Motores difieren: P{p}, {n}')
        results.append(dict(poligono=p,escenarios=n,python_s=pair[0]['pared_s'],cpp_s=pair[1]['pared_s'],
            aceleracion=pair[0]['pared_s']/pair[1]['pared_s'],entradas_y_asignaciones_identicas=True,
            python_peak_rss=pair[0]['memoria_final']['peak_rss_bytes'],cpp_peak_rss=pair[1]['memoria_final']['peak_rss_bytes']))
        if p==1:last_p1=pair
        print(json.dumps(results[-1]),flush=True)
        (folder/'comparacion.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    manifest=dict(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        plataforma=platform.platform(),cpu=platform.processor(),python=sys.version,
        versiones={p:importlib.metadata.version(p) for p in ('numpy','scipy','pandas','networkx')},
        hilos=1,presupuesto_pared_s=args.presupuesto_segundos,omitidos=skips,
        alcance='Cada grupo es un solo polígono; 10000 NO son 10000 por cada uno de los 30.',
        fuentes_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for sub in ('src','cpp','data','config','scripts') for p in (ROOT/sub).rglob('*') if p.is_file() and '__pycache__' not in str(p)},
        pared_orquestacion_s=perf_counter()-start)
    (folder/'manifiesto.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(folder,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--progresivo',action='store_true')
    parser.add_argument('--motor',choices=['python','cpp'],default='python')
    parser.add_argument('--poligono',type=int,default=1);parser.add_argument('--escenarios',type=int,default=1)
    parser.add_argument('--salida');parser.add_argument('--presupuesto-segundos',type=float,default=600.)
    args=parser.parse_args()
    if args.escenarios<1:parser.error('escenarios debe ser positivo')
    worker(args) if args.worker else main(args)
