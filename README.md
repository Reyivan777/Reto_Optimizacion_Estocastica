# Reto de Optimización Estocástica — Reforestación

## Estado implementado y validado

Refactorización didáctica del prototipo de P1, basada en `main` **53c13a98636e77c51e77ed81110588b6df3f3a1d**. Se conserva la heurística, las cuotas y la simulación espacial; el código reusable ahora reside en módulos. El notebook contiene 16 secciones, tablas de símbolos, ejemplos P1 y cuatro figuras principales. No representa un plano georreferenciado ni demuestra mayor supervivencia.

**Resultados realmente ejecutados:**

- Entorno virtual limpio, instalación desde `requirements.txt`, Python 3.12.10; 15 pruebas automatizadas correctas.
- P1, escenario 0: **1089.006627 → 991.747705 → 874.525183** (aleatoria, DSATUR, DSATUR + local). Reducción de **19.6951%** frente a aleatoria. Coincide con el prototipo anterior.
- P1: **12/12 escenarios**; reducción media **20.1518%**, rango **19.2457%–21.2434%**. Los índices de los doce escenarios coinciden con las tablas históricas dentro de `1e-8`.
- Escala: primero P4 (908 plantas) y P25 (2757), un escenario cada uno. Después **30/30 polígonos** completados, **un escenario por polígono**, 6000 propuestas: J agregado **161430.286548 → 146407.918776 → 134245.194845**, reducción **16.8401%** frente a aleatoria. Aproximadamente 37.69 s sumados en esta máquina; no es garantía de rendimiento en otra.
- Los 30 conservan **23,569 existentes + 96,850 nuevas = 120,419**; superficie tabulada **183.01 ha**. No se han ejecutado 12 escenarios para cada uno de los 30.
- Comparación pareada P1, escenarios 0–2: 6000 propuestas frente a `10 × 677 = 6770`; el presupuesto proporcional redujo J en las tres corridas. No certifica superioridad general ni un óptimo.

Detalle, comandos, limitaciones de ejecución y cambios: [docs/validacion.md](docs/validacion.md). Evidencia nueva: `resultados/refactorizacion/`. Los CSV y PNG directamente en `resultados/` conservan los resultados **históricos** del prototipo.

## Datos y procedencia

- `data/especies.csv`: diez especies, metas por ha y costos unitarios.
- `data/inventario.csv`: 300 registros, diez especies para 30 polígonos, áreas y conteos conocidos.
- `data/supervivencia_porcentajes.csv`: contexto histórico; no se usa como C ni para predecir supervivencia.
- `data/fuentes_sha256.json`: huellas de documentos originales, no sus contenidos. **`sources/` no está en main ni es necesaria para ejecutar esta versión.** No se inventaron documentos ni se reextrajeron datos.

Se conservan las normalizaciones Opuntia engelmannii y Opuntia streptacantha, el orden del catálogo y P13=5.05 ha como interpretación editorial pendiente. Las etiquetas del mapa no necesariamente corresponden a los IDs P1–P30. El costo se expresa en unidades monetarias: la fuente no especifica moneda.

## Formulación matemática preservada

Para cada polígono p:

- P contiene 30 polígonos; S diez especies; F_p son coordenadas existentes simuladas, V_p coordenadas nuevas seleccionadas, U_p su unión y E_p los pares no dirigidos a distancia ≤ r. Cada arista se cuenta una sola vez. Las posiciones se almacenan como **(x,y)** en metros.
- A_p es el área; D=658 plantas/ha; T_p=floor(A_p D+0.5); n_ps es inventario, R_ps cuota final y q_ps=R_ps−n_ps adquisición conocida. Cuotas por restos mayores y desempate por orden del catálogo; se rechaza inventario superior a cuota.
- x_pis es binaria: especie s en posición nueva i. Para existentes y_pis=a_pis fijo; para nuevas y_pis=x_pis. Python representa cada fila one-hot con una etiqueta entera de especie, sin crear vectores de ocupación del terreno.

