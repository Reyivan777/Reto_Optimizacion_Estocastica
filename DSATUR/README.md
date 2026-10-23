# Reforestación: optimización económica y DSATUR

La interfaz didáctica es **modelo_reforestacion.ipynb**. Trabajar desde `DSATUR/` e instalar `python -m pip install -r config/requirements.txt`. No se modifica `Algoritmo Genético/`.

## Motor C++17 opcional — fase 1

La migración C++17 está completada. La fase 4 incorpora sustituciones e intercambios de posiciones candidatas y la fase 5 añade Monte Carlo con precisión estadística y procesos opcionales. Las geometrías aproximadas aportadas todavía no están integradas en el ejecutor; los experimentos usan el rectángulo simulado y los mapas HTML siguen pospuestos.

Python permanece como referencia predeterminada. Compilar con `python scripts/compilar_cpp.py` (GCC/Clang C++17) y seleccionar `MOTOR = "cpp"` en el notebook o `--motor cpp` en `scripts/ejecutar_dos_etapas.py`. La selección de candidatas, DSATUR y los intercambios se ejecutan en C++; NumPy conserva los flujos aleatorios y SciPy/HiGHS la economía. No hay fallback silencioso.

Consultar [compilación, arquitectura y tolerancias](docs/MOTOR_CPP.md), [plan por fases](docs/PLAN_IMPLEMENTACION.md), [estado persistente](docs/ESTADO_IMPLEMENTACION.md) y [benchmarks medidos](docs/BENCHMARKS_CPP.md). Ejecutar `python tests/verificar_cpp.py` además de las dos baterías originales. Los módulos Python originales y los resultados históricos se conservan.

## Sustitución opcional de posiciones

DSATUR sigue siendo el algoritmo principal. Tras los intercambios de especies se puede sustituir la posición de una planta nueva por una candidata libre de la malla. La vecindad `mixta` permite también intercambiar coordenadas de dos plantas nuevas cuando el destino está ocupado. Cada planta conserva su especie, las existentes permanecen fijas y se mantienen cuotas, costo, presupuesto y C. Solo se aceptan descensos del objetivo original respetando pertenencia y separación. La etapa está **desactivada por defecto**, con los flujos históricos intactos; `sustituciones` preserva la implementación previa.

```powershell
python scripts/compilar_cpp.py
python scripts/ejecutar_dos_etapas.py --motor cpp --poligonos 1,13,5 --escenarios 12 --optimizar-posiciones --intentos-posiciones 6000 --sin-graficas
python tests/verificar_posiciones.py
# Comparación independiente: tres métodos, ambos motores, cuotas factibles, mismos escenarios
python scripts/comparar_posiciones.py
# Fase 4 completa: sustituciones + intercambios; económico o fijo
python scripts/ejecutar_dos_etapas.py --motor cpp --poligonos 1,13,5 --escenarios 1 --optimizar-posiciones --vecindad-posiciones mixta --sin-graficas
python scripts/comparar_posiciones.py --incluir-mixta
```

En el notebook: `OPTIMIZAR_POSICIONES = True`, `VECINDAD_POSICIONES = "mixta"` e `INTENTOS_POSICIONES = 6000`; en código: `perfil('completo', optimizar_posiciones=True, vecindad_posiciones='mixta', intentos_posiciones=6000, motor='cpp')`. Omitir la bandera o usar `False` reproduce el modelo de posiciones fijas. No hay alternancia ni desplazamientos continuos.

La interfaz `Terreno.contiene(puntos)` permite conectar posteriormente polígonos irregulares sin implementarlos aquí. `g_inicial` conserva las posiciones de las referencias; `g` contiene la distribución final. Véanse [formulación, resultados y límites](docs/OPTIMIZACION_POSICIONES.md). Los experimentos crean carpetas nuevas `resultados/comparacion_posiciones_<fecha>/`; no sustituyen históricos.

Referencia previa de **solo sustituciones** (21 de octubre): 12 escenarios por polígono, 6000 propuestas; mejora adicional media sobre DSATUR + local de especies y tiempo adicional C++ medido:

|Polígono|Reducción adicional|Tiempo adicional medio|
|---|---:|---:|
|P1, 842 plantas|2.58%|0.017 s|
|P13, 3323 plantas|1.80%|0.072 s|
|P5, 5264 plantas|1.98%|0.086 s|

