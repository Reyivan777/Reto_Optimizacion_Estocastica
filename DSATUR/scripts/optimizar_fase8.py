"""Compara referencia y mejoras opcionales, exportando soluciones auditables."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
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
from reforestacion.datos import Datos, cargar_competencia
from reforestacion.experimento import seleccionar_poligonos, LimiteRecursos
from reforestacion.geometria import EscenarioNoConstruido
from reforestacion.mejoras import Mejoras, mejorar
from reforestacion.monte_carlo import estadisticas
from reforestacion.motores import informacion_motor
from reforestacion.optimizacion_economica import planificar


def guardar(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def ejecutar(args):
    ids = seleccionar_poligonos('todos' if args.poligonos == 'todos' else [int(p) for p in args.poligonos.split(',')])
    cfg = perfil('completo', poligonos=tuple(ids), escenarios=args.escenarios,
        semilla=args.semilla, motor=args.motor, optimizar_posiciones=args.optimizar_posiciones,
        vecindad_posiciones='mixta')
    op = Mejoras(args.reinicios, args.intentos_local, args.intentos_conjuntos, args.margen_desviacion)
    if len(ids)*cfg.escenarios*(1+op.reinicios) > args.max_corridas:
        raise ValueError('Presupuesto de construcciones/asignaciones excede --max-corridas.')
    info = informacion_motor(cfg.motor)
    datos = Datos(ROOT); C = cargar_competencia(ROOT/'config/competencia.json', datos.S)
    planes = planificar(datos, cfg, ids)
    if any(v['estado'] != 'factible_economicamente' for v in planes.values()):
        raise ValueError('La selección no tiene todos sus planes económicos factibles.')
    out = ROOT/'resultados'/('mejoras_fase8_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True, exist_ok=False)
    guardar(out/'planes_referencia.json', planes)
    filas, trazas, cuotas, distribuciones = [], [], [], []
    inicio = perf_counter()
    for p in ids:
        for e in range(cfg.escenarios):
            clave = dict(poligono=p, escenario=e)
            try:
                f, d = mejorar(p, e, datos, cfg, C, planes[p], op)
            except (EscenarioNoConstruido, LimiteRecursos) as error:
                filas.append(dict(**clave, estado='no_construido' if isinstance(error, EscenarioNoConstruido) else 'omitido', detalle=str(error)))
                continue
            filas.append(f)
            trazas.extend(dict(**clave, **t) for t in d['traza'])
            _, n, R, _ = datos.poligono(p, cfg)
            cuotas.extend(dict(**clave, especie=s, original=int(R[k]), existente=int(n[k]),
                referencia=int(d['R'][k]), final=int(d['R_final'][k]), compras=int(d['R_final'][k]-n[k])) for k, s in enumerate(datos.S))
            archivo = f'P{p}_E{e}.npz'
            np.savez_compressed(out/archivo, U=d['g']['U'], pares=d['g']['pares'], pesos=d['g']['pesos'],
                nf=d['g']['nf'], referencia=d['referencia'], final=d['final'], C=C,
                R=R, n=n, x=d['R_final'], limites=d['limites'])
            f['solucion_sha256'] = hashlib.sha256(d['final'].astype('<i8').tobytes()).hexdigest()
            f['sitios_sha256'] = hashlib.sha256(d['g']['U'].astype('<f8').tobytes()).hexdigest()
            if e == 0:
                distribuciones.extend(dict(**clave, indice=i, x_m=float(u[0]), y_m=float(u[1]),
                    existente=i<d['g']['nf'], especie=datos.S[int(y)]) for i, (u, y) in enumerate(zip(d['g']['U'], d['final'])))
        print(f'P{p}: completado', flush=True)
    tabla = pd.DataFrame(filas)
    tabla.to_csv(out/'escenarios.csv', index=False)
    pd.DataFrame(trazas).to_csv(out/'trayectorias.csv', index=False)
    pd.DataFrame(cuotas).to_csv(out/'cuotas.csv', index=False)
    pd.DataFrame(distribuciones).to_csv(out/'distribuciones_escenario0.csv', index=False)
    resumen = []
    for p in ids:
        t = tabla.loc[tabla.poligono.eq(p)&tabla.estado.eq('ok')]
        valores = t.diferencia_J.to_numpy() if len(t) else np.array([])
        resumen.append(dict(poligono=p, **estadisticas(valores, cfg.escenarios),
            mejora=int(sum(valores < -1e-8)), empate=int(sum(abs(valores) <= 1e-8)),
            empeora=int(sum(valores > 1e-8))))
    pd.DataFrame(resumen).to_csv(out/'resumen_pareado.csv', index=False)
    fuentes = [*sorted((ROOT/'src').rglob('*.py')), *sorted((ROOT/'data').glob('*.csv')),
               *sorted((ROOT/'config').glob('*')), Path(__file__)]
    guardar(out/'manifiesto.json', dict(argumentos=vars(args), config=asdict(cfg), opciones=asdict(op),
        motor=info, python=platform.python_version(), versiones={v:importlib.metadata.version(v) for v in ('numpy','scipy','pandas')},
        base_git=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        fuentes_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in fuentes if p.is_file()},
        segundos_lote=perf_counter()-inicio, solicitados=len(ids)*cfg.escenarios,
        validos=int(tabla.estado.eq('ok').sum()),
        limites='Rectángulos simulados; C heurística; búsqueda acotada sin certificado espacial. IC puntuales exploratorios de diferencias, sin relación J-supervivencia.'))
    texto = ['# Comparación fase 8', '',
        'Diferencia = J final − J de referencia; valores negativos favorecen las mejoras.',
        'La referencia se incluye entre los candidatos. El trabajo adicional tiene costo computacional.', '',
        '|Polígono|Válidos/solicitados|Diferencia media J|Mejoras|Empates|Empeora|',
        '|---|---|---|---|---|---|']
    for r in resumen:
        texto.append(f"|{r['poligono']}|{r['validos']}/{cfg.escenarios}|{r['media']}|{r['mejora']}|{r['empate']}|{r['empeora']}|")
    texto += ['', f'Margen adicional de desviación: {op.margen_desviacion}. Intentos conjuntos: {op.intentos_conjuntos}.',
        'Con composición conjunta se prioriza J dentro del límite D y presupuesto; el costo mínimo del desempate económico deja de estar garantizado.',
        'Rectángulos simulados y coeficientes heurísticos. No es una recomendación ecológica ni un óptimo global.',
        'Los NPZ permiten recalcular objetivos, cuotas, geometría y costos; CSV conserva denominadores y tiempos.']
    (out/'INFORME.md').write_text('\n'.join(texto)+'\n', encoding='utf-8')
    print(out, flush=True)
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--poligonos', default='1,13,5')
    parser.add_argument('--escenarios', type=int, default=12)
    parser.add_argument('--semilla', type=int, default=20261014)
    parser.add_argument('--motor', choices=('python','cpp'), default='python')
    parser.add_argument('--reinicios', type=int, default=3)
    parser.add_argument('--intentos-local', type=int, default=6000)
    parser.add_argument('--intentos-conjuntos', type=int, default=0)
    parser.add_argument('--margen-desviacion', default='0')
    parser.add_argument('--optimizar-posiciones', action='store_true')
    parser.add_argument('--max-corridas', type=int, default=1000)
    ejecutar(parser.parse_args())
