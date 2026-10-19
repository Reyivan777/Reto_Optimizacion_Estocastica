# Resultados organizados por polígono

El notebook principal está en [modelo_reforestacion.ipynb](modelo_reforestacion.ipynb). Los archivos de entrada siguen en `data/`, `config/` y el código en `reforestacion/`.

## Cómo ejecutar

Desde la raíz: `python -m pip install -r requirements.txt`. Luego abre el notebook en Jupyter o VS Code. En su primera celda usa:

```python
POLIGONOS = "todos"
ESCENARIOS_MC = 12
ESCENARIOS_LOTE = 1
EJECUTAR_COMPARACION_PRESUPUESTOS = False
```

Ejecuta todas las celdas. La sección 15 guarda en `resultados/` un resumen por polígono, un resumen global y la configuración, y escribe en `resultados/P1/` a `P30/` las distribuciones y gráficas generadas para el escenario 0. El ejemplo detallado (secciones anteriores) corresponde a P1 cuando se seleccionan todos.

## Estructura de `resultados/`

- `resumen_30_poligonos.csv`: una fila por polígono y escenario, con estado, cantidades, J, costo y mejora.
- `resumen_global.csv`: suma de los polígonos terminados para cada escenario.
- `cuotas_30.csv`: áreas y metas de las 30 parcelas.
- `configuracion.json`: parámetros y matriz de competencia usados.
- `P1/`: `distribucion.csv`, `comparacion.csv`, `monte_carlo.csv`, `estadisticas_mc.csv` y `graficas/`.
- `P2/`–`P30/`: `comparacion.csv` histórica y `graficas/03_comparacion.svg` histórica. El notebook genera `distribucion.csv` y las tres figuras PNG al **volver a ejecutar** `POLIGONOS = "todos"`.

**Distinción importante:** el historial conservó las métricas de los 30 polígonos, pero solo había exportado las coordenadas y etiquetas de P1. Las distribuciones P2–P30 no están inventadas ni reconstruidas desde los valores J. El cuaderno ahora las genera nuevamente con la misma semilla cuando se ejecuta.

## Lectura de `resumen_global.csv`

`escenario=0` es la primera simulación espacial. `existentes` son plantas inventariadas, `nuevas` la cantidad por añadir y `total` su suma. `J_base`, `J_dsatur` y `J_final` son los índices de competencia de aleatoria, DSATUR y DSATUR + búsqueda local; menor es mejor según la matriz provisional. `costo_um` representa solo adquisición, sin moneda confirmada. `mejora_pct = 100(J_base-J_final)/J_base`. `poligonos_completados` registra cuántos tuvieron estado `ok`.

En la ejecución histórica del escenario 0 se completaron **30/30**, con **23,569 existentes + 96,850 nuevas = 120,419**, `J_base=161430.286548`, `J_dsatur=146407.918776`, `J_final=134245.194845`, **16.8401%** de mejora del índice y costo **2,279,608 u.m.**. No representa 12 escenarios en cada polígono.

## Límites

Las posiciones son simuladas en rectángulos de área equivalente, no mediciones GPS; la matriz de competencia 3/2/1 es provisional, y la simulación no estima todavía la compra cuando los inventarios sean desconocidos. Reducir J no demuestra mayor supervivencia real. El archivo histórico anterior permanece en Git.
