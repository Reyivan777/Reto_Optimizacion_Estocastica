"""Fase 6: proyecciones condicionales, sin vínculo entre J y supervivencia.

Los porcentajes históricos no permiten estimar denominadores ni calibrar
dependencia. Binomiales independientes son una hipótesis, no un ajuste.
"""
from dataclasses import dataclass
from decimal import Decimal
import numbers
import numpy as np
import pandas as pd


def auditar_historico(tabla, especies):
    """Contrato estricto del CSV; devuelve observaciones, nunca probabilidades ajustadas."""
    columnas = ['especie', '2021', '2022', '2023']
    if list(tabla.columns) != columnas:
        raise ValueError('Esquema histórico esperado: especie,2021,2022,2023.')
    if (tabla.isna().any().any() or tabla.especie.duplicated().any()
            or len(tabla) != len(especies) or set(tabla.especie) != set(especies)):
        raise ValueError('Histórico incompleto, duplicado o con especies desconocidas.')
    try:
        x = tabla.set_index('especie').loc[especies, columnas[1:]].to_numpy(float)
    except (TypeError, ValueError) as error:
        raise ValueError('Porcentajes deben ser numéricos.') from error
    if not np.isfinite(x).all() or (x < 0).any() or (x > 100).any():
        raise ValueError('Porcentajes finitos en [0,100] requeridos.')
    return dict(filas=len(tabla), columnas=columnas, faltantes=0, duplicados=0,
                especies_completas=True, minimo_pct=float(x.min()), maximo_pct=float(x.max()),
                base_2021_100=bool((x[:, 0] == 100).all()),
                especies_con_aumento=int((np.diff(x, axis=1) > 0).any(axis=1).sum()),
                ultimo_periodo_observado=2023, denominadores_disponibles=False,
                interpretacion_temporal='No confirmada: no multiplicar ni dividir años automáticamente.',
                calibracion_estadistica=False, causalidad_competencia_supervivencia=False)


@dataclass(frozen=True)
class Hipotesis:
    nombre: str
    justificacion: str
    factor_supervivencia_nuevas: float = 1.
    supervivencia_existentes: float = 1.
    fraccion_reposicion: float = 0.
    factor_supervivencia_reposicion: float = 1.
    factor_precio_inicial: float = 1.
    factor_precio_reposicion: float = 1.
    factor_presupuesto: float = 1.

    def __post_init__(self):
        if not isinstance(self.nombre, str) or not self.nombre.strip():
            raise ValueError('Nombre de hipótesis requerido.')
        if not isinstance(self.justificacion, str) or not self.justificacion.strip():
            raise ValueError('Justificación explícita requerida.')
        campos = ('factor_supervivencia_nuevas', 'supervivencia_existentes',
                  'fraccion_reposicion', 'factor_supervivencia_reposicion',
                  'factor_precio_inicial', 'factor_precio_reposicion', 'factor_presupuesto')
        for k in campos:
            v = getattr(self, k)
            if (isinstance(v, bool) or not isinstance(v, numbers.Real)
                    or not np.isfinite(v) or v < 0):
                raise ValueError(f'{k}: número finito no negativo requerido.')
        if self.supervivencia_existentes > 1 or self.fraccion_reposicion > 1:
            raise ValueError('Probabilidades y fracción de reposición en [0,1].')


def preparar(n, q, probabilidades, costos, presupuesto, h):
    n, q, p, c = [np.asarray(x, dtype=float) for x in (n, q, probabilidades, costos)]
    if n.ndim != 1 or not len(n) or not (n.shape == q.shape == p.shape == c.shape):
        raise ValueError('Vectores no vacíos del mismo tamaño requeridos.')
    if not all(np.isfinite(x).all() for x in (n, q, p, c)):
        raise ValueError('Vectores finitos requeridos.')
    if any((x < 0).any() for x in (n, q, p, c)) or (p > 1).any():
        raise ValueError('Conteos/costos no negativos y probabilidades en [0,1].')
    if any((x % 1).any() or (x > 2**31-1).any() for x in (n, q)):
        raise ValueError('Conteos enteros no negativos hasta 2**31-1 requeridos.')
    # Sin recorte silencioso cuando un factor genera probabilidades inválidas.
    pn, pr = p*h.factor_supervivencia_nuevas, p*h.factor_supervivencia_reposicion
    if (pn > 1).any() or (pr > 1).any():
        raise ValueError('Factor genera una probabilidad mayor que uno.')
    B = Decimal(str(presupuesto))
    if not B.is_finite() or B < 0:
        raise ValueError('Presupuesto finito no negativo requerido.')
    ci = [Decimal(str(x))*Decimal(str(h.factor_precio_inicial)) for x in c]
    cr = [Decimal(str(x))*Decimal(str(h.factor_precio_reposicion)) for x in c]
    B *= Decimal(str(h.factor_presupuesto))
    n, q = n.astype(np.int64), q.astype(np.int64)
    inicial = sum((a*int(b) for a, b in zip(ci, q)), Decimal(0))
    return n, q, pn, pr, ci, cr, B, inicial


