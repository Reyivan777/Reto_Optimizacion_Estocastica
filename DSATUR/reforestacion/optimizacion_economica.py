"""MILP independiente: cuotas finales ±10%, total e inventario conservados."""
from decimal import Decimal
from fractions import Fraction
from time import perf_counter
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


def unidades_exactas(costos, presupuesto):
    """Escala decimal común; sin tolerancia monetaria ni redondeo del presupuesto."""
    valores = [Decimal(str(x)) for x in [*costos, presupuesto]]
    if any(not x.is_finite() or x < 0 for x in valores):
        raise ValueError('Costos y presupuesto deben ser finitos y no negativos.')
    escala = 10 ** max(0, -min(x.as_tuple().exponent for x in valores))
    enteros = [int(x * escala) for x in valores]
    if max(enteros, default=0) > 2**50:
        raise ValueError('Precisión monetaria excesiva para el solver.')
    return np.array(enteros[:-1], dtype=np.int64), enteros[-1], escala


def validar_cuotas(R, n, ajustadas, costos, presupuesto):
    R, n, x = map(np.asarray, (R, n, ajustadas))
    if not (R.shape == n.shape == x.shape) or np.any(x % 1):
        raise ValueError('Cuotas incompatibles o no enteras.')
    if (x < np.maximum(n, (90*R+99)//100)).any() or (x > 110*R//100).any() or x.sum() != R.sum():
        raise ValueError('Se incumplen bandas, inventario o total.')
    c, B, _ = unidades_exactas(costos, presupuesto)
    if sum(int(a)*int(b) for a,b in zip(c, x-n)) > B:
        raise ValueError('Presupuesto individual excedido.')
    return True


def desviacion_exacta(x, R):
    return sum((Fraction(abs(int(a)-int(b)), int(b)) for a,b in zip(x,R) if b), Fraction())


def optimizar_cuotas(R, n, costos, presupuesto, limite_segundos=60.):
    """Dos MILP: desviación relativa mínima y luego costo con desviación fija.

    Solo status=0 certifica optimalidad numérica del solver. Se revalida la
    factibilidad con enteros y moneda decimal; un límite no prueba inviabilidad.
    El desempate se acepta solo si conserva EXACTAMENTE la fracción objetivo.
    """
    inicio = perf_counter()
    R, n, costos = map(np.asarray, (R,n,costos))
    if R.ndim != 1 or not len(R) or R.shape != n.shape or R.shape != costos.shape:
        raise ValueError('Vectores incompatibles.')
    if not np.isfinite(R).all() or not np.isfinite(n).all() or (R<0).any() or (n<0).any() or (R%1).any() or (n%1).any():
        raise ValueError('Cuotas e inventarios deben ser enteros no negativos.')
    if not np.isfinite(limite_segundos) or limite_segundos <= 0:
        raise ValueError('Límite del solver debe ser positivo.')
    R,n = R.astype(np.int64),n.astype(np.int64)
    c,B,escala = unidades_exactas(costos,presupuesto)
    k=len(R); lo=np.maximum(n,(90*R+99)//100); hi=110*R//100
    info=dict(estado='inviable_economicamente', detalle='', R_original=R.tolist(),
              existentes=n.tolist(), presupuesto_um=float(presupuesto),
              costo_original_um=float(costos@(R-n)), costo_minimo_um=None,
              certificado_desviacion=False, certificado_desempate=False, solver=[])
    def terminar(**campos):
        info.update(campos); info['seg_economia']=perf_counter()-inicio
        return info
    if (lo>hi).any() or lo.sum()>R.sum() or hi.sum()<R.sum():
        return terminar(detalle='Bandas e inventario incompatibles con el total.')
    # Mínimo exacto por intercambio: igualdad única y capacidades enteras.
    minimo=lo.copy(); falta=int(R.sum()-lo.sum())
    for s in np.argsort(c,kind='stable'):
        delta=min(falta,int(hi[s]-minimo[s])); minimo[s]+=delta; falta-=delta
    costo_min=sum(int(a)*int(b) for a,b in zip(c,minimo-n))
    info['costo_minimo_um']=costo_min/escala
    if costo_min>B:
        return terminar(detalle='El presupuesto es menor al mínimo requerido dentro de la banda.')
    # d_s >= x_s-R_s y d_s >= R_s-x_s. R=0 implica x=0 y peso 0.
    pesos=np.divide(float(max(R.max(),1)),R,out=np.zeros(k),where=R>0)
    A=np.vstack([np.r_[np.ones(k),np.zeros(k)],np.r_[c,np.zeros(k)],
                 np.c_[np.eye(k),-np.eye(k)], np.c_[-np.eye(k),-np.eye(k)]])
    lower=np.r_[R.sum(),-np.inf,np.full(2*k,-np.inf)]
    upper=np.r_[R.sum(),B+int(c@n),R,-R]
    bounds=Bounds(np.r_[lo,np.zeros(k)],np.r_[hi,np.maximum(R-lo,hi-R)])
    integrality=np.r_[np.ones(k),np.zeros(k)]
    opciones={'time_limit':float(limite_segundos),'mip_rel_gap':0.0}
    def resolver(obj,mat,inf,sup):
        sol=milp(obj,integrality=integrality,bounds=bounds,
                 constraints=LinearConstraint(mat,inf,sup),options=opciones)
        info['solver'].append(dict(status=int(sol.status),mensaje=sol.message,
            gap=float(sol.mip_gap) if getattr(sol,'mip_gap',None) is not None else None))
        return sol
    objetivo=np.r_[np.zeros(k),pesos]
    sol=resolver(objetivo,A,lower,upper)
    if sol.x is None:
        return terminar(estado='omitido_limite_computacional' if sol.status==1 else 'error_ejecucion',
                        detalle='MILP no produjo solución; no se afirma inviabilidad adicional.')
    x=np.rint(sol.x[:k]).astype(np.int64)
    try: validar_cuotas(R,n,x,costos,presupuesto)
    except ValueError as error:
        return terminar(estado='error_ejecucion',detalle=str(error))
    info['certificado_desviacion']=sol.status==0
    if sol.status==0:
        valor=float(pesos@np.abs(x-R))
        seg=resolver(np.r_[c,np.zeros(k)],np.vstack([A,objetivo]),np.r_[lower,valor],np.r_[upper,valor])
        if seg.x is not None:
            candidato=np.rint(seg.x[:k]).astype(np.int64)
            try:
                validar_cuotas(R,n,candidato,costos,presupuesto)
                if desviacion_exacta(candidato,R)==desviacion_exacta(x,R) and c@candidato<=c@x:
                    x=candidato; info['certificado_desempate']=seg.status==0
            except ValueError:
                pass  # conservar primera solución válida, sin certificar desempate
    costo=sum(int(a)*int(b) for a,b in zip(c,x-n))/escala
    return terminar(estado='factible_economicamente',R_ajustada=x.tolist(),compras=(x-n).tolist(),
        costo_ajustado_um=costo,ahorro_um=info['costo_original_um']-costo,
        desviacion_relativa=float(desviacion_exacta(x,R)),
        detalle='Óptimo certificado por solver (tolerancias numéricas estándar).' if info['certificado_desviacion'] and info['certificado_desempate'] else 'Solución validada; optimalidad lexicográfica completa no certificada.')


class DatosConCuotas:
    """Vista de datos; no modifica inventario, catálogo ni archivos originales."""
    def __init__(self, datos, planes):
        self.original=datos
        self.planes=planes
    def __getattr__(self,nombre):
        return getattr(self.original,nombre)
    def poligono(self,p,config):
        area,n,R,q=self.original.poligono(p,config)
        plan=self.planes[p]
        if plan['estado']!='factible_economicamente':
            raise ValueError(f'P{p}: no hay cuotas económicas factibles.')
        x=np.asarray(plan['R_ajustada'],dtype=int)
        presupuesto=float(Decimal(str(area))*Decimal(str(config.presupuesto_por_ha)))
        validar_cuotas(R,n,x,self.especies.costo_unitario.to_numpy(),presupuesto)
        return area,n,x,x-n


def planificar(datos,config,poligonos,limite_segundos=60.):
    planes={}
    for p in poligonos:
        a,n,R,q=datos.poligono(p,config)
        B=float(Decimal(str(a))*Decimal(str(config.presupuesto_por_ha)))
        inicio=perf_counter()
        try:
            planes[p]=optimizar_cuotas(R,n,datos.especies.costo_unitario.to_numpy(),B,limite_segundos)
        except Exception as error:
            planes[p]=dict(estado='error_ejecucion',detalle=f'{type(error).__name__}: {error}',
                seg_economia=perf_counter()-inicio,certificado_desviacion=False,
                certificado_desempate=False)
    return planes
