## Modelo original de cuotas fijas (referencia del commit 75a54ab)

Esta documentación describe el comportamiento histórico del modo de cuotas fijas antes de integrar la etapa económica. La explicación actual está en el [README principal](../README.md).


Lo siguiente describe el modo original y sus resultados históricos. Las frases «no aplicado» o «futuro» se refieren exclusivamente a esa versión; el modo económico actual se documenta arriba. Sus rutas de salida antiguas no son las rutas del nuevo ejecutor.

# Modelo DSATUR — Reforestación

La interfaz principal es **[modelo_reforestacion.ipynb](../modelo_reforestacion.ipynb)**. Abre la carpeta **DSATUR/** como carpeta de trabajo en VS Code/Jupyter e instala `python -m pip install -r config/requirements.txt`. No se cambia el enfoque independiente de `Algoritmo Genético/`.

## Configurar y ejecutar

En la primera celda de código:

```python
POLIGONOS = "todos"    # o un entero de 1 a 30
ESCENARIOS_MC = 12     # Monte Carlo del polígono detallado
ESCENARIOS_LOTE = 12   # escenarios de cada polígono al elegir todos
EJECUTAR_COMPARACION_PRESUPUESTOS = False
```

Ejecuta en orden. Usa `ESCENARIOS_LOTE = 1` para una prueba rápida; un escenario no permite estimar una desviación estándar. El perfil completo limita cada polígono a 20000 plantas y cada lote a 360 corridas; los excesos quedan `omitido`. Los parámetros están en `src/reforestacion/config.py`.

Un ID genera sus resultados individuales; no actualiza una carpeta global que pudiera existir de una ejecución anterior (consulta su configuración). `"todos"` produce automáticamente P1–P30 y `resultados/modelo_completo/`. Las gráficas didácticas iniciales corresponden al primero de la selección; la sección 15 presenta el conjunto completo. Si los dos números de escenarios difieren, las carpetas individuales finales reflejan el experimento del lote, de forma uniforme. La comparación opcional de **presupuestos de propuestas de búsqueda** es distinta del presupuesto económico de adquisición.

## Matemática y heurísticas preservadas

P contiene 30 polígonos y S diez especies. F_p son posiciones existentes simuladas, V_p sitios nuevos seleccionados y U_p su unión; E_p contiene pares a distancia ≤6 m. Las posiciones se guardan como coordenadas `(x,y)` en metros. Para cada sitio nuevo se asigna exactamente una especie; las existentes y cuotas finales R_ps quedan fijas. Las compras son q_ps=R_ps−n_ps; `sum_s R_ps=floor(658 A_p+0.5)` y todos los sitios ocupados se separan al menos 3.4 m. La geometría se selecciona antes de asignar especies.

Se minimiza el índice adimensional:

$$J=\sum_p\sum_{\{i,j\}\in E_p}\max(0,1-d_{ij}/r)C_{s_i,s_j}.$$

C se carga de `config/competencia.json`: 3 misma especie, 2 especies distintas del mismo género, 1 géneros distintos. Es un supuesto provisional, simétrico, finito y no negativo; no una medición ecológica. Datos, matriz, geometría, objetivos, cuotas, desempates y semillas no se alteran para estas mejoras.

**DSATUR inicializa** la solución: prioriza saturación (especies distintas de vecinos asignados), grado ponderado e índice; elige especie disponible por costo incremental, cuota pendiente e índice. No es coloreo propio: puede repetir especie vecina, con penalización.

**Búsqueda local:** propone dos posiciones nuevas distintas, descarta especies iguales, calcula ΔJ por aristas incidentes y acepta únicamente ΔJ<−1e−10 (tolerancia histórica de empates). Conserva posiciones, existentes y cantidades. El presupuesto por defecto es 6000 propuestas, incluidas las descartadas; no equivale a 6000 aceptaciones ni certifica óptimo local/global. Se conservan los contadores técnicos y J_dsatur.

Las figuras principales comparan solo **Aleatoria** y **DSATUR + búsqueda local**. La reducción `100(J_base−J_final)/J_base` corresponde a todo el procedimiento, no exclusivamente a DSATUR. `comparacion.csv` conserva las tres etapas como datos técnicos. El diagnóstico opcional de trayectoria muestra propuestas en X, J en Y; descensos = intercambios aceptados y mesetas = ausencia de mejora.

## Monte Carlo: qué se simula

- Conteos existentes, metas, compras y costos son conocidos y fijos.
- Se proponen coordenadas existentes uniformes en un rectángulo de área equivalente; el rechazo por separación introduce dependencia. Las etiquetas se permutan conservando el inventario exacto.
- La malla triangular, el filtrado respecto a existentes y la selección sucesiva por dispersión son deterministas dada la geometría simulada. Los sitios nuevos **no son puntos aleatorios independientes**.
- La referencia aleatoria y las propuestas locales usan flujos independientes de las posiciones. DSATUR es determinista dado el grafo y sus entradas.
- `SeedSequence([semilla,p,escenario]).spawn(3)` separa los flujos; el orden del lote no cambia una solución. La semilla predeterminada es 20261014. Versiones y hashes de entradas quedan en el manifiesto global.

Un escenario individual incluye todas las posiciones y la reoptimización de un polígono. En P1 conserva 165 existentes y 677 nuevas, no doce posiciones cuando se configuran doce escenarios. Un escenario **global** reúne una realización de cada uno de los 30 polígonos y suma sus índices. No se suman escenarios entre sí como si fueran terrenos adicionales. La variación mezcla geometría, referencia y búsqueda; no estima incertidumbre en compras ni predice supervivencia. El procedimiento se adapta a cada geometría, no es una única decisión robusta previa.

Las coordenadas son metros locales inventados, sin orientación ni referencia geográfica real. No se construye un mapa global uniéndolas. Faltan contornos reales, topografía, suelo, agua e inventarios inciertos.

## Presupuesto: validación individual, sin reparación de cuotas

La presentación del socio formador (diapositiva 18) da **12500 u.m./ha**, sin moneda explícita:

$$B_p=12500A_p,\quad C_p=\sum_s c_sq_{ps},\quad saldo_p=B_p-C_p,\quad utilizado_p=100C_p/B_p.$$

Se verifica C_p≤B_p para **cada** polígono. Con cuotas fijas, C_p no depende del orden espacial ni del algoritmo. Se agrega `presupuesto_um`, `costo_um`, `saldo_um`, `presupuesto_utilizado_pct`, `cumple_presupuesto` y `estado_presupuesto`.

**24/30 cumplen; seis no:**

|Polígono|Presupuesto u.m.|Adquisición u.m.|Déficit u.m.|
|---|---:|---:|---:|
|P5|100000|100563|563|
|P9|88875|88983|108|
|P10|76375|76877.5|502.5|
|P12|61500|61620|120|
|P18|67500|68055.5|555.5|
|P23|95875|96603|728|

El presupuesto agregado es **2287625 u.m.**, frente a **2279608 u.m.** de plantas; el saldo agregado **8017** no implica cumplimiento individual ni autoriza transferencias. Los déficits individuales suman **2577**. P1 cumple: 16000 disponibles, 15903.5 de costo, saldo 96.5.

`estado=ok` indica ejecución espacial correcta. Un polígono puede ser `ok` y `cumple_presupuesto=False`: su asignación es válida espacialmente pero **inviable si se impone presupuesto obligatorio con esas cuotas**. No se ocultan ni se corrigen automáticamente esos casos. Falta incluir transporte, mantenimiento, riego y reposición: el cumplimiento calculado es solo de adquisición.

### Diagnóstico de flexibilidad, no aplicado

Las diapositivas 13 y 15 permiten variaciones de hasta ±10% manteniendo la cantidad total. Se estudia explícitamente la banda sobre las **cuotas finales enteras actuales**:

$$\max(n_{ps},\lceil0.9R_{ps}\rceil)\le R'_{ps}\le\lfloor1.1R_{ps}\rfloor,\quad \sum_sR'_{ps}=T_p.$$

`diagnostico_flexibilidad_10.csv` presenta el costo mínimo en esa banda. El cálculo llena límites inferiores y asigna el resto a costos crecientes; con una igualdad de total y capacidades enteras da el mínimo por argumento de intercambio, contrastado con programación lineal independiente. En esta interpretación los 30 podrían caber aritméticamente en B, incluidos los seis deficitarios.

**No se aplica al modelo**: se preservan R, q y todas las asignaciones del experimento. Mantener bandas, densidad e inventarios no certifica condiciones ecológicas equivalentes ni un J menor. Debe confirmarse la referencia exacta del ±10% con el socio e incorporar requisitos ecológicos verificables. Un futuro modelo tendría que decidir R', imponer presupuesto, mantener existentes y total y revalidar/integrar la asignación espacial; no basta intercambiar etiquetas con cuotas fijas.

## Resultados individuales y globales

```text
resultados/
├── P1/ ... P30/
│   ├── distribucion.csv
│   ├── comparacion.csv
│   ├── monte_carlo.csv
│   ├── estadisticas_mc.csv
│   └── graficas/01_existentes.png ... 04_monte_carlo.png
└── modelo_completo/
    ├── resumen_global.csv
    ├── resultados_por_poligono.csv
    ├── presupuesto_por_poligono.csv
    ├── estadisticas_monte_carlo.csv
    ├── diagnostico_flexibilidad_10.csv
    ├── cuotas_30.csv
    ├── configuracion.json
    ├── validacion.json
    └── graficas/01_comparacion_global.png ... 05_distribucion_mejoras.png
```

- **Distribución individual:** coordenadas y especies del escenario 0, no de un escenario promedio; las existentes están identificadas.
- **Comparación individual:** tres etapas técnicas del escenario 0 y presupuesto; en las gráficas principales solo dos procedimientos.
- **Monte Carlo individual:** todos los escenarios con estado y detalle, J_base/J_dsatur/J_final, costos, presupuesto y estadísticas de búsqueda. Las estadísticas indican completados/excluidos. Si falla el escenario 0 se retiran solo sus archivos generados conocidos para evitar mostrar una distribución vieja como nueva.
- **Resumen global:** una fila por escenario esperado, con número de polígonos completados y faltantes. Solo con 30/30 se publica el agregado; si es incompleto, J queda vacío y no entra en estadísticas ni gráficas de J global. Un fallo de presupuesto no es un fallo de simulación: se conserva con indicador económico explícito.
- **Por polígono:** cantidades y economía fijas; índices y mejora son **medias entre escenarios completados**. La media de porcentajes y la reducción calculada sobre J medio son columnas distintas. No se promedia sin indicar denominadores.
- **Estadísticas globales:** media, desviación estándar muestral (ddof=1), mínimo, máximo y conteos de escenarios completos/excluidos. Son descriptivas, no intervalos de confianza. La mejora media global promedia razones por escenario; la gráfica de barras promedia J. Esas dos operaciones no son necesariamente equivalentes.
- **Manifiesto:** parámetros, matriz C, orden de especies, esquema de semillas, versiones y huellas SHA-256 de entradas.

Las cinco figuras globales muestran: media de J agregado para dos procedimientos; reducción media por polígono con n; J agregado por escenario; presupuesto y costo por polígono con déficits señalados; distribución de mejoras de escenarios globales. No representan probabilidades de supervivencia.

Los cuatro resúmenes antiguos de la raíz (`resumen_30_poligonos.csv`, `resumen_global.csv`, `cuotas_30.csv`, `configuracion.json`) se sustituyen por los archivos explícitos de `modelo_completo/`. Las versiones anteriores y gráficas de tres métodos se recuperan en el historial Git, anterior a este cambio (base `fa888eefea118c154f6ada52145c7fc5ee6298ec`). Las 30 distribuciones del escenario 0 son idénticas byte a byte a la base: se conservan sus PNG de existentes y distribución final para evitar cambios binarios de estilo sin cambios de datos. Se actualizan las gráficas de comparación y Monte Carlo. No se elimina información de entrada ni archivos del algoritmo genético.

## Validación y límites

`python tests/verificar_modelo.py` ejecuta nueve pruebas rápidas opcionales: regresión P1, restricciones y deltas, reproducibilidad, presupuesto por polígono, mínimo económico contrastado, agregados incompletos/duplicados, dos métodos en las figuras y fallos controlados. El notebook sigue siendo la interfaz principal; el verificador no lanza el lote de 360 corridas.

**Ejecución efectivamente verificada en esta actualización:** 360/360 corridas (12 por cada uno de los 30), 12/12 escenarios globales completos, cero fallos y omisiones. Media de J agregado: aleatoria **161729.153384**, final **134334.030467**. Reducción media entre escenarios **16.938821%**, desviación estándar **0.074640 puntos porcentuales**, rango **16.830560%–17.054963%**. La máxima diferencia contra las 360 filas históricas es **4.55×10⁻¹³** (redondeo/serialización, tolerancia 1e-8); no se alteraron las heurísticas. P1, escenario 0: J aleatoria 1089.006627, DSATUR interno 991.747705 y final 874.525183. Se verificaron también los 240 archivos individuales y el modo de un único polígono (P1, dos escenarios). Las nueve pruebas rápidas pasan.

La evidencia exacta de la ejecución de esta actualización se guarda en `modelo_completo/validacion.json`: escenarios realmente ejecutados, regresión contra las 360 filas históricas, archivos generados y resultados de pruebas. Al volver a ejecutar se regenera ese registro con las validaciones integradas de la nueva corrida; no se heredan como ejecutadas pruebas rápidas o regresiones de una ejecución anterior. El notebook guardado contiene salidas ejecutadas. La ejecución en este entorno usa IPython en proceso; un kernel externo de Jupyter y el HTML integral no se dan por verificados sin una comprobación adicional en un entorno con sockets y navegador. Las figuras PNG se inspeccionan por separado.

Pendientes: geometría y recursos medidos, C calibrada, P13=5.05 ha y relación mapa-tabla, decisión real de cuotas flexibles con presupuesto obligatorio, inventario desconocido y compras estocásticas, costos integrales y optimalidad certificada. Menor J no demuestra mayor supervivencia. No se añaden Markov ni optimización conjunta de posiciones y especies.
