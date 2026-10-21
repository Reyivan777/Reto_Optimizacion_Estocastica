"""Checked NumPy/ctypes bridge. Randomness and economic arithmetic stay in Python."""
import ctypes as ct
from functools import lru_cache
from pathlib import Path
import sys
from time import perf_counter
import numpy as np
from scipy.spatial import cKDTree
from . import algoritmos as py, geometria as geo

_I=np.ctypeslib.ndpointer(dtype=np.int64, flags='C_CONTIGUOUS')
_D=np.ctypeslib.ndpointer(dtype=np.float64, flags='C_CONTIGUOUS')

@lru_cache(maxsize=1)
def biblioteca():
    path=Path(__file__).resolve().parents[2]/'build'/('reforestacion.dll' if sys.platform=='win32' else 'libreforestacion.so')
    if not path.exists():
        raise RuntimeError('Motor C++ no compilado. Ejecute python scripts/compilar_cpp.py desde DSATUR/.')
    lib=ct.CDLL(str(path))
    lib.reforestacion_abi.restype=ct.c_int
    if lib.reforestacion_abi()!=1:
        raise RuntimeError('ABI C++ incompatible; recompilar.')
    lib.seleccionar.argtypes=[ct.c_int64,ct.c_int64,_D,_D,_I]
    lib.asignar.argtypes=[ct.c_int64,ct.c_int64,ct.c_int64,_I,_I,_D,_I,_I,_D,_D,_I]
    lib.intercambiar.argtypes=[ct.c_int64,ct.c_int64,_I,_I,_D,_D,_I,_I,_I,_D,_I]
    for name in ('seleccionar','asignar','intercambiar'):
        getattr(lib,name).restype=ct.c_int
    return lib

def _check(status):
    if status:
        raise RuntimeError(f'Fallo del núcleo C++: {status}')

def _enteros(x, nombre):
    a=np.asarray(x)
    if a.ndim!=1 or not np.isfinite(a).all() or (a%1).any() or (a<0).any() or (a>np.iinfo(np.int64).max).any():
        raise ValueError(f'{nombre}: vector entero no negativo requerido.')
    return np.ascontiguousarray(a,dtype=np.int64)

def _csr(g):
    n=len(g['U'])
    if len(g['ady'])!=n or not 0<=g['nf']<=n:
        raise ValueError('Grafo incompatible.')
    off=np.zeros(n+1,dtype=np.int64)
    adj=[]; pesos=[]
    for i,ad in enumerate(g['ady']):
        for j,w in ad:
            if not isinstance(j,(int,np.integer)):
                raise ValueError('Adyacencia inválida.')
            adj.append(j); pesos.append(w)
        off[i+1]=len(adj)
    adj=np.asarray(adj,dtype=np.int64); pesos=np.asarray(pesos,dtype=np.float64)
    if (adj<0).any() or (adj>=n).any() or not np.isfinite(pesos).all() or (pesos<0).any():
        raise ValueError('Adyacencia inválida.')
    return off,adj,pesos

def candidatas(F,limites,cantidad,config):
    if not isinstance(cantidad,(int,np.integer)) or cantidad<0:
        raise ValueError('Cantidad debe ser entero no negativo.')
    # The reference builds/filters exactly the same triangular pool, selecting zero.
    pool,_=geo.candidatas(F,limites,0,config)
    if len(pool)<cantidad:
        raise geo.EscenarioNoConstruido(f'Capacidad de malla {len(pool)} < demanda {cantidad}.')
    cerca=cKDTree(F).query(pool)[0] if len(F) else np.full(len(pool),np.inf)
    indices=np.empty(cantidad,dtype=np.int64)
    _check(biblioteca().seleccionar(len(pool),cantidad,np.ascontiguousarray(pool),np.ascontiguousarray(cerca),indices))
    return pool,pool[indices]

def dsatur(fijas,q,g,C):
    py.validar_C(C)
    C=np.ascontiguousarray(C,dtype=np.float64)
    fijas=_enteros(fijas,'Existentes'); q=_enteros(q,'Cuotas')
    n=len(g['U']); nf=len(fijas)
    if len(q)!=len(C) or nf!=g['nf'] or sum(map(int,q))!=n-nf or (fijas>=len(C)).any():
        raise ValueError('Cuotas o existentes incompatibles con el grafo.')
    off,adj,w=_csr(g); y=np.empty(n,dtype=np.int64)
    # sum(float) changed in CPython 3.12. Preserve the interpreter's exact
    # degree/ties rather than approximating its summation in another language.
    grado=np.array([sum(w for _,w in ad) for ad in g['ady']],dtype=np.float64)
    _check(biblioteca().asignar(n,nf,len(C),off,adj,w,fijas,q,C,grado,y))
    return y

