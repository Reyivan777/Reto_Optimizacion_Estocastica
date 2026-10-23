"""Fase 6 independiente: auditar, proyectar y simular sin alterar el optimizador."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos
from reforestacion.experimento import seleccionar_poligonos
from reforestacion.monte_carlo import estadisticas
from reforestacion.optimizacion_economica import planificar, DatosConCuotas
from reforestacion.supervivencia import Hipotesis, auditar_historico, preparar, proyectar, simular


def guardar_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def cargar_hipotesis(path):
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    if set(raw) != {'interpretacion', 'columna_historica', 'horizonte', 'hipotesis'}:
        raise ValueError('Esquema de hipótesis desconocido.')
    for k in ('interpretacion', 'horizonte'):
        if not isinstance(raw[k], str) or not raw[k].strip():
            raise ValueError('Interpretación y horizonte explícitos requeridos.')
    if raw['columna_historica'] not in ('2021', '2022', '2023'):
        raise ValueError('Columna histórica no disponible.')
    hs = [Hipotesis(**x) for x in raw['hipotesis']]
    if not hs or len({h.nombre for h in hs}) != len(hs):
        raise ValueError('Hipótesis no vacías con nombres únicos requeridas.')
    return raw, hs


def resumir(tabla, claves):
    filas = []
    for key, g in tabla.groupby(claves, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        prefijo = dict(zip(claves, key))
        for metrica in ('vivos_finales', 'deficit', 'reposiciones', 'costo_total_um', 'exceso_um'):
            filas.append(dict(**prefijo, metrica=metrica,
                **estadisticas(g[metrica].to_numpy(), len(g))))
    return pd.DataFrame(filas)


def ejecutar(args):
    if args.escenarios < 2 or args.semilla < 0:
        raise ValueError('Se requieren escenarios >=2 y semilla no negativa.')
    ids = seleccionar_poligonos('todos' if args.poligonos == 'todos'
                               else tuple(map(int, args.poligonos.split(','))))
    raw, hs = cargar_hipotesis(args.hipotesis)
    cfg = perfil('completo', poligonos=tuple(ids))
    datos = Datos(ROOT)
    auditoria = auditar_historico(datos.supervivencia, datos.S)
    p = datos.supervivencia.set_index('especie').loc[datos.S, raw['columna_historica']].to_numpy(float)/100
    planes = planificar(datos, cfg, ids) if args.modo == 'economico' else {}
    if any(x['estado'] != 'factible_economicamente' for x in planes.values()):
        raise ValueError('Hay planes no factibles; no simular una compra no validada.')
    vista = DatosConCuotas(datos, planes) if planes else datos
    entradas = {}
    proyecciones, especies = [], []
    # Validación completa antes de crear evidencia o simular.
    for pol in ids:
        a, n, R, q = vista.poligono(pol, cfg)
        B = Decimal(str(a))*Decimal(str(cfg.presupuesto_por_ha))
        costos = datos.especies.costo_unitario.to_numpy(float)
        entradas[pol] = (n, q, p, costos, B)
        for h in hs:
            preparar(*entradas[pol], h)
            detalle, resumen = proyectar(*entradas[pol], h)
            detalle.insert(0, 'especie', datos.S)
            detalle.insert(0, 'poligono', pol)
            detalle.insert(0, 'hipotesis', h.nombre)
            especies.append(detalle)
            proyecciones.append(dict(poligono=pol, hipotesis=h.nombre, **resumen))
    out = ROOT/'resultados'/('supervivencia_fase6_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(exist_ok=False)
    inicio = perf_counter()
    guardar_json(out/'auditoria_historico.json', auditoria)
    guardar_json(out/'hipotesis.json', raw)
    guardar_json(out/'planes.json', planes)
    pd.concat(especies, ignore_index=True).to_csv(out/'proyeccion_por_especie.csv', index=False)
    proy = pd.DataFrame(proyecciones)
    proy.to_csv(out/'proyeccion_por_poligono.csv', index=False)
    registros = []
    for h in hs:
        for pol in ids:
            registros.extend(simular(*entradas[pol], h, pol, i, args.semilla) for i in range(args.escenarios))
        print(f'{h.nombre}: {len(ids)*args.escenarios} realizaciones', flush=True)
    tabla = pd.DataFrame(registros)
    tabla.to_csv(out/'simulaciones.csv', index=False)
    resumen = resumir(tabla, ['hipotesis', 'poligono'])
    esperado = proy.melt(id_vars=['hipotesis','poligono'],
        value_vars=['vivos_finales_esperados','deficit_esperado','reposiciones_esperadas','costo_total_esperado_um'],
        var_name='metrica', value_name='esperanza_analitica')
    esperado['metrica'] = esperado.metrica.map(dict(vivos_finales_esperados='vivos_finales',
        deficit_esperado='deficit', reposiciones_esperadas='reposiciones', costo_total_esperado_um='costo_total_um'))
    resumen = resumen.merge(esperado, on=['hipotesis','poligono','metrica'], how='left', validate='one_to_one')
    resumen.to_csv(out/'estadisticas.csv', index=False)
    riesgo = []
    for (h, pol), g in tabla.groupby(['hipotesis','poligono'], sort=False):
        frecuencia = float((~g.cumple_presupuesto).mean())
        riesgo.append(dict(hipotesis=h, poligono=int(pol), solicitados=args.escenarios,
            validos=len(g), exceden_presupuesto=int((~g.cumple_presupuesto).sum()),
            frecuencia_exceso=frecuencia, error_estandar_mc=float(np.sqrt(frecuencia*(1-frecuencia)/len(g))),
            advertencia='Frecuencia simulada condicional; 0/1 no certifican riesgo nulo/seguro en general.'))
    pd.DataFrame(riesgo).to_csv(out/'riesgo_presupuesto.csv', index=False)
    # Cada índice tiene todos los polígonos, sin sumar escenarios entre sí.
    if tabla.duplicated(['hipotesis','poligono','escenario']).any():
        raise AssertionError('Escenarios duplicados.')
    grupos = tabla.groupby(['hipotesis','escenario'], sort=False)
    if not grupos.size().eq(len(ids)).all():
        raise AssertionError('Agregado incompleto.')
    columnas = ['vivos_finales','deficit','reposiciones','costo_total_um','exceso_um']
    agregado = grupos[columnas].sum()
    agregado['todos_cumplen_presupuesto'] = grupos.cumple_presupuesto.all()
    agregado['poligonos_completos'] = len(ids)
    agregado.reset_index().to_csv(out/'agregado_subconjunto.csv', index=False)
    resumir(agregado.reset_index(), ['hipotesis']).to_csv(out/'estadisticas_agregadas.csv', index=False)
    fuentes = (list((ROOT/'data').glob('*')) + list((ROOT/'src/reforestacion').glob('*.py'))
        + list((ROOT/'config').glob('*')) + [Path(__file__)])
    guardar_json(out/'manifiesto.json', dict(commit_base=subprocess.check_output(
        ['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        argumentos=vars(args), configuracion_base=asdict(cfg), poligonos=ids,
        escenarios_por_hipotesis_poligono=args.escenarios, semilla=args.semilla,
        rng='SeedSequence([semilla,6,poligono,indice]).spawn(4); PCG64; orden existentes/nuevas/reposición/supervivencia reposición',
        clasificacion='Observaciones: CSV; proyecciones: esperanzas; hipótesis: todos los parámetros futuros y binomiales independientes.',
        horizonte=raw['horizonte'], interpretacion=raw['interpretacion'],
        hipotesis_efectivas=[asdict(h) for h in hs],
        costos_reales_integrales_disponibles=False, moneda='u.m. no identificada',
        supuestos='Stocks y especies independientes; sin clima común ni incertidumbre de parámetros. Reposición por misma especie sin reoptimización. No garantiza ejecución de compras sin presupuesto.',
        ic='IC95% puntual de la media Monte Carlo; percentiles predictivos bajo hipótesis, no IC de supervivencia histórica.',
        python=sys.version, plataforma=platform.platform(),
        versiones={x:importlib.metadata.version(x) for x in ('numpy','pandas','scipy')},
        fuentes_sha256={str(f.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in fuentes},
        hipotesis_sha256=hashlib.sha256(Path(args.hipotesis).read_bytes()).hexdigest(),
        segundos_simulacion_y_exportacion=perf_counter()-inicio))
    print(out, flush=True)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--poligonos', default='1,13,5', help='IDs separados por coma o todos')
    parser.add_argument('--escenarios', type=int, default=1000)
    parser.add_argument('--semilla', type=int, default=20261014)
    parser.add_argument('--modo', choices=['economico','fijo'], default='economico')
    parser.add_argument('--hipotesis', default=str(ROOT/'config/escenarios_supervivencia.json'))
    ejecutar(parser.parse_args())


if __name__ == '__main__':
    main()
