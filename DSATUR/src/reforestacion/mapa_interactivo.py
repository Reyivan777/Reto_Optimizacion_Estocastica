"""Carga por ID, auditoría y HTML autónomo reproducible; no ejecuta el optimizador."""
from pathlib import Path
import hashlib
import json
from dataclasses import fields
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import shape, box, mapping
from .config import Config, perfil
from .datos import Datos, cargar_competencia
from .experimento import seleccionar_poligonos
from .geometria import construir_grafo
from .algoritmos import objetivo, validar_C
from .terrenos import cargar_geometrias, TerrenoPoligonal


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def leer_distribucion(path, especies):
    t = pd.read_csv(path)
    requeridas = {'indice','x_m','y_m','existente','especie'}
    if not requeridas.issubset(t) or t[list(requeridas)].isna().any().any():
        raise ValueError('Distribución incompleta')
    if not np.array_equal(t.indice.to_numpy(), np.arange(len(t))):
        raise ValueError('Índices deben ser únicos y consecutivos en orden')
    if not t.existente.isin([True,False]).all():
        raise ValueError('Indicadores de existentes inválidos')
    f = t.existente.to_numpy(bool)
    if not np.array_equal(f, np.arange(len(t)) < f.sum()):
        raise ValueError('Las existentes deben preceder a las nuevas')
    U = t[['x_m','y_m']].to_numpy(float)
    y = t.especie.map({s:i for i,s in enumerate(especies)})
    if y.isna().any() or not np.isfinite(U).all():
        raise ValueError('Especies desconocidas o coordenadas no finitas')
    return U, y.to_numpy(int), int(f.sum())