En esa referencia 36/36 escenarios mejoraron, Python/C++ produjeron soluciones idénticas y 31/31 pruebas pasaron. Son resultados sobre rectángulos simulados, sin garantía de optimalidad espacial. La comparación actual de cuatro métodos, pruebas y límites se documenta en [OPTIMIZACION_POSICIONES.md](docs/OPTIMIZACION_POSICIONES.md); el diagnóstico de diferencias entre ramas está en [DIAGNOSTICO_FASE4.md](docs/DIAGNOSTICO_FASE4.md).

**Fase 4, validación del 23 de octubre:** vecindad mixta con reducción adicional media frente a posiciones fijas de **4.19% (P1), 3.44% (P13) y 3.50% (P5)**; mejoró los 36/36 escenarios y coincidió exactamente entre motores. La etapa C++ adicional promedió 0.0135/0.0781/0.1450 s respectivamente. Pasaron 36/36 pruebas, 72 regresiones apagadas y 216 comparaciones con los tres métodos previos; se preservaron 1217 archivos por SHA-256. Ver [resumen medido](resultados/comparacion_posiciones_20261023T192716_901247Z/resumen_fase4.csv). Se conserva el costo computacional adicional; no se certifica optimalidad ni supervivencia. La fase 5 se documenta en la sección siguiente.

## Monte Carlo espacial — fase 5

```shell
python scripts/escalar_monte_carlo.py --motor cpp --workers 2 --optimizar-posiciones --vecindad-posiciones mixta
python tests/verificar_monte_carlo.py
```

Ejecutor independiente: piloto de 30 escenarios y confirmación de tamaño fijo
estimado antes de observarla, entre 100 y 1000 escenarios por polígono.
Objetivo configurable: semiancho del IC de la media J final de hasta
`max(1, 0.25% de la media piloto)`. Publica error estándar, IC puntual del 95%,
percentiles, convergencia y agregación por escenarios completos. No cambia
compras, inventario ni las semillas anteriores. Posiciones sigue apagada por
defecto; sin opciones usa Python y un proceso.

Validación P1/P13/P5: 100 confirmaciones válidas por polígono, sin exclusiones;
los tres alcanzaron la precisión objetivo. Los IC son aproximados y describen
la media bajo los supuestos del modelo. No representan supervivencia.
Resultados, límites y benchmark serie/procesos en
[MONTE_CARLO_FASE5.md](docs/MONTE_CARLO_FASE5.md).
La fase 6 requiere otra solicitud.

## Estructura

```text
DSATUR/
├── README.md
├── modelo_reforestacion.ipynb
├── config/       # competencia.json y requirements.txt
├── data/         # datos de entrada
├── docs/         # validación, antecedentes e informe histórico
├── resultados/   # resultados por polígono y ejecución
├── scripts/      # ejecución y validación de lotes
├── src/          # paquete reforestacion
└── tests/        # pruebas del modelo fijo y económico
```

## Dos modos y etapas independientes

```bash
# Economía exclusivamente: 30 MILP, sin simulación espacial
python scripts/ejecutar_dos_etapas.py --etapa economica --poligonos todos
# Un polígono; por defecto compara con cuotas fijas bajo condiciones idénticas
python scripts/ejecutar_dos_etapas.py --poligonos 5 --escenarios 1
# Selección
python scripts/ejecutar_dos_etapas.py --poligonos 5,9,10,12,18,23 --escenarios 1
# Los 30; prueba progresiva
python scripts/ejecutar_dos_etapas.py --poligonos todos --escenarios 1
# Experimento Monte Carlo completo (costoso)
python scripts/ejecutar_dos_etapas.py --poligonos todos --escenarios 12
# Modo histórico: no repara cuotas
python scripts/ejecutar_dos_etapas.py --modo fijo --poligonos todos --escenarios 1
# Pruebas
python tests/verificar_modelo.py
python tests/verificar_economia.py
# Validación completa pareada: 12 escenarios, 6 procesos independientes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/validar_lote_economico.py --escenarios 12 --workers 6
```

`--sin-comparacion` omite la ejecución espacial fija de referencia; `--sin-graficas` evita renderizar PNG. Cada ejecución crea `resultados/ejecuciones/<fecha_UTC>_<modo>/`; nunca sustituye otra carpeta. El notebook conserva un recorrido explicativo con cuotas fijas (secciones 2–14), separado del experimento elegido mediante `MODO` en la sección 15. Sus parámetros iniciales usan un escenario para comprobar funcionamiento; 12 habilita el experimento completo. Se aceptan un ID, una lista o `"todos"`.

