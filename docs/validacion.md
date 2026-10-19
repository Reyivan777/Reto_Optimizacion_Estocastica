# Validación y control de cambios

## Base y alcance

Base inspeccionada: `main`, commit `53c13a98636e77c51e77ed81110588b6df3f3a1d`. Primero se leyó el README completo; después notebook, datos y salidas. El README mencionaba scripts ausentes: ambas rutas `scripts/crear_notebook.py` y `scripts/ejecutar_notebook.py` devolvieron 404. No había `sources/`. No se reconstruyeron documentos originales ni se reextrajeron CSV. Los adjuntos Datos-Reto y Entregable 2 y los pasajes pertinentes de la presentación se usaron como contexto; no sustituyen el historial de los datos.

Se ejecutaron las funciones del notebook original antes de extraerlas, sin sus celdas de escritura. Se protegió una copia del notebook antes de reorganizarlo. El historial Git mantiene el original íntegro. La implementación nueva conserva funciones geométricas, orden de especies y aristas, desempates DSATUR, flujos aleatorios y tolerancia local.

## Archivos y nueva estructura

- `modelo_reforestacion.ipynb`: 16 secciones, 34 celdas, 17 de código; explicación antes del cálculo, notación, tablas de símbolos y ejemplo P1. Cuatro figuras incrustadas. Las funciones DSATUR, objetivo y búsqueda local se muestran desde su fuente real, evitando duplicar implementaciones divergentes.
- `reforestacion/{config,datos,geometria,algoritmos,validacion,experimento,visualizacion}.py` y `__init__.py`: separación simple entre entradas, sitios, asignaciones, validación, orquestación y presentación.
- `config/competencia.json`: coeficientes explícitos provisionales y orden de especies; intercambiables por otro JSON.
- `scripts/ejecutar_modelo.py`: selección individual/lista/todos, perfiles y presupuesto fijo/proporcional.
- `scripts/ejecutar_notebook.py`: ejecución y HTML en archivos nuevos; no sobrescribe el notebook fuente. `--sin-kernel` permite ejecutar con IPython sin sockets.
- `scripts/crear_notebook.py`: copia del notebook canónico a una ruta nueva; rechaza sobrescritura, no regenera desde fuentes faltantes.
- `tests/test_modelo.py`: 15 pruebas; `README.md`, este informe y `.gitignore`.
- `resultados/refactorizacion/`: figuras y comparación P1, distribución, estadísticas, lotes/MC/presupuestos y evidencia de pruebas. Resultados directamente bajo `resultados/` permanecen históricos y no se reemplazan.

## Cambios de lógica y decisiones numéricas

**No se reemplazaron la selección geométrica, DSATUR ni la regla de intercambios.** Se corrige la formulación escrita: una posición nueva seleccionada exige `sum_s x_pis = 1`, no `≤1`. La implementación anterior ya ocupaba todos esos sitios.

La búsqueda mantiene `delta < -1e-10`, que cumple aceptar únicamente descensos negativos y descarta empates numéricos. Se experimentó con `<0` estricto: P1 final pasó a 874.453102755 por aceptar diferencias de redondeo casi nulas y cambiar la trayectoria. Esa modificación fue descartada; no forma parte del algoritmo entregado.

Cambios efectivos:

1. Contadores de propuestas, iguales, evaluados, aceptados y rechazados; J inicial/final, porcentaje de reducción local y tiempo. Menos de dos posiciones movibles implica cero propuestas realizadas, aunque se solicite un presupuesto mayor.
2. Punto final de trayectoria en la última propuesta, incluso si no se acepta, para mostrar la meseta completa; no añade un intercambio ni cambia J.
3. Configuración sin estado global del notebook, matriz externa y perfiles/lotes con límites explícitos. Matriz exactamente simétrica (no se tolera asimetría numérica), requisito de la fórmula que omite la arista entre los sitios intercambiados. Se validan además dimensión, finitud, no negatividad y orden de especies.
4. Fallos de construcción y validación por escenario se reportan como `fallo`; exceder un límite de recursos como `omitido`. No se sustituyen escenarios. Configuraciones inválidas globales (p. ej. matriz o selección malformada) fallan antes del lote.
5. Agregados por escenario, con número de polígonos completados. No se suman múltiples escenarios como si aumentaran la superficie real.