$$\min J=\sum_{p\in P}\sum_{\{i,j\}\in E_p}w_{pij}\sum_{s\in S}\sum_{t\in S}C_{st}y_{pis}y_{pjt},\qquad w_{pij}=\max(0,1-d_{pij}/r).$$

Restricciones: **exactamente una** especie por sitio nuevo; `n_ps + sum_i x_pis = R_ps`; `sum_s R_ps = T_p = |F_p|+|V_p|`; existentes inmutables; sitios dentro del terreno simulado y separados al menos d_min; variables binarias. Se corrige la desigualdad `≤1` del texto antiguo porque V_p contiene únicamente sitios seleccionados y todos se ocupan.

La selección geométrica ocurre **antes** de optimizar especies. Se usa rectángulo de área equivalente, separación 3.4 m, malla triangular y dispersión geométrica. Esos supuestos no son coordenadas medidas ni optimización conjunta. El radio supuesto de interacción es 6 m. J=J_FF+J_FV+J_VV; J_FF permanece constante en un escenario.

## Matriz de competencia intercambiable

`config/competencia.json` contiene una matriz explícita y el orden de especies. Se valida dimensión 10×10, simetría, finitud, no negatividad y correspondencia con el catálogo. Se conserva **3 misma especie / 2 especies distintas del mismo género / 1 distinto género** como criterio provisional. No son mediciones ecológicas.

Para sustituirla, editar sus coeficientes o pasar otro JSON mediante `--matriz`; no se modifica DSATUR ni búsqueda local. En una futura calibración podrían normalizarse requerimientos de agua y nutrientes y justificarse pesos con evidencia de campo. Esa estimación científica queda pendiente.

## Algoritmos y Monte Carlo

1. **Aleatoria:** permutación del multiconjunto de nuevas especies; conserva cuotas y sitios.
2. **DSATUR adaptado:** prioriza saturación, grado ponderado y menor índice. Elige especie por menor costo incremental, mayor cuota pendiente y menor índice. Repetir especie vecina está permitido y penalizado; no se minimiza el número de colores.
3. **DSATUR + local:** propone dos posiciones nuevas distintas, omite especies iguales y acepta solo ΔJ negativo. Se conserva la tolerancia numérica histórica `ΔJ < −1e−10`, que evita aceptar empates de coma flotante. No mueve existentes ni cambia cantidades. No certifica óptimo local o global.

Se registran propuestas, especies iguales, evaluados, aceptados, rechazados, J inicial/final, reducción porcentual y tiempo. `propuestas = iguales + evaluados`, `evaluados = aceptados + rechazados`. El diagnóstico de trayectoria tiene propuestas en X y J en Y; descensos son mejoras aceptadas y mesetas ausencia de mejora. Ahora incluye la meseta hasta la última propuesta.

Monte Carlo usa escenarios espaciales **completos** y semillas separadas `(semilla, polígono, escenario)`. En P1 cada escenario conserva **165 existentes y 677 nuevas**. La variación mezcla posiciones, referencia aleatoria y propuestas locales; no modela cantidades de compra desconocidas. Las estadísticas se condicionan a los completados; fallos y omisiones permanecen en el reporte. Doce escenarios son exploratorios y no validación ecológica.

## Estructura

|Archivo o carpeta|Responsabilidad|
|---|---|
|`modelo_reforestacion.ipynb`|Documento canónico ejecutado, 16 secciones: formulación → geometría → algoritmos → validación → resultados|
|`reforestacion/config.py`|Configuración, perfiles, selección y presupuestos|
|`reforestacion/datos.py`|Carga, validación, cuotas, lectura de C|
|`reforestacion/geometria.py`|Simular existentes, seleccionar sitios, construir grafo|
|`reforestacion/algoritmos.py`|Objetivo, referencia, DSATUR y deltas/intercambios|
|`reforestacion/validacion.py`|Restricciones de soluciones|
|`reforestacion/experimento.py`|Escenarios, lotes, estados, agregados y manifiestos|
|`reforestacion/visualizacion.py`|Cuatro figuras principales y cinco diagnósticos opcionales|
|`scripts/ejecutar_modelo.py`|CLI para uno, varios o todos los polígonos|
|`scripts/ejecutar_notebook.py`|Ejecuta una copia y exporta HTML sin sobrescribir el fuente|
|`scripts/crear_notebook.py`|Copia segura del notebook canónico a un archivo nuevo; no regenera desde sources/|
|`tests/test_modelo.py`|15 pruebas de propiedades y regresión|
|`docs/validacion.md`|Evidencias, diferencias y pendientes|

