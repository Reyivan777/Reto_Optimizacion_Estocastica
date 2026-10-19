from pathlib import Path
import json
import numpy as np
import pandas as pd
from .algoritmos import validar_C

class Datos:
    def __init__(self, root):
        root = Path(root)
        self.especies = pd.read_csv(root/'data/especies.csv')
        self.inventario = pd.read_csv(root/'data/inventario.csv')
        self.supervivencia = pd.read_csv(root/'data/supervivencia_porcentajes.csv')
        e, inv = self.especies, self.inventario
        self.S = e.especie.tolist()
        if len(e) != 10 or not e.especie.is_unique or e.isna().any().any():
            raise ValueError('Catálogo incompleto o especies duplicadas.')
        numericos = e[['objetivo_por_ha','costo_unitario']].to_numpy(float)
        if not np.isfinite(numericos).all() or (numericos < 0).any() or e.objetivo_por_ha.sum() != 658:
            raise ValueError('Metas o costos inválidos.')
        if inv.isna().any().any() or inv.duplicated(['poligono','especie']).any():
            raise ValueError('Inventario con faltantes o duplicados.')
        if len(inv) != 300 or set(inv.poligono) != set(range(1,31)):
            raise ValueError('Se requieren los 30 polígonos completos.')
        valores = inv[['existentes','area_ha']].to_numpy(float)
        if not np.isfinite(valores).all() or (inv.existentes < 0).any() or (inv.existentes % 1 != 0).any() or (inv.area_ha <= 0).any():
            raise ValueError('Conteos o superficies inválidos.')
        if not inv.groupby('poligono').area_ha.nunique().eq(1).all() or not all(set(g.especie) == set(self.S) for _,g in inv.groupby('poligono')):
            raise ValueError('Especies o áreas inconsistentes por polígono.')
        self.areas = inv.groupby('poligono').area_ha.first()

    def poligono(self, p, config):
        areas, inventario, especies, S = self.areas, self.inventario, self.especies, self.S
        if p not in areas.index:
            raise ValueError(f'Polígono {p} no disponible.')
        if config.densidad <= 0:
            raise ValueError('La densidad debe ser positiva.')
        n = inventario[inventario.poligono.eq(p)].set_index('especie').loc[S,'existentes'].to_numpy(int)
        total = int(np.floor(areas.loc[p] * config.densidad + 0.5))
        ideal = total * especies.objetivo_por_ha.to_numpy() / especies.objetivo_por_ha.sum()
        R = np.floor(ideal).astype(int)
        # Restos mayores; empates resueltos por el orden fijo de especies.
        orden = np.argsort(-(ideal-R), kind='stable')
        R[orden[:total-int(R.sum())]] += 1
        if np.any(R < n):
            raise ValueError('Inventario superior a una cuota: no se eliminan plantas ni se trunca el faltante.')
        return float(areas.loc[p]), n, R, R-n

    def resumen(self, config):
        filas = []
        for p in self.areas.index:
            a,n,R,q = self.poligono(p,config)
            filas.append(dict(poligono=int(p), area_ha=a, existentes=int(n.sum()),
                              meta_final=int(R.sum()), nuevas=int(q.sum())))
        return pd.DataFrame(filas)


def cargar_competencia(path, especies):
    """JSON explícito, orden de especies obligatorio; no se deriva dentro de DSATUR."""
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    if raw['especies'] != especies:
        raise ValueError('El orden de especies de C no coincide con el catálogo.')
    C = np.asarray(raw['matriz'], dtype=float)
    validar_C(C, len(especies))
    return C
