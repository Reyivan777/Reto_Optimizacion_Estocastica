"""Reproducir el primer casi empate de DSATUR con C y 0.5*C+0.5.

Solo diagnóstico de fase 7: replica las decisiones originales hasta divergir,
sin modificar el algoritmo ni proponer un nuevo desempate.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos, cargar_competencia
from reforestacion.experimento import ejecutar_escenario
from reforestacion.optimizacion_economica import planificar, DatosConCuotas


def diagnosticar():
    cfg=perfil('completo',escenarios=1)
    d=Datos(ROOT);C=cargar_competencia(ROOT/'config/competencia.json',d.S)
    v=DatosConCuotas(d,planificar(d,cfg,[1]))
    _,r=ejecutar_escenario(1,0,v,cfg,C)
    g=r['g'];nf=g['nf'];N=len(g['U'])
    estados=[]
    for matriz in (C,.5*C+.5):
        st=dict(C=matriz,y=np.full(N,-1,dtype=int),restante=r['q'].copy(),
                vistos=np.zeros((N,10),bool),coste=np.zeros((N,10)))
        st['y'][:nf]=r['fijas'];estados.append(st)
    def actualizar(st,i,s):
        for j,w in g['ady'][i]:
            if st['y'][j]<0:
                st['vistos'][j,s]=True
                st['coste'][j]+=w*st['C'][:,s]
    for st in estados:
        for i,s in enumerate(r['fijas']):actualizar(st,i,int(s))
    grado=np.array([sum(w for _,w in ad) for ad in g['ady']])
    for paso in range(N-nf):
        decisiones=[]
        for st in estados:
            libres=np.flatnonzero(st['y']<0)
            sat=st['vistos'][libres].sum(axis=1)
            i=int(libres[np.lexsort((libres,-grado[libres],-sat))[0]])
            factibles=np.flatnonzero(st['restante']>0)
            s=int(min(factibles,key=lambda s:(st['coste'][i,s],-st['restante'][s],s)))
            decisiones.append((i,s))
        if decisiones[0]!=decisiones[1]:
            i=decisiones[0][0];s0=decisiones[0][1];s1=decisiones[1][1]
            masa=sum(w for j,w in g['ady'][i] if estados[0]['y'][j]>=0)
            return dict(poligono=1,escenario=0,paso_primera_divergencia=paso,decisiones=decisiones,
                especies=[d.S[s0],d.S[s1]],
                cuotas_restantes=estados[0]['restante'][[s0,s1]].tolist(),
                costos_original=estados[0]['coste'][i,[s0,s1]].tolist(),
                costos_moderado=estados[1]['coste'][i,[s0,s1]].tolist(),
                costos_afin_calculados=(.5*estados[0]['coste'][i,[s0,s1]]+.5*masa).tolist(),
                interpretacion='Divergencia de la heurística en casi empate de punto flotante; no cambian preferencias matemáticas en grafo fijo. Se conserva el motor original.')
        for st,(i,s) in zip(estados,decisiones):
            st['y'][i]=s;st['restante'][s]-=1;actualizar(st,i,s)
    return dict(poligono=1,escenario=0,paso_primera_divergencia=None)


if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(diagnosticar(),ensure_ascii=False,indent=2))
