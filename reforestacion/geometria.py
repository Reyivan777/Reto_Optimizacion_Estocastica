"""Posiciones simuladas: selección geométrica previa a asignar especies."""
import numpy as np
import networkx as nx
from scipy.spatial import cKDTree

def dimensiones(area_ha, config):
    if area_ha <= 0 or config.aspecto <= 0:
        raise ValueError('Área y aspecto deben ser positivos.')
    ancho = np.sqrt(10000*area_ha*config.aspecto)
    return np.array([ancho, 10000*area_ha/ancho])

class EscenarioNoConstruido(ValueError):
    pass

def simular_existentes(n, limites, config, rng):
    d = config.separacion_min
    if d <= 0:
        raise ValueError('La separación mínima debe ser positiva.')
    puntos, cubetas = [], {}
    for _ in range(config.max_propuestas_posicion):
        if len(puntos) == int(n.sum()):
            break
        z = rng.uniform([0,0],limites)
        celda = tuple(np.floor(z/d).astype(int))
        vecinos = [j for dx in (-1,0,1) for dy in (-1,0,1)
                   for j in cubetas.get((celda[0]+dx,celda[1]+dy),[])]
        if any(np.linalg.norm(z-puntos[j]) < d for j in vecinos):
            continue
        cubetas.setdefault(celda,[]).append(len(puntos))
        puntos.append(z)
    if len(puntos) != int(n.sum()):
        raise EscenarioNoConstruido(f'Solo se generaron {len(puntos)}/{n.sum()} existentes; límite de intentos.')
    etiquetas = rng.permutation(np.repeat(np.arange(len(n)),n))
    return np.array(puntos).reshape(-1,2), etiquetas

def flujos(p, escenario, config):
    return [np.random.default_rng(s) for s in
            np.random.SeedSequence([config.semilla,p,escenario]).spawn(3)]

def candidatas(F, limites, cantidad, config):
    paso, minimo = config.paso_malla, config.separacion_min
    if paso < minimo or minimo <= 0:
        raise ValueError('El paso de la malla debe ser >= separación mínima > 0.')
    filas=[]
    for j,y in enumerate(np.arange(paso/2,limites[1],paso*np.sqrt(3)/2)):
        xs=np.arange(paso/2+(j%2)*paso/2,limites[0],paso)
        filas.extend((x,y) for x in xs)
    malla=np.array(filas).reshape(-1,2)
    dist=cKDTree(F).query(malla)[0] if len(F) else np.full(len(malla),np.inf)
    pool=malla[dist >= minimo-1e-9]
    if len(pool)<cantidad:
        raise EscenarioNoConstruido(f'Capacidad de malla {len(pool)} < demanda {cantidad}.')
    cercano=cKDTree(F).query(pool)[0] if len(F) else np.full(len(pool),np.inf)
    elegidas=[]
    for _ in range(cantidad):
        i=int(np.argmax(cercano))
        elegidas.append(i)
        cercano=np.minimum(cercano,np.linalg.norm(pool-pool[i],axis=1))
        cercano[elegidas]=-np.inf
    return pool, pool[np.array(elegidas,dtype=int)]

def construir_grafo(p, F, V, config):
    if config.radio <= 0:
        raise ValueError('Radio debe ser positivo.')
    U=np.vstack([F,V])
    pares=cKDTree(U).query_pairs(config.radio,output_type='ndarray')
    dist=np.linalg.norm(U[pares[:,0]]-U[pares[:,1]],axis=1)
    pesos=np.maximum(0,1-dist/config.radio)
    G=nx.Graph()
    G.add_nodes_from(((p,i),{'pos':tuple(z),'fija':i<len(F)}) for i,z in enumerate(U))
    G.add_weighted_edges_from(((p,int(i)),(p,int(j)),float(w)) for (i,j),w in zip(pares,pesos))
    ady=[[] for _ in U]
    for (i,j),w in zip(pares,pesos):
        ady[i].append((int(j),float(w)))
        ady[j].append((int(i),float(w)))
    return {'U':U,'pares':pares,'pesos':pesos,'G':G,'ady':ady,'nf':len(F),'p':p}
