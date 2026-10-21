# Benchmarks de fase 1

Ejecución: 21 de octubre de 2026, Windows 11, Intel Family 6 Model 186, CPython 3.12.10 x64, TDM-GCC 10.3.0, NumPy 2.5.4, SciPy 1.18.1, pandas 3.0.6 y NetworkX 3.7. Semilla 20261014, 6000 propuestas locales por escenario, mismas cuotas fijas, geometrías simuladas e índices de escenario. Los benchmarks no sustituyen la validación económica con cuotas ajustadas.

Evidencia: [comparación](../resultados/benchmarks/20261021T062053_890100Z/comparacion.json) y [manifiesto](../resultados/benchmarks/20261021T062053_890100Z/manifiesto.json). Cada subcarpeta conserva resumen con parámetros, tiempos por etapa, memoria inicial/final, compilación e identificadores SHA-256; escenarios.jsonl registra cada realización. Los hashes de entradas (coordenadas, existentes, cuotas) y de asignaciones DSATUR/final coinciden entre motores en los ocho grupos.

## Tiempo de pared medido

|Polígono|Plantas por escenario|Escenarios de ese polígono|Python (s)|C++ (s)|Python/C++|
|---|---:|---:|---:|---:|---:|
|P1|842|1|0.146|0.059|2.45×|
|P13|3323|1|0.676|0.146|4.64×|
|P5|5264|1|1.374|0.224|6.12×|
|P1|842|12|1.668|0.626|2.66×|
|P13|3323|12|9.679|1.454|6.65×|
|P5|5264|12|23.032|2.741|8.40×|
|P1|842|100|17.901|7.628|2.35×|
|P1|842|1000|187.373|75.011|2.50×|

10000 escenarios de P1: **no ejecutados**, al superar el presupuesto restante de 600 s del escalamiento. El manifiesto conserva una estimación solo para programar/omitir ese trabajo; no constituye un tiempo medido. No se hicieron 1000/10000 escenarios de cada uno de los 30 polígonos. El ensayo histórico adicional sí comprende 30×12=360 escenarios.

Cada medición incluye pipeline, conversiones CSR, generación de propuestas NumPy, verificaciones, escritura de CSV de la distribución actual y JSONL. Excluye compilación, importaciones y carga inicial de biblioteca. Sin figuras PNG. Procesos independientes por grupo/motor, un hilo BLAS/OMP, ejecución serial Python seguida de C++; no se ejecutaron otras pruebas computacionales durante estos grupos. Durante el escalamiento se añadieron metadatos a exportadores que el benchmark no invoca; los núcleos y el pipeline medido se mantuvieron iguales.

Se hizo una repetición por carga; 12/100/1000 son escenarios diferentes, no repeticiones cronometradas de un único escenario. El orden no fue aleatorizado. Temperatura, carga del equipo, cachés y sistema de archivos pueden variar: estas aceleraciones describen estas ejecuciones y no garantizan un factor universal.

## Etapas: P5, suma de doce escenarios (s)

|Etapa|Python|C++|
|---|---:|---:|
|Existentes NumPy|0.295|0.208|
|Construcción/filtro de malla y selección de candidatas|8.026|0.554|
|Grafo cKDTree/NetworkX|1.043|0.801|
|DSATUR|11.860|0.300|
|Búsqueda local, incluidas propuestas NumPy|1.348|0.494|
|Exportación de distribución CSV|0.127|0.104|
|Pared completa|23.032|2.741|

La diferencia en etapas comunes, como existentes y grafo, es variación de ejecución, no aceleración atribuible a migrarlas. La pared completa incluye validación, referencia aleatoria, objetivos, lectura de datos, hashes y escritura de filas; no coincide exactamente con la suma de las etapas listadas. seg_geometria incluye existentes/candidatas/grafo, y seg_total las incluye de nuevo: **no sumar columnas inclusivas**.

El perfil inicial anterior a implementar C++ (P5 e0, cProfile) dio 1.552 s instrumentados: DSATUR 0.775, candidatas 0.503, grafo 0.115, local 0.114 y existentes 0.029. Confirmó los objetivos de migración. No se usa ese perfil instrumentado para calcular aceleraciones; la línea base es el motor Python original medido sin profiler. perfilar_python.py permite guardar el perfil y la exportación en una carpeta independiente.

## Memoria máxima residente

|Carga|Python (MiB)|C++ (MiB)|
|---|---:|---:|
|P1 × 1|99.84|100.81|
|P5 × 12|122.03|120.88|
|P1 × 100|101.75|102.38|
|P1 × 1000|109.58|110.92|

Valores del proceso completo, no solo arrays nativos. En P1×1000 el proceso C++ inicia alrededor de 96.40 MiB y alcanza 110.92 MiB; no retiene 1000 distribuciones. Los núcleos no garantizan reducir RSS porque Python/NetworkX y sus asignadores dominan parte del consumo. Se conserva una distribución, se liberan detalles por escenario y se transmiten filas a disco. La matriz densa de distancias no se utiliza.

## Validación

Las baterías verifican pequeñas/medianas/grandes instancias, ausencia de aristas, cero/una posición movible, ausencia de existentes o nuevas, empates, propuestas precalculadas, deltas contra objetivo completo, errores controlados, invariantes geométricos y todas las cuotas económicas. El presupuesto se contrasta con el valor decimal del plan, sin reconstruirlo mediante multiplicación flotante que introduzca decimales espurios.

El resultado de regresión de las 360 referencias y la ejecución independiente del notebook se registra en ESTADO_IMPLEMENTACION.md junto a las rutas y los conteos efectivamente completados. Compilación Linux viable por interfaz y opciones; pendiente probarla en un equipo Linux. No hay mapas, geometrías reales, movilidad ni inferencia estadística nueva en esta fase.
