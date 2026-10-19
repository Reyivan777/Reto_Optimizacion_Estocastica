import numpy as np
from scipy.spatial import cKDTree

def validar_solucion(y,g,fijas,n,R,limites,config):
    K=len(n)
    U=g['U']
    assert y.shape==(len(U),) and np.all((y>=0)&(y<K))
    assert np.array_equal(y[:len(fijas)],fijas)
    assert np.array_equal(np.bincount(y[:len(fijas)],minlength=K),n)
    assert np.array_equal(np.bincount(y,minlength=K),R)
    assert len(U)==int(R.sum())
    assert np.all(U>=0) and np.all(U<=limites)
    assert len(np.unique(U,axis=0))==len(U)
    assert len(cKDTree(U).query_pairs(config.separacion_min-1e-8))==0
    assert len(set(g['G'].nodes))==len(U)
    return True
