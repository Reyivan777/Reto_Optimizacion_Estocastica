"""Evidencia fase 2/3: 360 regresiones, 30 contornos y notebook en proceso.

Escribe pruebas temporales únicamente en build y reportes en docs/validacion_mapa.
No cambia los CSV históricos ni ejecuta los experimentos de fases 4–8.
"""
from pathlib import Path
import argparse
import json
import os
import sys
import hashlib
from dataclasses import replace
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.experimento import ejecutar_escenario,guardar_detalle_poligono
from reforestacion.mapa_interactivo import generar_mapa


def main(notebook=True, regresion=True):
    os.chdir(ROOT)
    docs=ROOT/'docs/validacion_mapa';tmp=ROOT/'build/validacion_mapa';tmp.mkdir(parents=True,exist_ok=True)
    datos=Datos(ROOT);C=cargar_competencia(ROOT/'config/competencia.json',datos.S)
    cfg=perfil('completo',motor='cpp',escenarios=12,poligonos='todos')
    if regresion:
        filas=[]
        for p in range(1,31):
            ref=pd.read_csv(ROOT/f'resultados/P{p}/monte_carlo.csv').set_index('escenario')
            for e in range(12):
                f,r=ejecutar_escenario(p,e,datos,cfg,C)
                fila=dict(poligono=p,escenario=e)
                for k in ('J_base','J_dsatur','J_final'):
                    fila[k+'_diferencia']=f[k]-ref.loc[e,k]
                    if abs(fila[k+'_diferencia'])>1e-8:raise AssertionError((p,e,k))
                if e==0:
                    h=pd.read_csv(ROOT/f'resultados/P{p}/distribucion.csv')
                    np.testing.assert_allclose(r['g']['U'],h[['x_m','y_m']],rtol=0,atol=1e-12)
                    np.testing.assert_array_equal(r['final'],h.especie.map({s:i for i,s in enumerate(datos.S)}))
                filas.append(fila)
            print(f'Histórico P{p}: 12/12',flush=True)
        pd.DataFrame(filas).to_csv(docs/'regresion_360.csv',index=False)
    aproximada=replace(cfg,geometria='aproximada',escenarios=1)
    ruta=tmp/'aproximada';res=[]
    for p in range(1,31):
        f,r=ejecutar_escenario(p,0,datos,aproximada,C)
        guardar_detalle_poligono(ruta,datos,f,r,C,graficas=False);res.append(f)
        print(f'Aproximado P{p}: ok',flush=True)
    pd.DataFrame(res).to_csv(docs/'aproximada_30.csv',index=False)
    generar_mapa(ROOT,ruta,ruta/'mapa.html',reporte=docs/'aproximada_30.json')
    if notebook:
        import nbformat
        from IPython.core.interactiveshell import InteractiveShell
        from IPython.utils.capture import capture_output
        import matplotlib
        matplotlib.use('module://matplotlib_inline.backend_inline')
        from matplotlib_inline.backend_inline import configure_inline_support
        shell=InteractiveShell.instance();configure_inline_support(shell,'inline')
        resumen=[]
        for motor,geometria in (('python','simulada'),('cpp','aproximada')):
            nb=nbformat.read(ROOT/'modelo_reforestacion.ipynb',as_version=4);nbformat.validate(nb)
            etiqueta=f'{motor}_{geometria}';primera=nb.cells[1]
            primera.source=primera.source.replace('MOTOR = "python"',f'MOTOR = "{motor}"')
            primera.source=primera.source.replace('POLIGONOS = "todos"','POLIGONOS = [1,5]')
            primera.source=primera.source.replace('GEOMETRIA_LOTE = "simulada"',f'GEOMETRIA_LOTE = "{geometria}"')
            primera.source=primera.source.replace("ROOT/'resultados'/'ejecuciones'",f"ROOT/'build/validacion_mapa/tutorial_{etiqueta}'")
            count=0
            for celda in nb.cells:
                if celda.cell_type!='code':continue
                codigo=celda.source.replace('modo=MODO, comparar=True, graficas=True,',f"modo=MODO, comparar=True, graficas=True, salida=ROOT/'build/validacion_mapa/lote_{etiqueta}',")
                with capture_output() as captured:
                    result=shell.run_cell(codigo,store_history=False)
                result.raise_error();count+=1
                print(f'Notebook {etiqueta}, celda {count}: ok',flush=True)
            resumen.append(dict(motor=motor,geometria_lote=geometria,celdas=count,errores=0,metodo='IPython en proceso; no kernel externo'))
        (docs/'notebook.json').write_text(json.dumps(resumen,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sin-notebook',action='store_true')
    parser.add_argument('--sin-regresion',action='store_true',help='Repetir solo integración, conservando evidencia histórica previa')
    args=parser.parse_args()
    main(not args.sin_notebook, not args.sin_regresion)
