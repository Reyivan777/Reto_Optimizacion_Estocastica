# Validación de optimización económica + DSATUR

Base: `75a54abc199563471bec29bba051da3d1d483e8b` (main). Solo DSATUR.

## Resultados económicos

30/30 económicamente factibles; 30/30 con ambos pasos MILP certificados por el solver, gap cero. Solo seis polígonos cambian. Los otros 24 mantienen exactamente R. Se validaron total, banda ±10%, integridad, inventario y presupuesto decimal sin ampliación por tolerancias.

|Polígono|Presupuesto|Costo fijo|Costo ajustado|Ahorro|
|---|---:|---:|---:|---:|
|P5|100,000.00|100,563.00|99,995.00|568.00|
|P9|88,875.00|88,983.00|88,871.00|112.00|
|P10|76,375.00|76,877.50|76,373.50|504.00|
|P12|61,500.00|61,620.00|61,500.00|120.00|
|P18|67,500.00|68,055.50|67,495.50|560.00|
|P23|95,875.00|96,603.00|95,875.00|728.00|

Adquisición total: **2,279,608.00 → 2,277,016.00 u.m.** Ahorro **2,592.00 u.m.** No se transfieren recursos entre polígonos. Los planes completos están en `resultados/ejecuciones/validacion_30_20261019T060618_054822Z/poligonos/`, y las 300 filas de cuotas en `resultados/ejecuciones/validacion_30_20261019T060618_054822Z/cuotas.csv`.

## Comparación espacial completa

**360/360 pares válidos**, 30 polígonos × 12 escenarios; geometría y etiquetas existentes idénticas en cada par. Se verifican compras mediante el histograma de la asignación final y J_final <= J_dsatur. Se ejecutaron 360 referencias fijas y 72 corridas económicas adicionales; 288 resultados económicos reutilizan la referencia de la misma ejecución porque las cuotas no cambian. No son 720 simulaciones espaciales independientes.

- Media de J final agregado con cuotas fijas: **134334.030467156**.
- Media de J final agregado económico: **134051.545469848**.
- Media del cambio porcentual pareado: **-0.210287%** (negativo = menor competencia).
- Desviación estándar muestral entre los 12 cambios porcentuales: **0.015920 puntos porcentuales**.
- Comparaciones individuales con incremento de J: **5/360**. Minimizar desviación económica no garantiza menor competencia para cada realización.

Los totales se calculan solo con los 30 polígonos del mismo escenario. `resultados/ejecuciones/validacion_30_20261019T060618_054822Z/comparacion_global.csv` contiene 12 filas; `comparacion_pareada.csv`, 360. No se suman escenarios como si fueran terrenos distintos ni se mezclan los resultados del notebook (un escenario) con estas medias de doce.

## Tiempos y rendimiento

Validación con seis procesos independientes y librerías fijadas en `config/requirements.txt`:

- Tiempo de pared hasta exportar tablas: **381.784 s**; la figura comparativa se genera después.
- Economía, suma de los 30 problemas: **1.213 s**.
- Etapa espacial fija, tiempo acumulado de trabajadores: **1615.998 s**.
- Etapa espacial económica adicional, tiempo acumulado: **323.593 s**.

Los tiempos acumulados concurrentes no equivalen a tiempo de pared. La reutilización evita 288 llamadas duplicadas en esta comparación. No se afirma una aceleración porcentual de tiempo contra un experimento serial no medido. No se cambiaron selección de posiciones, construcción del grafo, DSATUR, deltas ni búsqueda local.

El notebook ejecutó por separado 30 pares con un escenario, con gráficos individuales: `resultados/ejecuciones/20261019T060401_348519Z_economico/`. Las 30 distribuciones de ese escenario son idénticas byte a byte a las del validador paralelo. Las distribuciones CSV pueden consultarse allí. Se conservan las gráficas comparativas PNG y las seis figuras embebidas del notebook. Los 124 PNG individuales generados durante la prueba serial/tutorial se omiten del commit por redundancia; se regeneran con el ejecutor (sin --sin-graficas). No se eliminó ningún PNG histórico.

## Pruebas efectivamente realizadas

- Nueve pruebas originales: pasan, incluida regresión P1, deltas, reproducibilidad, fallos y reportes.
- Seis pruebas nuevas: pasan; verifican los 30 problemas económicos, mínimo contra diagnóstico anterior, óptimo lexicográfico contra enumeración exhaustiva pequeña, ceros, inventario incompatible, presupuesto imposible y en frontera, rechazo de fracciones, límite del solver, integración P5, geometría, compras, errores, omisiones y carpetas únicas.
- Regresión de **360 filas originales**, mismos parámetros y semillas: máximas diferencias absolutas {'J_base': 0.0, 'J_dsatur': 0.0, 'J_final': 0.0} (tolerancia de comparación 1e-8, no monetaria).
- **253 archivos históricos** comprobados por SHA-256 y preservados. Referencias en `referencia_historica.json`.
- 30 distribuciones económicas del escenario cero iguales entre ejecución serial y paralela.
- Formato del notebook válido: 17 celdas de código ejecutadas, todas con salidas, cero errores guardados y seis PNG embebidos.
- Notebook ejecutado de principio a fin con IPython en proceso; posteriormente se regeneró la gráfica de saldos desde CSV y la celda final de agregados para marcar escenarios incompletos. No se repitieron simulaciones por cambios de presentación.
- CSV, índices, estados y gráficas comparativas inspeccionados. HTML del notebook generado; no se afirma inspección integral del HTML en navegador.

## Límites y pruebas pendientes

El kernel externo Jupyter no pudo iniciarse: el entorno impidió abrir sus sockets. La ejecución en proceso sí terminó. Para verificar el kernel externo en un equipo sin esa restricción: `python -m jupyter nbconvert --execute --to notebook --inplace modelo_reforestacion.ipynb` desde `DSATUR/` (el notebook guardado usa un escenario; cambiar ESCENARIOS_LOTE a 12 para repetir el completo en él).

La banda ±10% sobre cuotas finales originales sigue pendiente de confirmación del socio. Los costos solo cubren adquisición. Geometría simulada, C provisional, restricciones ecológicas no calibradas y supervivencia no modelada. El MILP tiene certificación numérica de HiGHS; no se afirma optimalidad espacial. La imposibilidad de construir la malla se distingue de una prueba de inviabilidad en todo el terreno. No hay pruebas pendientes del lote de 360 pares solicitado.

## Archivos implementados

`src/reforestacion/optimizacion_economica.py`: MILP, validación exacta y vista de cuotas.
`src/reforestacion/dos_etapas.py`: ejecución, comparación, estados y exportación.
`scripts/ejecutar_dos_etapas.py`: CLI de ambos modos y economía independiente.
`tests/verificar_economia.py`: pruebas económicas y de integración.
`scripts/validar_lote_economico.py`: validación completa paralela y regresión histórica.
Notebook, README, comentario de dependencia MILP en requirements, referencia histórica y resultados nuevos.

Los módulos espaciales originales y los datos permanecen intactos. No se modificó ningún archivo del algoritmo genético.
