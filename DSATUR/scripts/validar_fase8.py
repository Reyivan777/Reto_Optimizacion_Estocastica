"""Pruebas, regresiones históricas y verificación independiente de fase 8."""
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


def auditar_exportaciones(out):
    out=Path(out)
    m=json.loads((out/"manifiesto.json").read_text(encoding="utf-8"))
    d=Datos(ROOT)
    from decimal import Decimal
    from fractions import Fraction
    from scipy.spatial import cKDTree
    from reforestacion.optimizacion_economica import validar_cuotas, desviacion_exacta
    tabla=pd.read_csv(out/'escenarios.csv')
    assert len(tabla)==m['solicitados'] and tabla.estado.eq('ok').all()
    assert not tabla.duplicated(['poligono','escenario']).any()
    max_error=0.
    for f in tabla.itertuples():
        z=np.load(out/f'P{f.poligono}_E{f.escenario}.npz')
        def puntuar(y):
            a,b=z['pares'].T
            return float(np.sum(z['pesos'].astype(np.longdouble)*
                z['C'][y[a],y[b]].astype(np.longdouble),dtype=np.longdouble))
        ref=puntuar(z['referencia']); j=puntuar(z['final'])
        max_error=max(max_error,abs(j-f.J_final),abs(ref-f.J_referencia))
        assert max_error<1e-8 and j<=ref+1e-8
        np.testing.assert_array_equal(z['final'][:int(z['nf'])],z['referencia'][:int(z['nf'])])
        x=np.bincount(z['final'],minlength=10)
        np.testing.assert_array_equal(x,z['x'])
        assert np.all(z['U']>=0) and np.all(z['U']<=z['limites'])
        assert not cKDTree(z['U']).query_pairs(m['config']['separacion_min']-1e-8)
        costos=d.especies.costo_unitario.to_numpy()
        area=float(d.areas.loc[f.poligono])
        B=float(Decimal(str(area))*Decimal(str(m['config']['presupuesto_por_ha'])))
        # El CSV de referencia usa multiplicación float histórica. Reconstruir
        # dinero desde datos decimales, sin convertir su ruido a precisión monetaria.
        assert abs(B-f.presupuesto_um)<1e-8
        validar_cuotas(z['R'],z['n'],x,costos,B)
        assert desviacion_exacta(x,z['R'])<=Fraction(f.limite_desviacion)
        costo=sum(Decimal(str(c))*int(q) for c,q in zip(costos,x-z['n']))
        assert abs(float(costo)-f.costo_um)<1e-8
        assert hashlib.sha256(z['final'].astype('<i8').tobytes()).hexdigest()==f.solucion_sha256
        assert hashlib.sha256(z['U'].astype('<f8').tobytes()).hexdigest()==f.sitios_sha256
    from reforestacion.monte_carlo import estadisticas
    resumen=pd.read_csv(out/'resumen_pareado.csv')
    for r in resumen.to_dict('records'):
        est=estadisticas(tabla.loc[tabla.poligono.eq(r['poligono']),'diferencia_J'].to_numpy(),m['config']['escenarios'])
        for k in ('media','error_estandar','ic_inferior','ic_superior','p05','p50','p95'):
            if est[k] is None: assert pd.isna(r[k])
            else: assert abs(est[k]-r[k])<1e-8
    return dict(soluciones_recalculadas=len(tabla),max_error_J=max_error)


def validar(out, snapshot=None):
    out = Path(out).resolve()
    env = os.environ.copy()
    temporal = ROOT/'build/tmp'; temporal.mkdir(parents=True, exist_ok=True)
    env.update(TMP=str(temporal), TEMP=str(temporal), OPENBLAS_NUM_THREADS='1',
               OMP_NUM_THREADS='1', MPLBACKEND='Agg')
    pruebas = []
    for bateria in ('modelo','economia','cpp','posiciones','monte_carlo','supervivencia','sensibilidad','mejoras'):
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
    guardar(out/'preservados_sha256.json',snap)
    auditoria=auditar_exportaciones(out)
    guardar(out/'validacion.json',dict(baterias_ok=len(pruebas),regresiones=len(registros),
        archivos_preservados_sha256=len(snap),**auditoria))
    print('Validación completa',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resultado')
    parser.add_argument('--snapshot')
    parser.add_argument('--solo-exportaciones',action='store_true')
    args=parser.parse_args()
    if args.solo_exportaciones:
        print(auditar_exportaciones(args.resultado))
    else:
        validar(args.resultado,args.snapshot)
