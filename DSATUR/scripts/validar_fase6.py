"""Verificar una ejecución de fase 6 y regresiones; guardar evidencia nueva.

python scripts/validar_fase6.py resultados/supervivencia_fase6_FECHA
El snapshot opcional se captura ANTES del trabajo, no se regenera al validar.
"""
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
    for bateria in ('modelo','economia','cpp','posiciones','monte_carlo','supervivencia'):
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
    m = json.loads((out/'manifiesto.json').read_text(encoding='utf-8'))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in m['fuentes_sha256'].items())
    snap = json.loads(Path(snapshot).read_text(encoding='utf-8')) if snapshot else {}
    assert all(hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h for p,h in snap.items())
    if snapshot: guardar(out/'preservados_sha256.json',snap)
    t = pd.read_csv(out/'simulaciones.csv')
    proy = pd.read_csv(out/'proyeccion_por_poligono.csv')
    det = pd.read_csv(out/'proyeccion_por_especie.csv')
    est = pd.read_csv(out/'estadisticas.csv')
    hs = m['hipotesis_efectivas']; ids = m['poligonos']; nmc = m['escenarios_por_hipotesis_poligono']
    assert len(t)==len(hs)*len(ids)*nmc
    assert not t.duplicated(['hipotesis','poligono','escenario']).any()
    assert len(det)==len(hs)*len(ids)*10
    comprobaciones = 0
    raw = json.loads((out/'hipotesis.json').read_text(encoding='utf-8'))
    pbase = d.supervivencia.set_index('especie').loc[d.S,raw['columna_historica']].to_numpy()/100
    for h in hs:
        for pol in ids:
            a,n,R,q = d.poligono(pol,cfg)
            if m['argumentos']['modo']=='economico':
                pl = json.loads((out/'planes.json').read_text(encoding='utf-8'))[str(pol)]
                q = np.array(pl['compras'])
            pn = pbase*h['factor_supervivencia_nuevas']
            pr = pbase*h['factor_supervivencia_reposicion']
            pe,rho = h['supervivencia_existentes'], h['fraccion_reposicion']
            # Derivación por sitio, independiente del código de proyectar.
            esperado = (n*(pe+(1-pe)*rho*pr) + q*(pn+(1-pn)*rho*pr)).sum()
            f = proy.loc[(proy.hipotesis==h['nombre'])&(proy.poligono==pol)].iloc[0]
            np.testing.assert_allclose(f.vivos_finales_esperados,esperado,atol=1e-9,rtol=0)
            for metrica in ('vivos_finales','deficit','reposiciones','costo_total_um'):
                s = est.loc[(est.hipotesis==h['nombre'])&(est.poligono==pol)&(est.metrica==metrica)].iloc[0]
                assert s.validos==nmc and s.excluidos==0
                assert abs(s.media-s.esperanza_analitica)<=max(1e-8,6*s.error_estandar)
                comprobaciones += 1
    agg = pd.read_csv(out/'agregado_subconjunto.csv')
    g = t.groupby(['hipotesis','escenario'],sort=False)
    assert len(agg)==len(hs)*nmc and g.size().eq(len(ids)).all()
    np.testing.assert_array_equal(agg.vivos_finales,g.vivos_finales.sum())
    np.testing.assert_array_equal(agg.todos_cumplen_presupuesto,g.cumple_presupuesto.all())
    # Dinero evaluado por polígono; vidas idénticas al cambiar solo precio/presupuesto.
    seleccion = lambda nombre: t.loc[t.hipotesis.eq(nombre)].sort_values(['poligono','escenario'])
    if {h['nombre'] for h in hs} == {'referencia_transportada','mortalidad_alta',
            'mortalidad_existentes','reposicion_un_ciclo','precios_altos','presupuesto_reducido'}:
        a = seleccion('referencia_transportada')
        for nombre in ('precios_altos','presupuesto_reducido'):
            np.testing.assert_array_equal(a.vivos_finales,seleccion(nombre).vivos_finales)
        np.testing.assert_array_equal(a.muertes,seleccion('reposicion_un_ciclo').muertes)
        assert (seleccion('reposicion_un_ciclo').vivos_finales.to_numpy()>=a.vivos_finales.to_numpy()).all()
    # Verificación independiente del historial ejecutable del notebook.
    import nbformat
    viejo = nbformat.reads(subprocess.check_output(['git','show','4100608:DSATUR/modelo_reforestacion.ipynb'],
        cwd=ROOT,text=True,encoding='utf-8'),as_version=4)
    nuevo = nbformat.read(ROOT/'modelo_reforestacion.ipynb',as_version=4)
    assert nuevo.cells[:len(viejo.cells)]==viejo.cells
    nbformat.validate(nuevo)
    resultado = dict(baterias_ok=len(pruebas),regresiones=len(registros),
        max_diferencia_J=max(x['max_diferencia_J'] for x in registros),
        archivos_preservados_sha256=len(snap),realizaciones=len(t),
        comprobaciones_mc_contra_esperanza=comprobaciones,agregados_completos=len(agg),
        celdas_previas_intactas=len(viejo.cells),fuentes_manifiesto_verificadas=True)
    guardar(out/'validacion.json',resultado)
    print(resultado,flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resultado')
    parser.add_argument('--snapshot')
    args = parser.parse_args()
    validar(args.resultado,args.snapshot)