def propuestas_comunes(rng,nf,n,intentos):
    """Same sequence of choice calls as reference, without a new RNG algorithm."""
    movibles=np.arange(nf,n)
    return np.asarray([rng.choice(movibles,2,replace=False) for _ in range(intentos if len(movibles)>=2 else 0)],dtype=np.int64).reshape(-1,2)

def busqueda_con_propuestas(inicial,g,C,propuestas):
    inicio=perf_counter(); py.validar_C(C)
    y=_enteros(inicial,'Asignación').copy()
    if len(y)!=len(g['U']) or (y>=len(C)).any():
        raise ValueError('Asignación inválida.')
    propuestas=np.asarray(propuestas)
    if propuestas.ndim!=2 or propuestas.shape[1]!=2 or not np.isfinite(propuestas).all() or (propuestas%1).any():
        raise ValueError('Propuestas deben tener forma (n,2) con índices enteros.')
    if (propuestas<g['nf']).any() or (propuestas>=len(y)).any() or (propuestas[:,0]==propuestas[:,1]).any():
        raise ValueError('Solo se permiten intercambios entre dos posiciones nuevas distintas.')
    propuestas=np.ascontiguousarray(propuestas,dtype=np.int64)
    off,adj,w=_csr(g); C=np.ascontiguousarray(C,dtype=np.float64)
    m=len(propuestas); pasos=np.empty(m,dtype=np.int64); deltas=np.empty(m); counts=np.empty(2,dtype=np.int64)
    valor=py.objetivo(y,g,C); h=[(0,valor)]
    _check(biblioteca().intercambiar(len(C),m,off,adj,w,C,propuestas,y,pasos,deltas,counts))
    iguales,aceptados=map(int,counts)
    for k,d in zip(pasos[:aceptados],deltas[:aceptados]):
        valor+=d; h.append((int(k),valor))
    final=py.objetivo(y,g,C)
    if not np.isclose(valor,final,rtol=0,atol=1e-7):
        raise AssertionError('Objetivo incremental inconsistente.')
    if h[-1][0]!=m: h.append((m,final))
    stats=dict(propuestas=m,especies_iguales=iguales,evaluados=m-iguales,aceptados=aceptados,
        rechazados=m-iguales-aceptados,J_inicial=h[0][1],J_final=final,
        mejora_local_pct=100*(h[0][1]-final)/h[0][1] if h[0][1] else 0.,segundos=perf_counter()-inicio)
    return y,np.array(h),stats

def busqueda_local(inicial,g,C,rng,intentos):
    py.validar_C(C)
    if not isinstance(intentos,int) or isinstance(intentos,bool) or intentos<0:
        raise ValueError('Intentos debe ser entero no negativo.')
    inicio=perf_counter()
    propuestas=propuestas_comunes(rng,g['nf'],len(inicial),intentos)
    y,h,stats=busqueda_con_propuestas(inicial,g,C,propuestas)
    stats['segundos']=perf_counter()-inicio
    return y,h,stats


def sustituir(y, estado, propuestas):
    """Internal bridge; posiciones.optimizar_posiciones validates every buffer."""
    lib=biblioteca()
    try:
        fn=lib.sustituir
    except AttributeError as error:
        raise RuntimeError('Recompilar C++ para sustituciones: python scripts/compilar_cpp.py') from error
    fn.argtypes=[ct.c_int64,ct.c_int64,ct.c_int64,_I,_I,_D,_I,_I,_D,_I,_I,_I,_I,_I,_D,_I]
    fn.restype=ct.c_int
    m=len(propuestas); pasos=np.empty(m,dtype=np.int64); deltas=np.empty(m)
    counts=np.zeros(2,dtype=np.int64)
    _check(fn(len(estado['C']),estado['nf'],m,estado['off'],estado['adj'],estado['pesos'],
        estado['bloquea'],np.ascontiguousarray(estado['validos'],dtype=np.int64),estado['C'],
        y,propuestas,estado['sitios'],estado['ocupantes'],pasos,deltas,counts))
    factibles,aceptados=map(int,counts)
    historia=[(int(k)+1,int(propuestas[k,0]),int(propuestas[k,1]),float(d))
              for k,d in zip(pasos[:aceptados],deltas[:aceptados])]
    return historia,factibles