def proyectar(n, q, probabilidades, costos, presupuesto, h):
    n, q, pn, pr, ci, cr, B, inicial = preparar(n, q, probabilidades, costos, presupuesto, h)
    vivos_e, vivos_n = n*h.supervivencia_existentes, q*pn
    muertos = n+q-vivos_e-vivos_n
    reposiciones = h.fraccion_reposicion*muertos
    final = vivos_e+vivos_n+reposiciones*pr
    tabla = pd.DataFrame(dict(existentes=n, compras_iniciales=q, meta=n+q,
        prob_existentes=h.supervivencia_existentes, prob_nuevas=pn, prob_reposicion=pr,
        vivos_existentes_esperados=vivos_e, vivos_nuevas_esperados=vivos_n,
        muertes_esperadas=muertos, reposiciones_esperadas=reposiciones,
        vivos_finales_esperados=final, deficit_esperado=n+q-final,
        costo_inicial_um=[float(a*int(b)) for a, b in zip(ci, q)],
        costo_reposicion_esperado_um=reposiciones*np.array(cr, dtype=float)))
    costo_reposicion = float(tabla.costo_reposicion_esperado_um.sum())
    total = float(inicial)+costo_reposicion
    return tabla, dict(meta=int((n+q).sum()), compras_iniciales=int(q.sum()),
        vivos_iniciales_esperados=float((vivos_e+vivos_n).sum()),
        muertes_esperadas=float(muertos.sum()), reposiciones_esperadas=float(reposiciones.sum()),
        vivos_finales_esperados=float(final.sum()), deficit_esperado=float((n+q-final).sum()),
        costo_inicial_um=float(inicial), costo_reposicion_esperado_um=costo_reposicion,
        costo_total_esperado_um=total, presupuesto_um=float(B),
        cumple_compra_inicial=bool(inicial <= B),
        saldo_esperado_um=float(B)-total,
        alcance='Proyección bajo hipótesis; sin garantía presupuestaria ni espacial de reposición.')


def simular(n, q, probabilidades, costos, presupuesto, h, poligono, indice, semilla=20261014):
    for v in (poligono, indice, semilla):
        if isinstance(v, bool) or not isinstance(v, numbers.Integral) or v < 0:
            raise ValueError('Polígono, índice y semilla deben ser enteros no negativos.')
    n, q, pn, pr, ci, cr, B, inicial = preparar(n, q, probabilidades, costos, presupuesto, h)
    # Mismos flujos por stock entre hipótesis; independientes del orden del lote
    # y de los generadores espaciales. No implica dominancia muestra a muestra.
    rng = [np.random.default_rng(s) for s in np.random.SeedSequence(
        [int(semilla), 6, int(poligono), int(indice)]).spawn(4)]
    ve = rng[0].binomial(n, h.supervivencia_existentes)
    vn = rng[1].binomial(q, pn)
    muertos = n+q-ve-vn
    reposiciones = rng[2].binomial(muertos, h.fraccion_reposicion)
    vr = rng[3].binomial(reposiciones, pr)
    costo_r = sum((a*int(b) for a, b in zip(cr, reposiciones)), Decimal(0))
    costo = inicial+costo_r
    return dict(poligono=int(poligono), escenario=int(indice), hipotesis=h.nombre,
        vivos_primera_etapa=int((ve+vn).sum()), muertes=int(muertos.sum()),
        reposiciones=int(reposiciones.sum()), vivos_reposicion=int(vr.sum()),
        vivos_finales=int((ve+vn+vr).sum()), deficit=int((n+q-ve-vn-vr).sum()),
        compras_totales=int(q.sum()+reposiciones.sum()),
        costo_inicial_um=float(inicial), costo_reposicion_um=float(costo_r),
        costo_total_um=float(costo), presupuesto_um=float(B),
        saldo_um=float(B-costo), cumple_presupuesto=bool(costo <= B),
        exceso_um=float(max(Decimal(0), costo-B)))