## Ejecución

Desde la raíz, Windows:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts/ejecutar_notebook.py
.venv\Scripts\python -m unittest discover -s tests -v
```

En Linux/macOS usar `.venv/bin/python`. El notebook espera la raíz del proyecto. Puede abrirse directamente en Jupyter/VS Code y ejecutar todas las celdas.

El ejecutor guarda `resultados/ejecucion_notebook/modelo_reforestacion_ejecutado.ipynb` y HTML; conserva el notebook fuente. Las celdas actualizan sus tablas/figuras en `resultados/refactorizacion/`, por lo que conviene usar una rama de trabajo. Si no se permiten sockets de kernel, existe `python scripts/ejecutar_notebook.py --sin-kernel`: ejecución secuencial en IPython dentro del mismo proceso. Fue el modo efectivamente validado aquí.

Sin abrir Jupyter:

```bash
python scripts/ejecutar_modelo.py --poligonos 1 --escenarios 2
python scripts/ejecutar_modelo.py --poligonos 4,25 --escenarios 1
python scripts/ejecutar_modelo.py --poligonos 1 --presupuesto proporcional --factor 10
python scripts/ejecutar_modelo.py --perfil completo --poligonos todos --escenarios 1 --salida resultados/prueba_30
```

En Python, `Config(poligonos=1)`, `Config(poligonos=(4,))`, `Config(poligonos=(1,4,25))` o `Config(poligonos='todos')`. `Config()` conserva 12 escenarios P1 y 6000 propuestas. `perfil('rapido')`: 2 escenarios, máximo 4000 plantas por polígono y 24 corridas; `perfil('completo')`: 12 escenarios, 20000 plantas y 360 corridas. No se ejecuta un lote completo sin solicitarlo. Los límites generan estado **omitido**, distinto de **fallo** de construcción/validación; el CLI devuelve código 1 si hay alguno. No se relajan restricciones ni se reemplazan escenarios fallidos.

Para una copia editable adicional: `python scripts/crear_notebook.py --destino copia_modelo.ipynb`. Rechaza destinos existentes y no reconstruye el notebook con un generador. Los dos scripts mencionados en el README anterior no estaban realmente presentes en la rama inspeccionada: estos son implementaciones nuevas y autocontenidas.

## Pendiente y fuera de alcance

- Calibración ecológica de C, contornos/coordenadas reales, topografía, suelo y distancias por especie.
- Confirmar P13 y correspondencia mapa-tabla. Las áreas suman 183.01 frente a 183 ha aproximadas.
- Cuotas flexibles ±10%, selección conjunta de sitios/especies, inventario desconocido y compras probabilísticas.
- Supervivencia y cadenas de Markov. Menor J no demuestra más supervivencia.
- Óptimos certificados y comparación estadística amplia de presupuestos. Solo P1 tiene 12 escenarios; los demás tienen un escenario probado.
- Costo solo de adquisición: no transporte, riego, mantenimiento ni reposición; presupuesto por ha no impuesto.
- Kernel Jupyter externo y revisión visual del HTML completo pendientes en un entorno que permita sockets y disponga de navegador. Las 17 celdas de código sí se ejecutaron en orden con IPython, y las cuatro figuras PNG fueron inspeccionadas visualmente.

## Historial

- Primera entrega: investigación y propuesta conceptual de compras bajo incertidumbre.
- Prototipo: inventarios conocidos, simulación espacial P1, DSATUR e intercambios.
- 18 oct 2026: README describe estado y plan de refactorización.
- Refactorización actual: módulos, notebook didáctico, C independiente, perfiles/lotes y evidencia de P1 y 30 polígonos. La incertidumbre original de compra sigue pendiente y separada del Monte Carlo espacial.