Para ejecutar solo la etapa espacial a partir de cuotas ya calculadas:

```python
import json
from pathlib import Path
import sys
root = Path.cwd()
sys.path.insert(0, str(root/'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos, cargar_competencia
from reforestacion.optimizacion_economica import DatosConCuotas
from reforestacion.experimento import ejecutar_escenario, ejecutar_lote

datos = Datos(root)
cfg = perfil('completo', poligonos=(5,), escenarios=1)
C = cargar_competencia(root/'config/competencia.json', datos.S)
# Sustituir por la carpeta de la ejecución económica elegida:
archivo = root/'resultados/ejecuciones/FECHA_economico/planes.json'
planes = {int(k): v for k, v in json.loads(archivo.read_text()).items()}
vista = DatosConCuotas(datos, planes)
fila, detalle = ejecutar_escenario(5, 0, vista, cfg, C)
# O ejecutar_lote(vista, cfg, C) para varios escenarios.
```

La vista vuelve a validar bandas, total, inventario y presupuesto contra los datos/configuración actuales. Si se cambian datos después de planificar, recalcular el plan para obtener nuevamente garantías de optimalidad. Los módulos originales siguen disponibles; si se llaman sus exportadores directamente, elegir una carpeta nueva para no sobrescribir sus salidas.

## Formulación económica

Por polígono, R es la cuota final original, n el inventario, c el costo unitario, A el área, B=12500A y T=sum(R). Las decisiones enteras son x=R' y q=x−n. Se impone:

- `sum(x)=T`.
- `max(n, ceil(0.9 R)) <= x <= floor(1.1 R)`.
- `sum(c*q) <= B`, sin transferencias entre polígonos.
- Integridad y no negatividad de x y q.

**Supuesto pendiente de confirmar con el socio:** el ±10% se aplica sobre las cuotas finales originales ya redondeadas, no sobre las compras. El presupuesto corresponde únicamente a **adquisición de plantas**, no a transporte, riego, mantenimiento ni reposición; la moneda no está especificada.

Se minimiza `D = sum(abs(x_s−R_s)/R_s)` para R_s>0. Se introducen auxiliares d>=0 con `d>=x−R` y `d>=R−x`. Para R_s=0, la banda fuerza x_s=0 y se omite el término. La implementación multiplica todos los pesos por el mismo factor positivo para mejorar su escala, sin cambiar el óptimo.

La desviación absoluta sin normalizar puede concentrar modificaciones proporcionalmente grandes en especies poco frecuentes. La relativa penaliza más esos cambios; la banda limita además cada especie. Una combinación requeriría un peso ecológico adicional no respaldado por los datos. Esto protege la composición numérica, sin demostrar equivalencia ecológica.

La prioridad lexicográfica se aplica con dos llamadas a **scipy.optimize.milp/HiGHS**: primero D, después costo con D fijada. Solo se acepta el desempate si la desviación calculada con fracciones exactas permanece idéntica y el costo no aumenta. Si el segundo paso no consigue certificarlo, se conserva la primera solución factible y se informa la limitación. `status=0` y gap cero certifican optimalidad **numérica del solver**, no una prueba simbólica exacta ni optimalidad espacial. Límites de tiempo se identifican y una solución incumbente solo se usa después de validarla, sin afirmar óptimo.

El costo y el presupuesto se convierten a unidades decimales enteras comunes para la validación posterior: no se amplía el presupuesto mediante tolerancias. Se preserva el mínimo económico anterior: llenar los límites inferiores y completar por costo creciente da el mínimo dentro de la banda por intercambio. Si ese mínimo supera B se reporta inviabilidad y el presupuesto mínimo requerido. Bandas incompatibles no tienen presupuesto reparador.

## Integración, estados y rendimiento

`optimizacion_economica.py` decide cuotas y crea una vista de datos, sin mutar el catálogo ni el inventario. `dos_etapas.py` coordina planificación, llamadas a `ejecutar_escenario`, verificación final y reportes. La etapa opcional de posiciones se integra mediante `config.py` y `experimento.py`; conserva `algoritmos.py`, `geometria.py`, `datos.py`, `economia.py`, la matriz C y las validaciones originales.

