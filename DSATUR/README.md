# Reforestación: optimización económica y DSATUR

La interfaz didáctica es **modelo_reforestacion.ipynb**. Trabajar desde `DSATUR/` e instalar `python -m pip install -r requirements.txt`. No se modifica `Algoritmo Genético/`.

## Dos modos y etapas independientes

```bash
# Economía exclusivamente: 30 MILP, sin simulación espacial
python ejecutar_dos_etapas.py --etapa economica --poligonos todos
# Un polígono; por defecto compara con cuotas fijas bajo condiciones idénticas
python ejecutar_dos_etapas.py --poligonos 5 --escenarios 1
# Selección
python ejecutar_dos_etapas.py --poligonos 5,9,10,12,18,23 --escenarios 1
# Los 30; prueba progresiva
python ejecutar_dos_etapas.py --poligonos todos --escenarios 1
# Experimento Monte Carlo completo (costoso)
python ejecutar_dos_etapas.py --poligonos todos --escenarios 12
# Modo histórico: no repara cuotas
python ejecutar_dos_etapas.py --modo fijo --poligonos todos --escenarios 1
# Pruebas
python verificar_modelo.py
python verificar_economia.py
# Validación completa pareada: 12 escenarios, 6 procesos independientes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python validar_lote_economico.py --escenarios 12 --workers 6
```

`--sin-comparacion` omite la ejecución espacial fija de referencia; `--sin-graficas` evita renderizar PNG. Cada ejecución crea `resultados/ejecuciones/<fecha_UTC>_<modo>/`; nunca sustituye otra carpeta. El notebook conserva un recorrido explicativo con cuotas fijas (secciones 2–14), separado del experimento elegido mediante `MODO` en la sección 15. Sus parámetros iniciales usan un escenario para comprobar funcionamiento; 12 habilita el experimento completo. Se aceptan un ID, una lista o `"todos"`.

Para ejecutar solo la etapa espacial a partir de cuotas ya calculadas:

```python
import json
from pathlib import Path
from reforestacion.config import perfil
from reforestacion.datos import Datos, cargar_competencia
from reforestacion.optimizacion_economica import DatosConCuotas
from reforestacion.experimento import ejecutar_escenario, ejecutar_lote

root = Path.cwd()
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

`optimizacion_economica.py` decide cuotas y crea una vista de datos, sin mutar el catálogo ni el inventario. `dos_etapas.py` coordina planificación, llamadas a `ejecutar_escenario`, verificación final y reportes. **No se modifican** `algoritmos.py`, `geometria.py`, `datos.py`, `config.py`, `economia.py`, `experimento.py`, la matriz C ni las validaciones originales.

Los swaps conservan las cuotas ajustadas. Se vuelve a comprobar el histograma final, las compras y el presupuesto. Como total e inventario no cambian, los mismos flujos aleatorios generan exactamente los mismos sitios y etiquetas existentes en ambos modos; esto se verifica en cada comparación pareada. Todas las especies pueden ocupar cualquier sitio nuevo: no existe una prohibición especie-sitio adicional. La capacidad geométrica depende del total, no de la composición.

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

La referencia histórica de esta implementación es el commit **75a54abc199563471bec29bba051da3d1d483e8b**. `resultados/P*/` y `resultados/modelo_completo/` permanecen byte a byte intactos. La evidencia de las pruebas de esta actualización se documenta en `VALIDACION_ECONOMICA.md`. El validador paralelo crea una carpeta `validacion_30_<fecha>/` con tablas agregadas y una subcarpeta por ejecución de polígono; sus tiempos acumulados no deben confundirse con tiempo de pared. La concurrencia no modifica parámetros ni semillas. En Windows puede omitirse el prefijo de variables de entorno del comando.

---

## Documentación histórica del modo fijo (base 75a54ab)

Lo siguiente describe el modo original y sus resultados históricos. Las frases «no aplicado» o «futuro» se refieren exclusivamente a esa versión; el modo económico actual se documenta arriba. Sus rutas de salida antiguas no son las rutas del nuevo ejecutor.

# Modelo DSATUR — Reforestación

La interfaz principal es **[modelo_reforestacion.ipynb](modelo_reforestacion.ipynb)**. Abre la carpeta **DSATUR/** como carpeta de trabajo en VS Code/Jupyter e instala `python -m pip install -r requirements.txt`. No se cambia el enfoque independiente de `Algoritmo Genético/`.

## Configurar y ejecutar

En la primera celda de código:

```python
POLIGONOS = "todos"    # o un entero de 1 a 30
ESCENARIOS_MC = 12     # Monte Carlo del polígono detallado
ESCENARIOS_LOTE = 12   # escenarios de cada polígono al elegir todos
EJECUTAR_COMPARACION_PRESUPUESTOS = False
```

Ejecuta en orden. Usa `ESCENARIOS_LOTE = 1` para una prueba rápida; un escenario no permite estimar una desviación estándar. El perfil completo limita cada polígono a 20000 plantas y cada lote a 360 corridas; los excesos quedan `omitido`. Los parámetros están en `reforestacion/config.py`.

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

`python verificar_modelo.py` ejecuta nueve pruebas rápidas opcionales: regresión P1, restricciones y deltas, reproducibilidad, presupuesto por polígono, mínimo económico contrastado, agregados incompletos/duplicados, dos métodos en las figuras y fallos controlados. El notebook sigue siendo la interfaz principal; el verificador no lanza el lote de 360 corridas.

**Ejecución efectivamente verificada en esta actualización:** 360/360 corridas (12 por cada uno de los 30), 12/12 escenarios globales completos, cero fallos y omisiones. Media de J agregado: aleatoria **161729.153384**, final **134334.030467**. Reducción media entre escenarios **16.938821%**, desviación estándar **0.074640 puntos porcentuales**, rango **16.830560%–17.054963%**. La máxima diferencia contra las 360 filas históricas es **4.55×10⁻¹³** (redondeo/serialización, tolerancia 1e-8); no se alteraron las heurísticas. P1, escenario 0: J aleatoria 1089.006627, DSATUR interno 991.747705 y final 874.525183. Se verificaron también los 240 archivos individuales y el modo de un único polígono (P1, dos escenarios). Las nueve pruebas rápidas pasan.

La evidencia exacta de la ejecución de esta actualización se guarda en `modelo_completo/validacion.json`: escenarios realmente ejecutados, regresión contra las 360 filas históricas, archivos generados y resultados de pruebas. Al volver a ejecutar se regenera ese registro con las validaciones integradas de la nueva corrida; no se heredan como ejecutadas pruebas rápidas o regresiones de una ejecución anterior. El notebook guardado contiene salidas ejecutadas. La ejecución en este entorno usa IPython en proceso; un kernel externo de Jupyter y el HTML integral no se dan por verificados sin una comprobación adicional en un entorno con sockets y navegador. Las figuras PNG se inspeccionan por separado.

Pendientes: geometría y recursos medidos, C calibrada, P13=5.05 ha y relación mapa-tabla, decisión real de cuotas flexibles con presupuesto obligatorio, inventario desconocido y compras estocásticas, costos integrales y optimalidad certificada. Menor J no demuestra mayor supervivencia. No se añaden Markov ni optimización conjunta de posiciones y especies.
