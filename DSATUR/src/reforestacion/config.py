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
    presupuesto_por_ha: float = 12500.0  # referencia; se valida, no altera cuotas
    motor: str = 'python'      # al final para conservar argumentos posicionales
    optimizar_posiciones: bool = False
    intentos_posiciones: int = 6000
    vecindad_posiciones: str = 'sustituciones'  # 'mixta' habilita destinos ocupados
    geometria: str = 'simulada'
    archivo_geometrias: str = ''
    archivo_existentes: str = ''
    crs_origen: str = ''
    crs_destino: str = ''

    def __post_init__(self):
        if self.geometria not in ('simulada','aproximada','georreferenciada'):
            raise ValueError('geometria debe ser simulada, aproximada o georreferenciada.')
        if self.geometria == 'georreferenciada' and not (self.archivo_geometrias and self.crs_origen and self.crs_destino):
            raise ValueError('Georreferenciación requiere archivo y CRS explícitos.')
        if not isinstance(self.optimizar_posiciones, bool):
            raise ValueError('optimizar_posiciones debe ser booleano.')
        if self.vecindad_posiciones not in ('sustituciones', 'mixta'):
            raise ValueError('vecindad_posiciones debe ser sustituciones o mixta.')
        if self.motor not in ('python', 'cpp'):
            raise ValueError('Motor debe ser python o cpp.')
        positivos = [self.presupuesto_por_ha, self.densidad, self.aspecto, self.paso_malla, self.separacion_min, self.radio]
        if not np.isfinite(positivos).all() or min(positivos) <= 0:
            raise ValueError('Parámetros geométricos finitos y positivos requeridos.')
        if self.paso_malla < self.separacion_min:
            raise ValueError('paso_malla debe ser >= separacion_min.')
        for nombre in ('escenarios', 'intentos_local', 'intentos_por_nueva',
                       'max_propuestas_posicion', 'max_plantas', 'max_corridas', 'semilla', 'intentos_posiciones'):
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


