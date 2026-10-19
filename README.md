# Optimización estocástica — Reforestación

Proyecto universitario de distribución de diez especies para reforestación, a partir del reto presentado por el socio formador. **El archivo principal es [modelo_reforestacion.ipynb](modelo_reforestacion.ipynb).** No se necesita ejecutar scripts separados ni correr pruebas automatizadas para utilizarlo.

## Cómo ejecutar el notebook

1. Descargar o clonar **todo** el repositorio; no basta con descargar el archivo `.ipynb`, porque importa funciones de `reforestacion/` y lee archivos de `data/` y `config/`.
2. Abrir la carpeta raíz en VS Code o Jupyter con Python y ejecutar `python -m pip install -r requirements.txt` en una terminal.
3. Abrir `modelo_reforestacion.ipynb`, revisar las opciones de la **primera celda de código** y ejecutar todas las celdas de arriba hacia abajo. La carpeta de trabajo debe ser la raíz del proyecto.

Configuración central:

- `POLIGONOS = 1`: resuelve ese polígono; puedes cambiar el entero por cualquier ID de 1 a 30 (por ejemplo, `25`).
- `POLIGONOS = "todos"`: resuelve automáticamente los 30 en la sección 15, sin editar más celdas. El detalle paso a paso y las gráficas corresponden al primero de la selección (P1 en este modo).
- `ESCENARIOS_MC = 12`: escenarios Monte Carlo espaciales (usar 2 para una corrida más rápida).
- `EJECUTAR_COMPARACION_PRESUPUESTOS = False`: comparación opcional de propuestas fijas/proporcionales.
- `ESCENARIOS_LOTE = 1`: escenarios por polígono cuando se selecciona `"todos"`; independiente del Monte Carlo detallado. Se mantienen límites de 20000 plantas por polígono y 360 corridas por lote; excesos o fallos se reportan.

Las gráficas y tablas de P1 se encuentran en [resultados/](resultados/). Las ejecuciones generan allí sus salidas, sin necesidad de otros programas. La comparación de presupuestos queda desactivada por defecto. La ejecución de todos depende únicamente de `POLIGONOS = "todos"`. Las figuras de otras selecciones se guardan en subcarpetas para conservar la referencia P1.

## Estructura simplificada

| Ruta | Función |
| --- | --- |
| `modelo_reforestacion.ipynb` | **Interfaz principal**; explica formulación, cálculos, escenarios y conclusiones |
| `data/especies.csv` | Catálogo de especies, metas y costos |
| `data/inventario.csv` | Inventarios y áreas de los 30 polígonos |
| `data/supervivencia_porcentajes.csv` | Contexto histórico, no usado para predecir supervivencia |
| `data/fuentes_sha256.json` | Huellas de las fuentes documentales originales |
| `config/competencia.json` | Matriz provisional de competencia, sustituible sin modificar los algoritmos |
| `reforestacion/` | Módulos auxiliares de datos, geometría, algoritmos, validación, experimentos y visualización |
| `resultados/` | Cuatro figuras principales y CSV representativos de P1 |
| `requirements.txt` | Dependencias de Python |

Las carpetas `scripts/`, `tests/` y `docs/`, además de la evidencia detallada de experimentos antiguos, se retiraron **solo de la rama actual para simplificarla**. Pueden recuperarse con el historial de Git: no se modificó ni se reemplazó la heurística.

## Modelo y decisiones

Para cada polígono se construye un rectángulo de área equivalente y se simulan las coordenadas de las plantas existentes; después se seleccionan posiciones nuevas mediante una malla triangular. **No son posiciones medidas ni un plano georreferenciado**. El grafo conecta posiciones con distancia de hasta 6 m; cada arista contribuye con un peso dependiente de la distancia y del par de especies.

Se minimiza el índice de competencia

\[
J=\sum_{\{i,j\}\in E_p}\max(0,1-d_{ij}/r)\,C_{s_i,s_j}.
\]

Las cantidades finales y las especies existentes quedan fijas. Se comparan (1) asignación aleatoria factible, (2) DSATUR adaptado y (3) DSATUR seguido de búsqueda local por intercambios que solo acepta reducciones de J. Los tres enfoques usan los mismos sitios y cuotas en cada escenario. La matriz C predeterminada supone 3 para la misma especie, 2 para especies distintas del mismo género y 1 para géneros distintos; **no es una medición ecológica**.

El Monte Carlo del notebook repite escenarios **espaciales** con conteos existentes constantes. No simula aún inventarios inciertos ni determina probabilísticamente cuántas plantas comprar.

## Resultados de referencia, validados antes de la limpieza

- **P1, escenario 0:** 165 existentes, 677 nuevas, 842 totales. J aleatoria **1089.006627**, DSATUR **991.747705**, DSATUR + local **874.525183**; mejora **19.6951 %** frente a aleatoria.
- **P1, 12 escenarios:** 12/12 completados; mejora promedio del índice **20.1518 %**. Las corridas reproducibles mantienen la semilla y el método originales.
- **30 polígonos, un escenario cada uno:** 30/30 completados; 23,569 existentes, 96,850 nuevas, 120,419 en total; reducción agregada del índice **16.8401 %**. **No** se ejecutaron doce escenarios para cada polígono.
- La versión anterior reportó **15 pruebas automatizadas exitosas**. Su código y resultados permanecen en el historial Git. Esta simplificación no constituye una nueva ejecución de esa batería.

## Limitaciones y pendientes

La menor competencia *del índice provisional* no prueba una mayor supervivencia real. Faltan coordenadas de campo, una matriz de competencia calibrada, topografía y suelo, cuota flexible por especie (±10 %), compras bajo inventario desconocido y evaluación económica integral. Los costos del catálogo son unidades monetarias sin moneda especificada por la fuente. La interpretación de P13 = 5.05 ha y la correspondencia entre IDs de polígonos y el mapa requieren confirmación.

**Nota:** el notebook principal no está diseñado para ejecutarse aislado de las carpetas `data/`, `config/` y `reforestacion/`.

