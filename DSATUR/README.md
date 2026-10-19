# Modelo DSATUR — Reforestación

El archivo principal es **[modelo_reforestacion.ipynb](modelo_reforestacion.ipynb)**. Abre **la carpeta DSATUR como carpeta de trabajo** en VS Code/Jupyter, porque el notebook lee las rutas relativas `data/`, `config/` y `reforestacion/`. La carpeta `Algoritmo Genético/` es un enfoque alternativo independiente.

## Ejecutar

En la terminal ubicada en `DSATUR/`: `python -m pip install -r requirements.txt`.

En la primera celda del notebook:
```python
POLIGONOS = "todos"    # o entero 1 a 30
ESCENARIOS_MC = 12     # Monte Carlo del polígono explicado paso a paso
ESCENARIOS_LOTE = 12   # 12 escenarios por cada uno de los 30 polígonos
EJECUTAR_COMPARACION_PRESUPUESTOS = False
```
Usa `ESCENARIOS_LOTE = 1` para probar más rápido; una sola corrida no proporciona una distribución Monte Carlo informativa. Con 12, la ejecución completa puede tardar varios minutos.

## Organización de resultados

Cada carpeta `resultados/P1/` a `resultados/P30/` contiene los mismos archivos:

```text
resultados/
├── resumen_30_poligonos.csv   # detalles de ejecuciones individuales
├── resumen_global.csv         # suma por escenario, no suma escenarios como terrenos
├── cuotas_30.csv              # meta e inventario por polígono
├── configuracion.json         # matriz y parámetros utilizados
├── P1/
│   ├── distribucion.csv       # x/y simuladas, especie y existente/nueva
│   ├── comparacion.csv        # aleatoria, DSATUR, DSATUR + búsqueda local
│   ├── monte_carlo.csv        # escenarios espaciales
│   ├── estadisticas_mc.csv    # resumen de simulación
│   └── graficas/
│       ├── 01_existentes.png
│       ├── 02_final.png
│       ├── 03_comparacion.png
│       └── 04_monte_carlo.png
├── P2/                        # mismos ocho archivos
└── ... P30/                   # mismos ocho archivos
```

La carpeta antigua `resultados/monte_carlo_p1/` ya no debe generarse. Si existe localmente, el notebook la elimina solamente cuando contiene los cuatro archivos de salida antiguos conocidos y ningún otro archivo; de lo contrario emite una advertencia.

## Interpretar el modelo

`J_base` es el índice de competencia de la distribución aleatoria, `J_dsatur` el de DSATUR adaptado y `J_final` tras búsqueda local. Menor J indica menos penalización bajo la matriz provisional, no supervivencia real demostrada. `costo_um` es el costo de adquirir nuevas plantas en unidades monetarias sin moneda confirmada. `mejora_pct` compara J final con aleatoria.

Con un escenario por polígono, el resultado histórico tiene 30/30 casos completos: 23,569 existentes, 96,850 nuevas, 120,419 totales, J aleatoria 161430.286548, J DSATUR 146407.918776 y J final 134245.194845, reducción de 16.8401%. Las posiciones son **simuladas**, no coordenadas reales de campo. Aún falta modelar inventarios desconocidos y compra estocástica.

La regeneración de todos los archivos es reproducible y también se puede realizar directamente desde el notebook.