## Entorno y comandos efectivamente ejecutados

Entorno virtual nuevo, Python 3.12.10. Instalación correcta con los nueve paquetes fijados de `requirements.txt`: numpy 2.5.4, pandas 3.0.6, scipy 1.18.1, matplotlib 3.11.2, networkx 3.7, nbformat 5.11.1, nbclient 0.11.0, nbconvert 7.17.2 e ipykernel 7.4.0. Los manifiestos de cada lote registran versiones y configuración, incluida C completa.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r repo/requirements.txt
# Desde repo/ y usando el intérprete del entorno:
python -m unittest discover -s tests -v
python scripts/ejecutar_notebook.py --sin-kernel
python scripts/ejecutar_modelo.py --perfil completo --poligonos todos --escenarios 1 --salida resultados/refactorizacion/lote_30
python -m compileall -q reforestacion scripts tests
```

Los comandos se adaptaron a las rutas locales; no requieren VS Code. Las **17 celdas de código se ejecutaron secuencialmente con IPython en proceso**, sin errores, y se guardó el notebook ejecutado como entregable canónico. Se validó su formato nbformat y se exportó HTML. Se inspeccionaron visualmente las cuatro figuras PNG: leyendas, unidades, marcas y valores. También se generaron los cinco diagnósticos opcionales y se revisó la trayectoria local.

**Límite de verificación:** este entorno bloqueó sockets TCP e IPC de Jupyter; por tanto no se completó ejecución con kernel externo nbclient. El navegador Chromium de Playwright no estaba instalado: el HTML completo y el renderizado matemático en navegador no se inspeccionaron visualmente. La ejecución en proceso y la revisión de figuras no se presentan como esas comprobaciones. Para completar ambas: `python scripts/ejecutar_notebook.py` en un entorno que permita sockets y abrir el HTML resultante.

## Pruebas automatizadas: 15 correctas

|Prueba|Evidencia|
|---|---|
|Regresión P1|J de los tres métodos a tolerancia absoluta 1e-8 y conteos 165/677/842|
|Cuotas 30|23,569 existentes, 120,419 finales, 96,850 nuevas|
|Objetivo independiente|Suma directa de aristas NetworkX coincide con evaluación vectorizada|
|Deltas|375 intercambios contrastados con recálculo completo, incluidos pares adyacentes, C original, alternativa y cero|
|Conservación|Especies existentes, cuotas y coordenadas iguales; separación ≥3.4 m|
|Reproducibilidad|Repetición exacta de coordenadas, tres asignaciones y trayectoria|
|Matriz alternativa|Ejecución completa con C simétrica aleatoria, guardada y recargada desde JSON|
|Matrices inválidas|Rechaza dimensión incorrecta, NaN, infinito, negativos y asimetría|
|Estadísticas|Identidades de contadores y trayectoria monótona hasta propuesta 6000|
|Sin nuevas/sin aristas|Sin movimientos y J=0 en ejemplo pequeño sin interacciones|
|Fallos y recursos|Dos fallos controlados y treinta omisiones controladas, con motivos|
|Selección/presupuestos|Un ID, lista, todos; rechazo de duplicados/IDs inválidos; 6770 propuestas proporcionales|
|Otros polígonos|P4 y P25 completos con restricciones verificadas|
|Datos inválidos|Duplicados, conteos negativos, áreas infinitas, especies desconocidas e inventario superior a cuota|
|Protección de notebook|Copiador rechaza archivo existente sin alterar su contenido|

El registro de ejecución se conserva en `resultados/refactorizacion/pruebas/unittest.txt`. Los fallos/omisiones deliberados tienen CSV separados y no se mezclan con los resultados válidos.

## P1 frente al original

|Método|Antes|Después|Cambio|
|---|---:|---:|---:|
|Aleatoria|1089.006627233044|1089.006627233044|0|
|DSATUR|991.7477053447574|991.7477053447574|0|
|DSATUR + local|874.5251827583863|874.5251827583863|0|

Se compararon con la ejecución original los arrays completos: coordenadas, referencia aleatoria, DSATUR y asignación final **idénticos**. La historia aceptada es idéntica; solo se añade la meseta terminal. `pruebas/regresion.json` registra esta comprobación. Los J, término FF, reducción y costo de los **12 escenarios** también coinciden con los CSV históricos: máxima diferencia observada **0.0**.

P1 conserva adquisición **15903.5 u.m.** y mejora del índice **19.6951459%** frente a referencia. Monte Carlo **12/12**, media **20.151811%**, desviación estándar **0.722148 puntos porcentuales**. No son mediciones de supervivencia.

## Presupuesto de propuestas

Comparación pareada, mismas semillas y escenario; factor proporcional 10:

|Escenario P1|J con 6000|J con 6770|
|---|---:|---:|
|0|874.525183|872.195791|
|1|885.377297|881.048983|
|2|892.097343|889.860662|

Los tiempos por corrida se guardan en `presupuesto_fijo/escenarios.csv` y `presupuesto_proporcional/escenarios.csv`; dependen de la máquina y carga. El ensayo demuestra funcionamiento del parámetro y mejoras en estas tres corridas, no una regla universal de suficiencia del presupuesto ni optimalidad local.

## Escala y polígonos efectivamente ejecutados

Primero P4 (1.38 ha, 908 plantas) y P25 (4.19 ha, 2757 plantas), escenario 0:

|Polígono|Aleatoria|DSATUR|DSATUR + local|
|---|---:|---:|---:|
|P4|1189.669808|1062.972001|962.737283|
|P25|3670.716294|3330.173506|3035.474479|

Después se ejecutó **P1–P30**, escenario 0 de cada uno, C original, 6000 propuestas. **30/30 ok, 0 fallos, 0 omisiones**. Aproximadamente **37.69 s** sumados, intervalo observado 0.155–2.019 s por polígono. No incluye instalación, carga del intérprete ni exportaciones; no es una cota de complejidad. No se ejecutaron 360 escenarios.

|Agregado escenario 0|Resultado|
|---|---:|
|Existentes|23,569|
|Nuevas|96,850|
|Total final|120,419|
|J aleatoria|161430.286548|
|J DSATUR|146407.918776|
|J final|134245.194845|
|Reducción frente a aleatoria|16.840143%|
|Adquisición|2279608.0 u.m.|

Evidencia por polígono y estadísticas locales: `lote_30/escenarios.csv`; agregado: `lote_30/agregado.csv`; manifiesto: `lote_30/configuracion.json`. Las cuotas y restricciones se validan en cada ejecución, no solo en el agregado.

## Límites pendientes

- Kernel externo Jupyter y revisión visual integral del HTML, según límite del entorno descrito arriba.
- P1 tiene 12 escenarios; la prueba completa de los demás es de un escenario por polígono. Comparaciones amplias de presupuestos y optimización de rendimiento siguen pendientes.
- Cuotas, inventarios y adquisiciones son conocidos y fijos. No hay incertidumbre de compras, ±10%, optimización conjunta de sitios, supervivencia ni Markov.
- Rectángulo y coordenadas simulados, C y distancias provisionales: sin evidencia de eficacia ecológica. Confirmar P13 y relación mapa-tabla antes de aplicación de campo.
- Costos parciales, sin restricción presupuestal por hectárea ni óptimos certificados. No se introducen coeficientes científicos inventados.
