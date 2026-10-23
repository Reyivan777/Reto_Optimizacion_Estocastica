"""Candidatas triangulares dentro de geometrías irregulares (coordenadas en m)."""
import numpy as np
from shapely.geometry import Point
from scipy.spatial import cKDTree

def candidatos_tresbolillo(poligono, cantidad, separacion=3.7, existentes=None,
                           devolver_pool=False, separacion_existentes=None):
    if not isinstance(cantidad, (int, np.integer)) or isinstance(cantidad, bool) or cantidad < 0:
        raise ValueError('cantidad debe ser entero no negativo')
    if not poligono.is_valid or poligono.is_empty:
        raise ValueError('Polígono inválido')
    if not 3.4 <= separacion <= 4.0: raise ValueError('separacion debe estar entre 3.4 y 4.0 m')
    minx,miny,maxx,maxy=poligono.bounds; dy=separacion*np.sqrt(3)/2; pts=[]
    for j in range(int(np.floor(miny/dy))-1,int(np.ceil(maxy/dy))+2):
        y=j*dy; off=(j%2)*separacion/2
        for i in range(int(np.floor((minx-off)/separacion))-1,int(np.ceil((maxx-off)/separacion))+2):
            z=(off+i*separacion,y)
            if poligono.covers(Point(z)): pts.append(z)
    pts=np.asarray(pts,dtype=float).reshape(-1,2)
    if existentes is not None and len(pts) and len(existentes):
        pts=pts[cKDTree(np.asarray(existentes)).query(pts)[0] >= (separacion_existentes or separacion)-1e-8]
    if len(pts)<cantidad:
        from .geometria import EscenarioNoConstruido
        raise EscenarioNoConstruido(f'Capacidad {len(pts)} menor a demanda {cantidad}')
    if cantidad==0:
        vacio=np.empty((0,2))
        return (pts,vacio) if devolver_pool else vacio
    chosen=[int(np.argmax(np.linalg.norm(pts-pts.mean(axis=0),axis=1)))]; d=np.linalg.norm(pts-pts[chosen[0]],axis=1)
    d[chosen]=-np.inf
    for _ in range(1,cantidad):
        k=int(np.argmax(d)); chosen.append(k); d=np.minimum(d,np.linalg.norm(pts-pts[k],axis=1))
        d[chosen]=-np.inf
    return (pts,pts[chosen]) if devolver_pool else pts[chosen]
