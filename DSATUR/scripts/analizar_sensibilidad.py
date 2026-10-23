"""Fase 7: sensibilidad pareada de matrices, sin cambiar la ejecución habitual."""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos, cargar_competencia
from reforestacion.experimento import seleccionar_poligonos
from reforestacion.monte_carlo import estadisticas
from reforestacion.motores import informacion_motor
from reforestacion.optimizacion_economica import planificar, DatosConCuotas
from reforestacion.sensibilidad import cargar_hipotesis, comparar


def guardar(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def ejecutar(args):
    ids = seleccionar_poligonos('todos' if args.poligonos=='todos' else [int(x) for x in args.poligonos.split(',')])
    motores = args.motores.split(',')
    if not motores or len(set(motores))!=len(motores) or not set(motores)<= {'python','cpp'}:
        raise ValueError('Motores: python, cpp o python,cpp sin duplicados.')
    cfg = perfil('completo',poligonos=tuple(ids),escenarios=args.escenarios,semilla=args.semilla,
        optimizar_posiciones=args.optimizar_posiciones,vecindad_posiciones='mixta')
    d = Datos(ROOT)
    C = cargar_competencia(ROOT/'config/competencia.json',d.S)
    archivo = Path(args.config).resolve()
    matrices, raw = cargar_hipotesis(archivo,d.S,C)
    total = len(ids)*cfg.escenarios*len(motores)*len(matrices)
    if total > args.max_corridas:
        raise ValueError(f'{total} corridas exceden --max-corridas={args.max_corridas}.')
    # Cargar bibliotecas antes de crear salidas; nunca fallback silencioso.
    info = {m:informacion_motor(m) for m in motores}
    planes = planificar(d,cfg,ids) if args.modo=='economico' else None
    if planes and any(p['estado']!='factible_economicamente' for p in planes.values()):
        raise ValueError('No todos los planes económicos son factibles; revisar selección.')
    vista = DatosConCuotas(d,planes) if planes else d
    out = ROOT/'resultados'/('sensibilidad_fase7_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True,exist_ok=False)
    guardar(out/'hipotesis.json',raw)
    guardar(out/'matrices.json',{k:v.tolist() for k,v in matrices.items()})
    guardar(out/'planes.json',planes)
    filas, cruces = [], []
    inicio = perf_counter()
    for p in ids:
        for e in range(cfg.escenarios):
            for motor in motores:
                f,c = comparar(p,e,vista,replace(cfg,motor=motor),matrices,planes[p] if planes else None)
                filas.extend(f); cruces.extend(c)
        print(f'P{p}: completado',flush=True)
    pd.DataFrame(filas).to_csv(out/'escenarios.csv',index=False)
    columnas = ['poligono','escenario','motor','matriz_solucion','matriz_evaluadora','J',
        'J_referencia','diferencia_vs_original','diferencia_pct',
        'fraccion_etiquetas_nuevas_distintas','posiciones_finales_iguales']
    t = pd.DataFrame(cruces,columns=columnas)
    t.to_csv(out/'evaluacion_cruzada.csv',index=False)
    resumen = []
    # Incluye denominador aun cuando todas las construcciones de un grupo fallen.
    for p in ids:
        for m in motores:
            for a in matrices:
                for b in matrices:
                    g = t.loc[(t.poligono==p)&(t.motor==m)&(t.matriz_solucion==a)&(t.matriz_evaluadora==b)]
                    valores = g.diferencia_vs_original.dropna().to_numpy(float)
                    resumen.append(dict(poligono=p,motor=m,matriz_solucion=a,matriz_evaluadora=b,
                        **estadisticas(valores,cfg.escenarios),
                        mejora=int((valores < -1e-8).sum()),empate=int((abs(valores)<=1e-8).sum()),
                        empeora=int((valores>1e-8).sum())))
    pd.DataFrame(resumen).to_csv(out/'resumen_pareado.csv',index=False)
    fuentes = [*sorted((ROOT/'src').rglob('*.py')),*sorted((ROOT/'config').glob('*')),
               *sorted((ROOT/'data').glob('*.csv')),Path(__file__)]
    guardar(out/'manifiesto.json',dict(argumentos=vars(args),config=asdict(cfg),poligonos=ids,
        motores=info,python=platform.python_version(),
        versiones={x:importlib.metadata.version(x) for x in ('numpy','pandas','scipy')},
        base_git=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        config_sha256=hashlib.sha256(archivo.read_bytes()).hexdigest(),
        fuentes_sha256={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in fuentes if p.is_file()},
        corridas_solicitadas=total,corridas_validas=sum(f['estado']=='ok' for f in filas),
        filas_cruzadas=len(t),segundos_comparacion_exportacion=perf_counter()-inicio,
        interpretacion='Hipótesis no calibradas; IC puntuales de diferencias pareadas, no incertidumbre ecológica. Sin optimalidad global ni relación J-supervivencia.'))
    print(out,flush=True)
    return out


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(ROOT/'config/sensibilidad_competencia.json'))
    parser.add_argument('--poligonos',default='1,13,5')
    parser.add_argument('--escenarios',type=int,default=12)
    parser.add_argument('--semilla',type=int,default=20261014)
    parser.add_argument('--motores',default='python')
    parser.add_argument('--modo',choices=('economico','fijo'),default='economico')
    parser.add_argument('--optimizar-posiciones',action='store_true')
    parser.add_argument('--max-corridas',type=int,default=1000)
    ejecutar(parser.parse_args())