def construir_datos(root, resultados, ids=None):
    root, resultados = Path(root).resolve(), Path(resultados).resolve()
    datos = Datos(root)
    ids = seleccionar_poligonos('todos' if ids is None else ids)
    entrada = pd.read_csv(root/'data/poligonos_aproximados.csv')
    if entrada.id.duplicated().any() or set(entrada.id) != set(range(1,31)):
        raise ValueError('El CSV geométrico requiere P1–P30 una vez cada uno')
    areas = datos.areas.to_dict()
    aproximadas = cargar_geometrias(root/'data/poligonos_aproximados.geojson', areas)
    if set(aproximadas) != set(range(1,31)):
        raise ValueError('GeoJSON aproximado incompleto')
    historico = resultados == root/'resultados'
    confpath = resultados/'configuracion.json'
    if historico:
        confpath = resultados/'modelo_completo/configuracion.json'
    globales = json.loads(confpath.read_text(encoding='utf-8')) if confpath.exists() else {}
    salida = dict(version=1, especies=datos.S, poligonos={},
        nota='Coordenadas métricas del resultado original. Vista global en paneles independientes, sin ubicación geográfica.',
        fuentes={f'data/{p.name}':sha(p) for p in sorted((root/'data').iterdir()) if p.is_file()})
    reporte = []
    for p in sorted(ids):
        fila = dict(poligono=p, comprobaciones={}, detalle='')
        checks = fila['comprobaciones']
        def comprobar(nombre, condicion):
            checks[nombre] = 'pasa' if bool(condicion) else 'falla'
        ruta = resultados/f'P{p}'
        try:
            meta = json.loads((ruta/'metadatos.json').read_text(encoding='utf-8')) if (ruta/'metadatos.json').exists() else {}
            rawcfg = meta.get('config') or globales.get('config')
            if rawcfg is None:
                raise ValueError('Falta configuración de procedencia; no se infieren parámetros')
            cfg = Config(**{k:v for k,v in rawcfg.items() if k in {f.name for f in fields(Config)}})
            C = np.asarray(meta.get('matriz_C',globales.get('matriz_C')),float)
            validar_C(C)
            orden = meta.get('orden_especies',globales.get('orden_especies',datos.S if historico else None))
            comprobar('orden_especies_C', orden == datos.S)
            area, n, R, q = datos.poligono(p,cfg)
            # Cuotas económicas de ESTA ejecución, nunca de la última carpeta encontrada.
            cuotaspath = resultados/'cuotas.csv'
            if cuotaspath.exists():
                cuotas = pd.read_csv(cuotaspath)
                cuotas = cuotas.loc[cuotas.poligono.eq(p)]
                if cuotas.especie.duplicated().any() or set(cuotas.especie) != set(datos.S):
                    raise ValueError('Cuotas incompletas/duplicadas')
                cuotas = cuotas.set_index('especie').loc[datos.S]
                from .optimizacion_economica import validar_cuotas
                valores=cuotas[['R_original','R_ajustada','existentes','compras']].to_numpy(float)
                if not np.isfinite(valores).all() or (valores%1).any() or (valores<0).any():
                    raise ValueError('Cuotas exportadas deben ser enteras no negativas')
                comprobar('cuotas_originales',np.array_equal(cuotas.R_original,R))
                R = cuotas.R_ajustada.to_numpy(int)
                if globales.get('modo') == 'economico':
                    validar_cuotas(cuotas.R_original.to_numpy(int),n,R,
                                   datos.especies.costo_unitario.to_numpy(),area*cfg.presupuesto_por_ha)
                comprobar('cuotas_exportadas', np.array_equal(cuotas.existentes,n) and np.array_equal(cuotas.compras,R-n))
            U,y,nf = leer_distribucion(ruta/'distribucion.csv',datos.S)
            comprobar('identificador', meta.get('poligono',p) == p)
            comprobar('area_csv_inventario', abs(float(entrada.set_index('id').loc[p,'area_ha'])-area)<1e-8)
            if 'area_ha' in meta:
                comprobar('area_metadatos', abs(meta['area_ha']-area)<1e-8)
            else:
                checks['area_metadatos']='no_disponible'
            comprobar('total', len(y) == R.sum())
            comprobar('por_especie', np.array_equal(np.bincount(y,minlength=10), R))
            comprobar('existentes_por_especie', np.array_equal(np.bincount(y[:nf],minlength=10), n))
            comprobar('nuevas_por_especie', np.array_equal(np.bincount(y[nf:],minlength=10), R-n))
            info = meta.get('geometria')
            if not info:
                if cfg.geometria != 'simulada':
                    raise ValueError('Falta geometría utilizada en esta ejecución')
                from .geometria import dimensiones
                ancho,alto = dimensiones(area,cfg)
                info = dict(tipo='simulada',existentes='simuladas',origen_m=[0,0],geometria=mapping(box(0,0,ancho,alto)))
            geom = shape(info['geometria'])
            comprobar('geometria_valida',geom.is_valid and not geom.is_empty and np.isclose(geom.area/10000,area))
            comprobar('dentro_limites',TerrenoPoligonal(geom).contiene(U).all())
            minimo = float(cKDTree(U).query(U,k=2)[0][:,1].min()) if len(U)>1 else None
            comprobar('separacion_minima', minimo is None or minimo >= cfg.separacion_min-1e-8)
            comprobar('coordenadas_unicas',len(np.unique(U,axis=0)) == len(U))
            g = construir_grafo(p,U[:nf],U[nf:],cfg)
            calculado = objetivo(y,g,C,True)
            comp = pd.read_csv(ruta/'comparacion.csv')
            if comp.metodo.duplicated().any() or comp.empty:
                raise ValueError('Métricas duplicadas/vacías')
            final = comp.iloc[-1]
            comprobar('competencia_final',all(abs(float(final[k])-v)<1e-7 for k,v in calculado.items()) and abs(float(final.J)-calculado['total'])<1e-7)
            comprobar('escenario_metricas',comp.escenario.eq(meta.get('escenario',0)).all())
            costo = float((R-n)@datos.especies.costo_unitario.to_numpy())
            comprobar('costo_presupuesto',np.allclose(comp.costo_um,costo,rtol=0,atol=1e-7) and np.allclose(comp.presupuesto_um,area*cfg.presupuesto_por_ha,rtol=0,atol=1e-7))
            mcpath = ruta/'monte_carlo.csv'
            if mcpath.exists():
                mc = pd.read_csv(mcpath)
                m = mc.loc[mc.escenario.eq(meta.get('escenario',0))]
                comprobar('metricas_csv',len(m)==1 and m.poligono.eq(p).all() and m.estado.eq('ok').all() and abs(float(m.iloc[0].J_final)-calculado['total'])<1e-7 and int(m.iloc[0].total)==len(y)
                    and int(m.iloc[0].existentes)==nf and int(m.iloc[0].nuevas)==len(y)-nf
                    and all(abs(float(m.iloc[0][col])-float(comp.loc[comp.metodo.eq(metodo),'J'].iloc[0]))<1e-7
                        for col,metodo in [('J_base','Aleatoria'),('J_dsatur','DSATUR')]))
            else:
                checks['metricas_csv'] = 'no_disponible'
            inicial = None
            if (ruta/'distribucion_inicial.csv').exists():
                Ui,yi,nfi = leer_distribucion(ruta/'distribucion_inicial.csv',datos.S)
                comprobar('inicial_cuotas', nfi==nf and np.array_equal(np.bincount(yi,minlength=10),R))
                comprobar('existentes_inmutables',np.array_equal(Ui[:nf],U[:nf]) and np.array_equal(yi[:nf],y[:nf]))
                gi = construir_grafo(p,Ui[:nf],Ui[nf:],cfg)
                comprobar('inicial_espacial',TerrenoPoligonal(geom).contiene(Ui).all() and not cKDTree(Ui).query_pairs(cfg.separacion_min-1e-8))
                base = comp.loc[comp.metodo.eq('Aleatoria')]
                comprobar('competencia_inicial',len(base)==1 and abs(float(base.iloc[0].J)-objetivo(yi,gi,C))<1e-7)
                ti=pd.read_csv(ruta/'distribucion_inicial.csv')
                if 'especie_dsatur' in ti:
                    yd=ti.especie_dsatur.map({s:i for i,s in enumerate(datos.S)})
                    ds=comp.loc[comp.metodo.eq('DSATUR')]
                    comprobar('competencia_dsatur',not yd.isna().any() and len(ds)==1 and
                        np.array_equal(np.bincount(yd.to_numpy(int),minlength=10),R) and
                        abs(float(ds.iloc[0].J)-objetivo(yd.to_numpy(int),gi,C))<1e-7)
                else:
                    checks['competencia_dsatur']='no_disponible'
                inicial = np.c_[Ui,yi].tolist()
            else:
                checks['existentes_inmutables'] = checks['competencia_inicial'] = 'no_disponible'
                checks['competencia_dsatur']='no_disponible'
            fuentes = {n:sha(ruta/n) for n in ('distribucion.csv','comparacion.csv','metadatos.json','distribucion_inicial.csv','monte_carlo.csv') if (ruta/n).exists()}
            if meta.get('archivos_sha256'):
                comprobar('integridad_exportacion',all(fuentes.get(n)==h for n,h in meta['archivos_sha256'].items()))
            else:
                checks['integridad_exportacion']='no_disponible'
            ref = root/f'resultados/P{p}/distribucion.csv'
            fila.update(area_ha=area,total=len(y),existentes=nf,nuevas=len(y)-nf,
                geometria_utilizada=info['tipo'],limites_m=list(geom.bounds),origen_m=info['origen_m'],
                dimensiones_m=[geom.bounds[2]-geom.bounds[0],geom.bounds[3]-geom.bounds[1]],
                superficie_geometrica_ha=geom.area/10000,
                separacion_observada_m=minimo,especies_finales=np.bincount(y,minlength=10).tolist(),
                existentes_especies=np.bincount(y[:nf],minlength=10).tolist(),
                referencia_historica_sha256=sha(ref),fuentes_sha256=fuentes,
                coordenadas_iguales_historico=sha(ref)==fuentes['distribucion.csv'])
            salida['poligonos'][f'P{p}'] = dict(id=p,area_ha=area,nf=nf,total=len(y),
                puntos=np.c_[U,y].tolist(),inicial=inicial,geometria=info,limites=list(geom.bounds),
                conteos=np.bincount(y,minlength=10).tolist(),existentes=np.bincount(y[:nf],minlength=10).tolist(),
                competencia={str(r.metodo):float(r.J) for r in comp.itertuples()},
                desglose=calculado,matriz_C=C.tolist(),semilla=cfg.semilla,
                escenario=meta.get('escenario',0),motor=meta.get('motor',globales.get('motor',{})),
                separacion_min=cfg.separacion_min,fuentes_sha256=fuentes)
        except (ValueError,KeyError,TypeError,IndexError,OSError) as error:
            checks['lectura'] = 'falla'; fila['detalle'] = f'{type(error).__name__}: {error}'
        fila['estado'] = 'falla' if 'falla' in checks.values() else 'pasa'
        reporte.append(fila)
    return salida,reporte


