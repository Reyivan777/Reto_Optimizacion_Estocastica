from dataclasses import dataclass, replace
import numpy as np

@dataclass(frozen=True)
class Config:
    densidad: float = 658.0
    aspecto: float = 1.0        # ancho / alto del rectángulo aproximado
    paso_malla: float = 3.4    # tresbolillo de candidatas, no densidad final
    separacion_min: float = 3.4 # SUPUESTO: aplicar distancia ilustrada a todos los pares
    radio: float = 6.0         # interacción, distinto de la separación física
    semilla: int = 20261014
    escenarios: int = 12
    intentos_local: int = 6000
    max_propuestas_posicion: int = 200000
    presupuesto: str = 'fijo'
    intentos_por_nueva: int = 10
    poligonos: tuple = (1,)
    max_plantas: int = 4000
    max_corridas: int = 24
    diagnosticos: bool = False

    def __post_init__(self):
        positivos = [self.densidad, self.aspecto, self.paso_malla, self.separacion_min, self.radio]
        if not np.isfinite(positivos).all() or min(positivos) <= 0:
            raise ValueError('Parámetros geométricos finitos y positivos requeridos.')
        if self.paso_malla < self.separacion_min:
            raise ValueError('paso_malla debe ser >= separacion_min.')
        for nombre in ('escenarios', 'intentos_local', 'intentos_por_nueva',
                       'max_propuestas_posicion', 'max_plantas', 'max_corridas', 'semilla'):
            v = getattr(self, nombre)
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise ValueError(f'{nombre} debe ser entero no negativo.')
        if min(self.escenarios, self.max_plantas, self.max_corridas) < 1:
            raise ValueError('Escenarios y límites deben ser positivos.')
        if self.presupuesto not in ('fijo', 'proporcional'):
            raise ValueError('Presupuesto debe ser fijo o proporcional.')

    def intentos(self, nuevas):
        return self.intentos_local if self.presupuesto == 'fijo' else self.intentos_por_nueva * nuevas


def perfil(nombre='rapido', **cambios):
    """Completo permite escala mayor, pero solo procesa IDs solicitados."""
    if nombre not in ('rapido', 'completo'):
        raise ValueError('Perfil desconocido.')
    cfg = Config(escenarios=2) if nombre == 'rapido' else Config(max_plantas=20000, max_corridas=360)
    return replace(cfg, **cambios)

