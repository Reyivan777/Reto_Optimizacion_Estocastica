"""Auditoría reproducible del HTML recibido, leído desde Git sin restaurarlo."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reforestacion.datos import Datos
from reforestacion.config import perfil

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision',default='c175c0d')
    parser.add_argument('--extraer-plano',action='store_true')
    parser.add_argument('--salida',type=Path,help='CSV de auditoría; por defecto se distingue la revisión')
    args=parser.parse_args()
    original=subprocess.check_output(['git','show',f'{args.revision}:DSATUR/mapa_interactivo_tresbolillo.html'],cwd=ROOT.parent).decode('utf-8')
    D,_=json.JSONDecoder().raw_decode(original.split('const D=',1)[1])
    datos=Datos(ROOT);cfg=perfil('completo');filas=[]
    for r in D['summary']:
        p=r[0];area,n,R,q=datos.poligono(p,cfg)
        plantas=[z for z in D['plants'] if z[0]==p]
        hist=pd.read_csv(ROOT/f'resultados/P{p}/distribucion.csv')
        y=np.array([z[4] for z in plantas]); f=np.array([z[4] for z in plantas if z[3]])
        filas.append(dict(poligono=p,area_csv=area,area_html=r[1],area_coincide=abs(area-r[1])<1e-8,
            total_historico=len(hist),total_html=len(plantas),total_coincide=len(hist)==len(plantas),
            existentes_coinciden=np.array_equal(np.bincount(f,minlength=10),n),
            especies_coinciden=np.array_equal(np.bincount(y,minlength=10),R),
            ids_con_area_html=','.join(f'P{i}' for i,a in datos.areas.items() if abs(a-r[1])<1e-8)))
    destino=ROOT/'docs/validacion_mapa';destino.mkdir(parents=True,exist_ok=True)
    archivo=args.salida or destino/('html_recibido.csv' if args.revision=='c175c0d' else f'html_{args.revision}.csv')
    archivo.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(filas).to_csv(archivo,index=False)
    if args.extraer_plano:
        imagen=re.search(r'data:image/png;base64,([^"\s]+)',original).group(1)
        (ROOT/'visualizacion/plano_referencia.png').write_bytes(base64.b64decode(imagen))
    print(pd.DataFrame(filas).to_string(index=False))