def generar_mapa(root, resultados, salida, ids=None, reporte=None):
    """Mismos bytes con las mismas entradas y plantilla; no incluye hora ni rutas absolutas."""
    root, salida = Path(root),Path(salida)
    datos, filas = construir_datos(root,resultados,ids)
    reporte = Path(reporte) if reporte else salida.with_suffix('.validacion.json')
    reporte.parent.mkdir(parents=True,exist_ok=True)
    reporte.write_text(json.dumps(filas,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    pd.json_normalize(filas,sep='.').to_csv(reporte.with_suffix('.csv'),index=False)
    if any(f['estado']=='falla' for f in filas):
        # Una salida designada para regeneración no debe conservar el mapa anterior como si fuera actual.
        salida.unlink(missing_ok=True)
        raise ValueError(f'Validación fallida; mapa no generado. Revisar {reporte}')
    assets = root/'visualizacion'
    plantilla = (assets/'mapa.html').read_text(encoding='utf-8')
    contenido = plantilla.replace('/*__ESTILO__*/',(assets/'mapa.css').read_text(encoding='utf-8'))
    contenido = contenido.replace('/*__LOGICA__*/',(assets/'mapa.js').read_text(encoding='utf-8'))
    payload = json.dumps(datos,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    contenido = contenido.replace('__DATOS__',payload)
    salida.parent.mkdir(parents=True,exist_ok=True)
    salida.write_text(contenido,encoding='utf-8',newline='\n')
    return salida
