"""Misma DSATUR y deltas del prototipo, independientes de la matriz elegida."""
import numpy as np
from time import perf_counter

def validar_C(C, K=10):
    C = np.asarray(C, dtype=float)
    if C.shape!=(K,K) or not np.isfinite(C).all() or (C<0).any() or not np.array_equal(C,C.T):
        raise ValueError('C debe ser finita, no negativa, simétrica y de tamaño 10x10.')

def objetivo(etiquetas,g,C,desglose=False):
    if len(etiquetas)!=len(g['U']) or np.any((etiquetas<0)|(etiquetas>=len(C))):
        raise ValueError('La función objetivo requiere una asignación completa.')
    i,j=g['pares'].T
    valores=g['pesos']*C[etiquetas[i],etiquetas[j]]
    if not desglose:
        return float(valores.sum())
    ff=(i<g['nf'])&(j<g['nf'])
    vv=(i>=g['nf'])&(j>=g['nf'])
    return {'FF':float(valores[ff].sum()),'FV':float(valores[~(ff|vv)].sum()),
            'VV':float(valores[vv].sum()),'total':float(valores.sum())}

def base_aleatoria(fijas,q,rng):
    return np.r_[fijas,rng.permutation(np.repeat(np.arange(len(q)),q))]

def dsatur(fijas,q,g,C):
    validar_C(C)
    nf,N=len(fijas),len(g['U'])
    if len(q)!=len(C) or np.any(q<0) or np.any(q%1) or int(q.sum())!=N-nf:
        raise ValueError('Cuotas inválidas o incompatibles con el número de posiciones.')
    y=np.full(N,-1,dtype=int)
    y[:nf]=fijas
    restante=q.astype(int).copy()
    vistos=np.zeros((N,len(C)),dtype=bool)
    coste=np.zeros((N,len(C)))
    grado=np.array([sum(w for _,w in ad) for ad in g['ady']])
    def actualizar(i,s):
        for j,w in g['ady'][i]:
            if y[j]<0:
                vistos[j,s]=True
                coste[j]+=w*C[:,s]
    for i,s in enumerate(fijas):
        actualizar(i,int(s))
    for _ in range(N-nf):
        libres=np.flatnonzero(y<0)
        saturacion=vistos[libres].sum(axis=1)
        i=int(libres[np.lexsort((libres,-grado[libres],-saturacion))[0]])
        factibles=np.flatnonzero(restante>0)
        if not len(factibles):
            raise ValueError('No queda especie factible.')
        s=int(min(factibles,key=lambda s:(coste[i,s],-restante[s],s)))
        y[i]=s
        restante[s]-=1
        actualizar(i,s)
    assert not restante.any()
    return y

def delta_intercambio(a,b,y,g,C):
    sa,sb=int(y[a]),int(y[b])
    return sum(w*(C[sb,y[j]]-C[sa,y[j]]) for j,w in g['ady'][a] if j!=b) + sum(
        w*(C[sa,y[j]]-C[sb,y[j]]) for j,w in g['ady'][b] if j!=a)

def busqueda_local(inicial,g,C,rng,intentos):
    validar_C(C)
    if not isinstance(intentos, int) or intentos < 0:
        raise ValueError('Intentos debe ser entero no negativo.')
    inicio = perf_counter()
    iguales = evaluados = aceptados = 0
    y=inicial.copy()
    valor=objetivo(y,g,C)
    historia=[(0,valor)]
    movibles=np.arange(g['nf'],len(y))
    propuestas = intentos if len(movibles) >= 2 else 0
    for intento in range(1,propuestas+1):
        a,b=rng.choice(movibles,2,replace=False)
        if y[a]==y[b]:
            iguales += 1
            continue
        evaluados += 1
        delta=delta_intercambio(a,b,y,g,C)
        if delta < -1e-10:  # tolerancia original: descartar empates numéricos
            aceptados += 1
            y[a],y[b]=y[b],y[a]
            valor+=delta
            historia.append((intento,valor))
    assert np.isclose(valor,objetivo(y,g,C),atol=1e-7)
    final = objetivo(y,g,C)
    estadisticas = dict(propuestas=propuestas, especies_iguales=iguales,
        evaluados=evaluados, aceptados=aceptados, rechazados=evaluados-aceptados,
        J_inicial=historia[0][1], J_final=final,
        mejora_local_pct=100*(historia[0][1]-final)/historia[0][1] if historia[0][1] else 0.,
        segundos=perf_counter()-inicio)
    # Extender hasta el presupuesto permite ver la meseta final.
    if historia[-1][0] != propuestas:
        historia.append((propuestas, final))
    return y,np.array(historia),estadisticas
