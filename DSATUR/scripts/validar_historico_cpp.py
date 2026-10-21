"""Validate all 360 historical rows without overwriting any reference."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import sys
from time import perf_counter
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.experimento import ejecutar_escenario
from reforestacion.motores import informacion_motor

def main():
    ruta=ROOT/'resultados'/('validacion_cpp_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    ruta.mkdir(exist_ok=False)
    # Protect every tracked historical result, not just the three indices.
    paths=[p for p in (ROOT/'resultados').rglob('*') if p.is_file() and ruta not in p.parents and 'benchmarks' not in p.parts]
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    d=Datos(ROOT); cfg=perfil('completo',motor='cpp',escenarios=12,poligonos='todos')
    C=cargar_competencia(ROOT/'config/competencia.json',d.S);rows=[];diffs={k:0. for k in ('J_base','J_dsatur','J_final')}
    t=perf_counter()
    for p in range(1,31):
        ref=pd.read_csv(ROOT/f'resultados/P{p}/monte_carlo.csv').set_index('escenario')
        for e in range(12):
            f,r=ejecutar_escenario(p,e,d,cfg,C)
            for k in diffs:
                diffs[k]=max(diffs[k],abs(f[k]-ref.loc[e,k]))
                if abs(f[k]-ref.loc[e,k])>1e-8: raise AssertionError((p,e,k,f[k],ref.loc[e,k]))
            rows.append(f);del r
        print(f'P{p}: 12/12',flush=True)
    elapsed=perf_counter()-t
    pd.DataFrame(rows).to_csv(ruta/'regresion_360.csv',index=False)
    for rel,digest in before.items():
        if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest:raise AssertionError(f'Histórico alterado: {rel}')
    result=dict(corridas=len(rows),tolerancia_J=1e-8,max_diferencias=diffs,seg_pared=elapsed,
        archivos_historicos_preservados=len(before),historia_sha256=before,motor=informacion_motor('cpp'))
    (ruta/'validacion.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(ruta,flush=True)

if __name__=='__main__':main()
