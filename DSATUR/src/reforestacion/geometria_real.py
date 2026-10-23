"""Candidatas triangulares dentro de geometrías irregulares (coordenadas en m)."""
import numpy as np
from shapely.geometry import Point
from scipy.spatial import cKDTree

def candidatos_tresbolillo(poligono, cantidad, separacion=3.7, existentes=None):
    if not 3.4 <= separacion <= 4.0: raise ValueError('separacion debe estar entre 3.4 y 4.0 m')
    minx,miny,maxx,maxy=poligono.bounds; dy=separacion*np.sqrt(3)/2; pts=[]
    for j in range(int(np.floor(miny/dy))-1,int(np.ceil(maxy/dy))+2):
        y=j*dy; off=(j%2)*separacion/2
        for i in range(int(np.floor((minx-off)/separacion))-1,int(np.ceil((maxx-off)/separacion))+2):
            z=(off+i*separacion,y)
            if poligono.covers(Point(z)): pts.append(z)
    pts=np.asarray(pts,dtype=float).reshape(-1,2)
    if existentes is not None and len(pts) and len(existentes):
        pts=pts[cKDTree(np.asarray(existentes)).query(pts)[0] >= separacion-1e-8]
    if len(pts)<cantidad: raise ValueError(f'Capacidad {len(pts)} menor a demanda {cantidad}')
    if cantidad==0:return np.empty((0,2))
    chosen=[int(np.argmax(np.linalg.norm(pts-pts.mean(axis=0),axis=1)))]; d=np.linalg.norm(pts-pts[chosen[0]],axis=1)
    for _ in range(1,cantidad):
        k=int(np.argmax(d)); chosen.append(k); d=np.minimum(d,np.linalg.norm(pts-pts[k],axis=1))
    return pts[chosen]