Los swaps y la sustitución de posiciones conservan las cuotas ajustadas. Se vuelve a comprobar el histograma final, las compras y el presupuesto. Como total e inventario no cambian, los mismos flujos aleatorios generan exactamente los mismos sitios iniciales y etiquetas existentes en ambos modos; esto se verifica en cada comparación pareada. Las posiciones finales pueden diferir si se activa su optimización. Todas las especies pueden ocupar cualquier sitio nuevo: no existe una prohibición especie-sitio adicional. La capacidad geométrica depende del total, no de la composición.

`estado_factibilidad` distingue:

|Estado|Interpretación|
|---|---|
|factible_economica_y_espacialmente|Ambas etapas verificadas|
|inviable_economicamente|La banda/inventario/total o el presupuesto impiden un plan|
|inviable_economicamente_cuotas_fijas|Referencia espacial válida, pero excede B|
|economica_factible_espacial_no_construida|Plan válido; no se construyó una geometría válida con la malla/límite empleado|
|error_ejecucion|Fallo técnico o validación fallida; no se presenta como solución|
|omitido_limite_computacional|Exceso de límites o solver sin solución al agotar tiempo|

Una construcción fallida no demuestra imposibilidad matemática en todo el terreno. Se conserva el detalle del error. `estado=ok` sigue significando validación espacial en los CSV originales; usar `estado_factibilidad` para el sistema integrado. En etapa exclusivamente económica aún no se afirma factibilidad espacial.

Se revisaron los cuellos de botella: selección sucesiva de posiciones y ordenación de vértices en DSATUR tienen crecimiento aproximadamente cuadrático; grafo usa cKDTree, y búsqueda local usa aristas incidentes. No se cambian para preservar resultados. La mejora aplicada es resolver economía una vez por polígono y reutilizar la referencia fija **de esa misma ejecución** cuando las cuotas son idénticas. Para 30 polígonos, 24 no cambian: la comparación requiere 36 ejecuciones espaciales por escenario en lugar de 60. No se interpreta esta reducción de llamadas como un porcentaje medido de aceleración del tiempo total. Las gráficas son opcionales y los tiempos reales quedan registrados.

## Salidas y trazabilidad

Dentro de cada carpeta nueva:

- `planes.json`: cuotas, compras, mínimo económico, desviación, status/gap y certificados de ambos pasos.
- `cuotas.csv`: R original/ajustada, existentes, compras, diferencias firmadas, absolutas y porcentuales por especie.
- `economia.csv`: presupuesto, costos, ahorro y tiempo económico **una sola vez por polígono**.
- `escenarios.csv`: estado, tres índices J y tiempos por polígono/escenario.
- `resumen_por_poligono.csv`: economía y medias espaciales con denominadores explícitos.
- `referencia_fija_pareada.csv` y `comparacion_pareada.csv`: referencias recién ejecutadas y diferencias por escenario; no mezcla con promedios históricos.
- `configuracion.json`: parámetros, versiones, hashes de entradas/código, semillas, conteos y tiempo total hasta exportar tablas/manifiesto (excluye figuras comparativas finales).
- `economia.png`, `cambio_competencia.png` y carpetas `P*/`: gráficas, distribución del escenario cero y estadísticas Monte Carlo.

Un J faltante no se reemplaza por cero. Las medias indican cuántos escenarios completaron; una sola realización no permite desviación estándar. `seg_total` en una fila reutilizada conserva el tiempo de la referencia; `seg_espacial_adicional=0` identifica que no se ejecutó otra vez. No sumar `seg_economia` por escenarios: usar la tabla económica.

La referencia histórica de esta implementación es el commit **75a54abc199563471bec29bba051da3d1d483e8b**. `resultados/P*/` y `resultados/modelo_completo/` permanecen byte a byte intactos. La evidencia de las pruebas de esta actualización se documenta en `docs/VALIDACION_ECONOMICA.md`. El validador paralelo crea una carpeta `validacion_30_<fecha>/` con tablas agregadas y una subcarpeta por ejecución de polígono; sus tiempos acumulados no deben confundirse con tiempo de pared. La concurrencia no modifica parámetros ni semillas. En Windows puede omitirse el prefijo de variables de entorno del comando.

El desarrollo del modo original de cuotas fijas quedó archivado en [MODELO_CUOTAS_FIJAS_HISTORICO.md](docs/MODELO_CUOTAS_FIJAS_HISTORICO.md). La evidencia de validación está en [VALIDACION_ECONOMICA.md](docs/VALIDACION_ECONOMICA.md).
