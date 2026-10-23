"""Geometrías métricas explícitas; nunca infiere un CRS a partir de números."""
from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np
from shapely.geometry import shape, mapping, Point
from shapely.affinity import translate
from shapely import transform


def identificador(valor):
    texto = str(valor)
    if texto.startswith('P'):
        texto = texto[1:]
    if not texto.isdigit() or not 1 <= int(texto) <= 30:
        raise ValueError(f'Identificador inválido: {valor}')
    return int(texto)


@dataclass
class TerrenoPoligonal:
    geometria: object

    def contiene(self, puntos):
        return np.array([self.geometria.covers(Point(z)) for z in puntos], dtype=bool)


def cargar_geometrias(archivo, areas, tipo='aproximada', crs_origen=None, crs_destino=None):
    """Los esquemas del plano ya usan metros locales ficticios, sin CRS terrestre.

    Datos georreferenciados requieren CRS declarado y destino proyectado en metros.
    La declaración del usuario no certifica la exactitud topográfica de los datos.
    """
    raw = json.loads(Path(archivo).read_text(encoding='utf-8'))
    proyeccion = None
    if tipo == 'georreferenciada':
        from pyproj import CRS, Transformer
        if not crs_origen or not crs_destino:
            raise ValueError('Se requieren CRS origen y destino explícitos.')
        destino = CRS(crs_destino)
        if not destino.is_projected or any(a.unit_conversion_factor != 1 for a in destino.axis_info):
            raise ValueError('El CRS destino debe ser proyectado en metros.')
        proyeccion = Transformer.from_crs(crs_origen, destino, always_xy=True).transform
    elif tipo != 'aproximada':
        raise ValueError('Tipo geométrico desconocido.')
    elif crs_origen or crs_destino:
        raise ValueError('Los esquemas aproximados no admiten un CRS terrestre.')
    resultado = {}
    for feature in raw['features']:
        prop = feature['properties']; p = identificador(prop['id'])
        if p in resultado or p not in areas:
            raise ValueError(f'ID duplicado o sin área: P{p}')
        geom = shape(feature['geometry'])
        if geom.geom_type not in ('Polygon', 'MultiPolygon') or geom.is_empty or not geom.is_valid:
            raise ValueError(f'Geometría inválida P{p}')
        if tipo == 'georreferenciada' and prop.get('aproximado'):
            raise ValueError('Un esquema aproximado no se puede declarar georreferenciado.')
        if proyeccion:
            geom = transform(geom, proyeccion, interleaved=False)
        if not np.isfinite(geom.bounds).all():
            raise ValueError(f'Coordenadas no finitas P{p}')
        # No reescalar un levantamiento real para ocultar discrepancias de superficie.
        if not np.isclose(geom.area / 10000, areas[p], rtol=1e-6, atol=1e-8):
            raise ValueError(f'Área geométrica no coincide con el modelo P{p}')
        if 'area_ha' in prop and not np.isclose(prop['area_ha'], areas[p], rtol=0, atol=1e-8):
            raise ValueError(f'Área declarada inconsistente P{p}')
        resultado[p] = geom
    return resultado


def construir_espacio(p, area, n, cantidad, datos, config, rng):
    """Construcción opcional; existentes medidos nunca se desplazan para caber."""
    import pandas as pd
    from scipy.spatial import cKDTree
    from .geometria import EscenarioNoConstruido
    from .geometria_real import candidatos_tresbolillo
    archivo = Path(config.archivo_geometrias) if config.archivo_geometrias else datos.root/'data/poligonos_aproximados.geojson'
    geometria = cargar_geometrias(archivo, datos.areas.to_dict(), config.geometria,
                                  config.crs_origen, config.crs_destino)[p]
    origen = np.asarray(geometria.bounds[:2])
    local = translate(geometria, xoff=-origen[0], yoff=-origen[1])
    terreno = TerrenoPoligonal(local); limites = np.asarray(local.bounds[2:])
    if config.archivo_existentes:
        tabla = pd.read_csv(config.archivo_existentes)
        tabla = tabla.loc[tabla.poligono.eq(p)].copy()
        F = tabla[['x_m', 'y_m']].to_numpy(float) - origen
        fijas = tabla.especie.map({s:i for i,s in enumerate(datos.S)})
        if fijas.isna().any():
            raise ValueError('Especies existentes desconocidas.')
        fijas = fijas.to_numpy(int)
        if not np.array_equal(np.bincount(fijas, minlength=len(n)), n):
            raise ValueError(f'Inventario medido distinto del catálogo P{p}')
    else:
        if config.geometria == 'georreferenciada' and n.sum():
            raise ValueError('Se requieren posiciones existentes medidas para geometría georreferenciada.')
        puntos = []
        # Coordenadas sintéticas explícitas; se conserva el inventario, no se afirma medición.
        for _ in range(config.max_propuestas_posicion):
            if len(puntos) == n.sum():
                break
            z = rng.uniform([0, 0], limites)
            if terreno.contiene([z])[0] and (not puntos or np.min(np.linalg.norm(np.asarray(puntos)-z, axis=1)) >= config.separacion_min):
                puntos.append(z)
        if len(puntos) != n.sum():
            raise EscenarioNoConstruido('No se construyeron todas las existentes simuladas.')
        F = np.asarray(puntos).reshape(-1, 2)
        fijas = rng.permutation(np.repeat(np.arange(len(n)), n))
    if not np.isfinite(F).all() or not terreno.contiene(F).all() or cKDTree(F).query_pairs(config.separacion_min-1e-8):
        raise ValueError('Existentes fuera del terreno o sin separación mínima; no se mueven.')
    pool, V = candidatos_tresbolillo(local, cantidad, config.paso_malla, F, devolver_pool=True,
                                     separacion_existentes=config.separacion_min)
    metadatos = dict(tipo=config.geometria, origen_m=origen.tolist(), geometria=mapping(local),
                     archivo=str(archivo.name), crs_origen=config.crs_origen, crs_destino=config.crs_destino,
                     existentes='aportadas' if config.archivo_existentes else 'simuladas')
    return F, fijas, pool, V, terreno, limites, metadatos
