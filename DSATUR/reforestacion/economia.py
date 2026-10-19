"""Validación económica con cuotas fijas; flexibilidad solo como diagnóstico."""
import numpy as np
import pandas as pd


def presupuesto_poligono(datos, p, config):
    area, n, R, q = datos.poligono(p, config)
    presupuesto = float(config.presupuesto_por_ha * area)
    costo = float(datos.especies.costo_unitario.to_numpy() @ q)
    cumple = costo <= presupuesto + 1e-8  # tolerancia de coma flotante, no relajación monetaria
    return dict(poligono=int(p), area_ha=area, existentes=int(n.sum()), nuevas=int(q.sum()),
                total=int(R.sum()), presupuesto_um=presupuesto, costo_um=costo,
                saldo_um=presupuesto-costo, presupuesto_utilizado_pct=100*costo/presupuesto,
                cumple_presupuesto=bool(cumple),
                estado_presupuesto='cumple' if cumple else 'inviable_cuotas_fijas')


def presupuestos(datos, config):
    """Verifica los 30 independientemente, aunque solo se optimice uno."""
    return pd.DataFrame([presupuesto_poligono(datos, int(p), config) for p in datos.areas.index])


def diagnostico_flexibilidad(datos, config):
    """Cota mínima exacta de costo bajo una interpretación explícita de ±10% de R.

    No modifica datos, cuotas ni asignaciones. No impone criterios ecológicos nuevos.
    La única igualdad acoplada es sum(R')=T: llenar capacidad por costo creciente
    es óptimo por intercambio (capacidades y demanda enteras).
    """
    costos = datos.especies.costo_unitario.to_numpy(float)
    filas = []
    for p in datos.areas.index:
        a,n,R,q = datos.poligono(p,config)
        inferior = np.maximum(n, (90*R+99)//100)
        superior = (110*R)//100
        propuesto = inferior.copy()
        faltante = int(R.sum()-propuesto.sum())
        posible = bool(np.all(inferior <= superior) and faltante >= 0)
        if posible:
            for s in np.argsort(costos, kind='stable'):
                cantidad = min(faltante, int(superior[s]-propuesto[s]))
                propuesto[s] += cantidad
                faltante -= cantidad
            posible = faltante == 0
        minimo = float(costos @ (propuesto-n)) if posible else np.nan
        B = float(a*config.presupuesto_por_ha)
        filas.append(dict(poligono=int(p), presupuesto_um=B, costo_fijo_um=float(costos@q),
            costo_minimo_banda_10_um=minimo, ahorro_maximo_teorico_um=float(costos@q)-minimo,
            presupuesto_alcanzable_en_banda=bool(posible and minimo <= B+1e-8),
            total_conservado=bool(posible and propuesto.sum()==R.sum()),
            existentes_conservados=bool(posible and (propuesto>=n).all()),
            validacion_ecologica='pendiente; banda numerica no equivale a validacion ecologica',
            aplicado_al_modelo=False))
    return pd.DataFrame(filas)
