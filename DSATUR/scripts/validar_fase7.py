"""Pruebas, regresiones históricas y verificación independiente de fase 7."""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos, cargar_competencia
from reforestacion.monte_carlo import realizar
from reforestacion.optimizacion_economica import planificar


def guardar(path, valor):
    path.write_text(json.dumps(valor, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def validar(out, snapshot=None):
    out = Path(out).resolve()
    env = os.environ.copy()
    temporal = ROOT/'build/tmp'; temporal.mkdir(parents=True, exist_ok=True)
    env.update(TMP=str(temporal), TEMP=str(temporal), OPENBLAS_NUM_THREADS='1',
               OMP_NUM_THREADS='1', MPLBACKEND='Agg')
    pruebas = []
    for bateria in ('modelo','economia','cpp','posiciones','monte_carlo','supervivencia','sensibilidad'):
        t = perf_counter()
        r = subprocess.run([sys.executable, str(ROOT/f'tests/verificar_{bateria}.py')],
            cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
        (out/f'pruebas_{bateria}.log').write_text(r.stdout+r.stderr, encoding='utf-8')
        pruebas.append(dict(bateria=bateria, exit_code=r.returncode, segundos=perf_counter()-t))
        guardar(out/'pruebas.json', pruebas)
        if r.returncode: raise AssertionError(f'{bateria}: {r.stderr}')
        print(f'Pruebas {bateria}: OK', flush=True)
    # Regresión contra evidencia preservada de fase 4: ambos motores y posiciones on/off.
    prev = pd.read_csv(ROOT/'resultados/comparacion_posiciones_20261023T192716_901247Z/escenarios.csv')
    cfg = perfil('completo', escenarios=12, vecindad_posiciones='mixta')
    d = Datos(ROOT); C = cargar_competencia(ROOT/'config/competencia.json', d.S)
    planes = planificar(d,cfg,[1,13,5]); registros = []
    for p in (1,13,5):
        for e in range(12):
            for motor in ('python','cpp'):
                for metodo in ('especies','mixta'):
                    conf = replace(cfg,motor=motor,optimizar_posiciones=metodo=='mixta')
                    f = realizar((p,e,d,conf,C,planes[p]))
                    old = prev.loc[(prev.poligono==p)&(prev.escenario==e)&
                        (prev.motor==motor)&(prev.metodo==metodo)].iloc[0]
                    assert f['entradas_sha256'] == old.entradas_sha256
                    assert f['solucion_sha256'] == old.solucion_sha256
                    delta = max(abs(f[k]-old[k]) for k in ('J_base','J_dsatur','J_final'))
                    assert delta <= 1e-8
                    registros.append(dict(poligono=p,escenario=e,motor=motor,metodo=metodo,
                        hashes_identicos=True,max_diferencia_J=delta))
        print(f'Regresión P{p}: OK', flush=True)
    pd.DataFrame(registros).to_csv(out/'regresion_espacial.csv',index=False)
    m=json.loads((out/'manifiesto.json').read_text(encoding='utf-8'))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in m['fuentes_sha256'].items())
    snap=json.loads(Path(snapshot).read_text(encoding='utf-8')) if snapshot else {}
    assert all(hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h for p,h in snap.items())
    if snapshot:guardar(out/'preservados_sha256.json',snap)
    matrices={k:np.array(v) for k,v in json.loads((out/'matrices.json').read_text(encoding='utf-8')).items()}
    t=pd.read_csv(out/'escenarios.csv')
    cruces=pd.read_csv(out/'evaluacion_cruzada.csv')
    resumen=pd.read_csv(out/'resumen_pareado.csv')
    assert len(t)==m['corridas_solicitadas']
    assert not t.duplicated(['poligono','escenario','motor','matriz']).any()
    # Este validador de evidencia principal exige que no haya exclusiones.
    assert t.estado.eq('ok').all()
    assert len(cruces)==len(t)*len(matrices)
    assert not cruces.duplicated(['poligono','escenario','motor','matriz_solucion','matriz_evaluadora']).any()
    assert t.groupby(['poligono','escenario','motor']).entradas_sha256.nunique().eq(1).all()
    for _,g in t.groupby(['poligono','escenario']):
        for columna in ('costo_um','total','nuevas','existentes','presupuesto_um'):
            assert g[columna].nunique()==1
    if m['argumentos']['modo']=='economico':assert t.cumple_presupuesto.all()
    equivalencias=0
    if set(t.motor)=={'python','cpp'}:
        for _,g in t.groupby(['poligono','escenario','matriz']):
            assert len(g)==2
            assert g.solucion_sha256.nunique()==1
            assert g.entradas_sha256.nunique()==1
            assert abs(g.J_final.iloc[0]-g.J_final.iloc[1])<1e-8
            equivalencias+=1
    # Recalcular cada evaluación con las masas de aristas por par de especies.
    indices=['poligono','escenario','motor','matriz']
    soluciones=t.set_index(indices)
    max_error=0.
    for f in cruces.itertuples():
        C=matrices[f.matriz_evaluadora]
        def puntuar(nombre):
            fila=soluciones.loc[(f.poligono,f.escenario,f.motor,nombre)]
            return sum(fila[f'peso_{i}_{j}']*C[i,j] for i in range(10) for j in range(i,10))
        j=puntuar(f.matriz_solucion);ref=puntuar('original')
        max_error=max(max_error,abs(j-f.J),abs(ref-f.J_referencia),abs(j-ref-f.diferencia_vs_original))
        assert max_error<1e-8
        if ref:assert abs(100*(j-ref)/ref-f.diferencia_pct)<1e-8
        else:assert pd.isna(f.diferencia_pct)
    claves=['poligono','motor','matriz_solucion','matriz_evaluadora']
    from reforestacion.monte_carlo import estadisticas
    for f in resumen.to_dict('records'):
        g=cruces
        for k in claves:g=g.loc[g[k].eq(f[k])]
        valores=g.diferencia_vs_original.to_numpy()
        est=estadisticas(valores,m['config']['escenarios'])
        for k in ('media','error_estandar','ic_inferior','ic_superior','p05','p50','p95'):
            if est[k] is None:assert pd.isna(f[k])
            else:assert abs(f[k]-est[k])<1e-8
        assert f['validos']==len(g) and f['excluidos']==0
        assert f['mejora']==sum(valores < -1e-8)
        assert f['empeora']==sum(valores > 1e-8)
    import nbformat
    viejo=nbformat.reads(subprocess.check_output(['git','show','c2c0fe4:DSATUR/modelo_reforestacion.ipynb'],
        cwd=ROOT,text=True,encoding='utf-8'),as_version=4)
    nuevo=nbformat.read(ROOT/'modelo_reforestacion.ipynb',as_version=4)
    assert nuevo.cells[:len(viejo.cells)]==viejo.cells
    nbformat.validate(nuevo)
    resultado=dict(baterias_ok=len(pruebas),regresiones=len(registros),
        archivos_preservados_sha256=len(snap),corridas=len(t),evaluaciones_cruzadas=len(cruces),
        equivalencias_motores=equivalencias,max_error_recalculo_J=max_error,
        celdas_previas_intactas=len(viejo.cells),fuentes_manifiesto_verificadas=True)
    guardar(out/'validacion.json',resultado)
    print(resultado,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resultado')
    parser.add_argument('--snapshot')
    args=parser.parse_args()
    validar(args.resultado,args.snapshot)
