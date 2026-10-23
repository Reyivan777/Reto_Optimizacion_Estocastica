# Optimización discreta de posiciones candidatas

## Extensión de fase 4 — 23 de octubre de 2026

La implementación anterior se conserva y se integra en main desde `36046d7`
sobre la base remota `484f01f`. [Diagnóstico previo](DIAGNOSTICO_FASE4.md): main
no tenía las sustituciones y la rama local no contenía las geometrías recién
aportadas. Los archivos de geometrías y los datos originales se preservan.

`vecindad_posiciones='sustituciones'` reproduce la etapa anterior.
`vecindad_posiciones='mixta'` usa los mismos pares planta/candidata, pero permite
un destino ocupado por otra nueva: intercambia las coordenadas de las dos
plantas manteniendo cada etiqueta. Un destino propio se rechaza. Las existentes
nunca son origen ni destino. Si el destino está libre se aplica la sustitución
anterior con todas sus comprobaciones. Las dos opciones requieren activar
`optimizar_posiciones`; continúa apagada por defecto.

Para sitios actuales A y B de plantas a y b, el delta de intercambio es:

```
delta = sum_{j != a,b} w(A,u_j) (C[y_b,y_j]-C[y_a,y_j])
      + sum_{j != a,b} w(B,u_j) (C[y_a,y_j]-C[y_b,y_j])
```

El término a-b no cambia por simetría de C. Intercambiar mantiene exactamente
el conjunto ocupado: las distancias y la pertenencia previamente validadas
siguen siendo factibles. El costo por propuesta es O(grado(A)+grado(B)); una
aceptación actualiza cuatro entradas de sitios/ocupantes. Se reconstruye el
grafo una vez al terminar y se comprueba J completo contra los deltas con la
misma tolerancia. No se construyen matrices densas ni se cambian DSATUR, MILP,
flujos previos, C, precios o datos. La memoria asintótica se conserva.

El intercambio es equivalente, para J, a intercambiar especies en sitios fijos;
permite explorar esa vecindad después de que las sustituciones cambien la
ocupación. No implica una ganancia ecológica diferente ni garantiza superar
siempre solo sustituciones con un presupuesto finito. No se alternan etapas,
no hay reinicios ni desplazamientos continuos (fuera de este alcance).

La historia conserva cuatro columnas `(paso, planta, candidata, delta)`.
Para reproducirla hay que consultar el ocupante actual del destino antes de
cada paso: si hay otra planta nueva se intercambian ambas posiciones; si está
libre se sustituye. `aplicar` realiza esa actualización del estado. Esta regla
también reproduce las trayectorias antiguas. Los nuevos contadores
`factibles_sustitucion`, `factibles_intercambio`, `aceptados_sustitucion` y
`aceptados_intercambio` permiten distinguir ambas operaciones. Sus sumas dan
los contadores agregados; al revertir la salida se anulan aceptaciones.

C++ conserva ABI 1 y el símbolo original `sustituir`; añade
`intercambiar_posiciones`. Ambos comparten el núcleo de ocupación dinámica.
Una biblioteca antigua debe recompilarse para usar la vecindad mixta y produce
un error explícito si falta el símbolo. Python conserva RNG y preparación CSR.

Uso desde DSATUR:

```
python scripts/compilar_cpp.py
python scripts/ejecutar_dos_etapas.py --motor cpp --poligonos 1,13,5 --optimizar-posiciones --vecindad-posiciones mixta --sin-graficas
python scripts/comparar_posiciones.py --incluir-mixta --referencia resultados/posiciones_20261021T155856_224722Z/referencia_previa.json --referencia-sustituciones resultados/comparacion_posiciones_20261021T160613_735938Z
python scripts/verificar_notebook_cpp.py --en-proceso --optimizar-posiciones --vecindad-posiciones mixta --poligonos 1,13,5
```

El comparador mantiene sus tres métodos predeterminados; `--incluir-mixta`
añade un cuarto con el mismo presupuesto de propuestas. Guarda un NPZ mixto
por escenario, manifiesto y tablas nuevas. La referencia opcional de
sustituciones comprueba hashes de entradas y salidas, J y todos los arrays de
los NPZ anteriores, incluida la trayectoria. No sobrescribe evidencia previa.

El notebook permite `VECINDAD_POSICIONES = "mixta"`; CLI, tutorial, lote y
exportaciones usan las coordenadas finales correctas. La comparación económica
permanece sobre geometrías iniciales comunes. Los GeoJSON aproximados todavía
no se usan en el pipeline; la pertenencia de los experimentos es al rectángulo
simulado. Una integración geográfica futura exige validación independiente.

## Resultados de fase 4 (23 de octubre)

Evidencia actual: [manifiesto](../resultados/comparacion_posiciones_20261023T192716_901247Z/manifiesto.json),
[288 ejecuciones](../resultados/comparacion_posiciones_20261023T192716_901247Z/escenarios.csv),
[resumen de fase 4](../resultados/comparacion_posiciones_20261023T192716_901247Z/resumen_fase4.csv)
y [36 pares entre motores](../resultados/comparacion_posiciones_20261023T192716_901247Z/equivalencia.csv).
Semilla 20261014, 6000 propuestas de especies y 6000 de posiciones, mismos
escenarios, cuotas económicas factibles y orden de motores alternado. El
piloto de un escenario por polígono (24 pipelines) tardó 10.682650 s de pared;
se estimaron unos pocos minutos antes de autorizar el lote completo.

Media de doce escenarios; los valores de J coinciden exactamente entre motores:

|Polígono|Plantas|Posiciones fijas + local|Solo sustituciones|Vecindad mixta|Reducción mixta vs fijas|Reducción mixta vs sustituciones|
|---|---:|---:|---:|---:|---:|---:|
|P1|842|882.856168|860.064863|845.858694|4.189232%|1.649825%|
|P13|3323|3672.060778|3605.802940|3545.782789|3.438378%|1.664382%|
|P5|5264|5861.864619|5745.539234|5656.761048|3.498965%|1.544881%|

Los porcentajes son medias de reducciones pareadas por escenario. **36/36**
mejoraron estrictamente frente a cada referencia; cero empeoramientos. No se
extrapolan a otros terrenos ni a supervivencia. Cada motor evaluó 216000
propuestas mixtas, 215844 factibles, 4084 sustituciones y 8112 intercambios
aceptados; siempre se conservaron etiquetas completas, compras y presupuesto.

Tiempos medios medidos en segundos, sin importaciones/compilación/economía ni
exportación en los tiempos de escenario:

|Polígono|Etapa mixta Python|Etapa mixta C++|Total fijo C++|Total mixto C++|
|---|---:|---:|---:|---:|
|P1|0.110378|0.013498|0.066769|0.081535|
|P13|0.170861|0.078062|0.185700|0.275054|
|P5|0.232069|0.144973|0.265964|0.418072|

El paso mixto incluye índice CSR, propuestas, núcleo, reconstrucción y
comprobación. Acumuló 6.159690 s en Python y 2.838404 s en C++. La mejora de J
tiene un costo computacional adicional; no se afirma aceleración respecto al
modelo fijo. El tiempo adicional se mide dentro del paso, sin restar totales
de ejecuciones distintas. El comparador completo tardó **184.616094 s** de
pared para 288 pipelines, verificaciones cruzadas y exportación; la regresión
apagada tomó otros **30.898544 s**, medida separadamente.

Mismo equipo Windows y compilador descritos en la referencia, versiones exactas
y hashes en manifiesto. Una medición por método/escenario y orden de métodos
fijo; no se estimó incertidumbre del tiempo ni se midió memoria adicional en
esta entrega. La memoria asintótica del índice se conserva, aunque un radio
grande o pool denso puede densificar sus aristas.

Validación actual:

- **36/36 pruebas**, cero fallos: 9 modelo, 6 economía, 5 C++ y 16 posiciones.
  [Registro](../resultados/comparacion_posiciones_20261023T192716_901247Z/pruebas.json)
  y logs de cada batería en esa carpeta. Incluye deltas exhaustivos de
  intercambios con matriz simétrica general y radios distintos; intercambio
  sin libres; trayectoria mixta validada paso a paso; invariantes, contadores,
  semillas, motores, exportación y factibilidad económica.
- **72/72 regresiones apagadas**: entradas/asignaciones idénticas y diferencia
  J=0. **216/216 comparaciones** de los tres métodos previos: hashes idénticos;
  máxima diferencia J=9.094947017729282e-13 al leer CSV; todos los arrays y
  trayectorias de 36 NPZ de sustituciones idénticos exactamente.
- **1217 archivos** preservados por SHA-256: datos y geometrías aportadas,
  algoritmo genético y resultados anteriores de ambas ramas. [Huellas y
  alcance](../resultados/comparacion_posiciones_20261023T192716_901247Z/preservacion.json).
- Notebook C++ con mixta P1/P13/P5: [17 celdas, cero errores](../resultados/notebook_cpp_20261023T193241_153556Z/validacion.json).
  Apagado P1: [17 celdas, cero errores](../resultados/notebook_cpp_20261023T193308_553571Z/validacion.json).
  Ambos ejecutados con IPython en proceso, seis PNG y nbformat válido; gráfica
  comparativa P5 inspeccionada. El kernel externo conserva su limitación previa.
- CLI modo fijo/Python con mixta P1: [ejecución factible](../resultados/ejecuciones/20261023T193314_997415Z_fijo/escenarios.csv).
  El notebook verificó también la integración económica C++ en los tres tamaños.

Fase 4 completada para la vecindad discreta solicitada. Permanece acotada al
pool y al terreno simulado; ninguna garantía de óptimo local/global. Geometrías
aproximadas sin integrar, matriz provisional y calibración ecológica siguen
siendo limitaciones conocidas. La siguiente fase recomendada es 5, que exige
otra solicitud; no se implementaron funcionalidades de fases 5–8.

## Referencia histórica: solo sustituciones (21 de octubre)

## Alcance y formulación

DSATUR y la búsqueda local de especies se conservan. La nueva etapa opcional se ejecuta una sola vez después de ellas; las etiquetas finales permanecen constantes. No hay desplazamientos continuos, alternancia, geometrías nuevas, mapas HTML ni cambios económicos. Base: `d29c169`; desarrollo en `optimizacion-posiciones-candidatas`.

El objetivo sigue siendo `J(U,y) = sum_{i<j} w(||u_i-u_j||) C[y_i,y_j]`, con `w(d)=max(0,1-d/radio)`. Un movimiento escoge un índice nuevo `a >= nf` y una candidata `c` libre. Se exige que `c` pertenezca al terreno y que `||c-u_j|| >= separacion_min` para todo `j != a`. La posición anterior queda libre y puede utilizarse en propuestas posteriores. Las candidatas actualmente ocupadas se rechazan; no se intercambian plantas ni especies.

Solo cambian los términos incidentes en `a`:

```
delta = sum_{j != a} [w(||c-u_j||) - w(||u_a-u_j||)] C[y_a,y_j]
```

Esto incluye aristas eliminadas, añadidas y con peso distinto. Las aristas entre otras plantas, incluido todo FF, permanecen constantes. Se acepta exclusivamente `delta < -1e-10`, como tolerancia de mejora del motor anterior. Si no hay mejoras se devuelve el mismo grafo de entrada. Se recalcula el objetivo completo al terminar y se verifica el acumulado con `atol=1e-7, rtol=0`; si el resultado completo no desciende, se restaura la solución anterior. Las distancias usan tolerancia de cálculo de 1e-9 m en nuevas propuestas, más estricta que los 1e-8 m de la validación histórica. No hay tolerancia monetaria.

## Arquitectura y costo

`src/reforestacion/posiciones.py` define el protocolo `Terreno.contiene(puntos)` que recibe coordenadas métricas `(n,2)` y devuelve máscara booleana `(n,)`. Incluye solamente el adaptador del rectángulo existente. El proveedor futuro podrá decidir contornos y agujeros. No se fabrican polígonos ni coordenadas geográficas. El optimizador recibe este adaptador y un conjunto candidato explícito; el ejecutor actual utiliza la misma malla triangular de siempre.

Se construye con cKDTree una vecindad estática entre existentes y candidatas hasta `max(radio,separacion_min)`, representada en CSR. Un vector por sitio contiene el índice de su planta o −1 si está libre; otro enlaza planta→sitio. Una propuesta solo recorre vecinos de destino y origen, y una aceptación modifica tres entradas de ocupación/sitio. No se recalcula J ni se reconstruye el grafo por propuesta. El grafo NetworkX/adyacencias se reconstruye una vez al terminar si hubo aceptaciones.

Memoria `O(sitios + aristas candidatas + intentos)`; una malla muy densa o un radio muy grande puede hacer densa la vecindad. No se construye una matriz de distancias N². Python y el núcleo C++17 `sustituir` usan exactamente el mismo CSR y las mismas propuestas NumPy. C++ reduce el costo del bucle de propuestas; la preparación espacial, conversión, RNG, reconstrucción y validación siguen en Python. Recompilar la biblioteca; una DLL anterior produce un error explícito, sin fallback. Las funciones originales y ABI 1 se conservan, con un símbolo nuevo opcional.

El RNG de posiciones usa `SeedSequence([semilla,p,escenario,104729])`. No consume ninguno de los tres flujos previos. Se generan pares uniformes planta/candidata; propuestas ocupadas o inválidas cuentan como evaluadas y rechazadas. `factibles` cuenta aquellas que pasan ocupación, pertenencia y separación y llegan a evaluar delta. No se afirma explorar exhaustivamente todas las sustituciones ni alcanzar óptimo local/global al agotar el presupuesto.

## Uso y salidas

Activar `Config.optimizar_posiciones=True`; `intentos_posiciones` limita propuestas independientemente del presupuesto de intercambios de especies. En CLI usar `--optimizar-posiciones --intentos-posiciones 6000`. El notebook tiene `OPTIMIZAR_POSICIONES` e `INTENTOS_POSICIONES`; se aplican al tutorial, lote y Monte Carlo existente. Por defecto la etapa permanece apagada. `intentos_local=0` permite DSATUR sin búsqueda de especies; no hay un algoritmo principal nuevo.

`ejecutar_escenario` devuelve `g_inicial` para referencias y `g` para coordenadas finales, `pool`, `historia_posiciones` (paso, planta, candidata, delta), `stats_posiciones`, `J_local_especies`, `seg_posiciones` y columnas `posiciones_*`. Las etiquetas `final` son las mismas antes/después del movimiento. `V` conserva la selección inicial; posiciones nuevas finales están en `g['U'][nf:]`. Las comparaciones y exportaciones evalúan cada asignación sobre su grafo correspondiente. Las comparaciones económicas verifican igualdad de geometrías **iniciales**; las finales pueden variar al cambiar las cuotas. `geometria_identica` sigue indicando igualdad final y se añade `geometria_inicial_identica`.

Las cuotas fijas históricas de seis polígonos ya excedían su presupuesto; esta etapa no repara ni empeora esos costos. La comparación nueva usa `DatosConCuotas` y los planes MILP existentes para garantizar presupuesto factible en los tres tamaños. No se cambia la formulación económica, el presupuesto ni C.

## Reproducción y evidencia

```
python scripts/compilar_cpp.py
python tests/verificar_modelo.py
python tests/verificar_economia.py
python tests/verificar_cpp.py
python tests/verificar_posiciones.py
python scripts/comparar_posiciones.py --escenarios 12 --poligonos 1,13,5
```

En entornos con temporales restringidos usar `TMP` y `TEMP` dentro de `build/tmp`. El comparador guarda manifiesto con hashes, configuración, versiones y compilación; planes económicos; filas CSV/JSONL; resumen; equivalencia de motores y distribuciones NPZ con sitios iniciales/finales y trayectoria aceptada. No retiene todos los grafos en memoria. Cada ejecución crea una carpeta exclusiva.

La referencia previa se capturó antes de modificar los núcleos: 36 escenarios (P1/P13/P5 × 12) con cada motor, más hashes de archivos históricos. `--referencia .../referencia_previa.json` verifica igualdad de entradas/asignaciones y objetivos al desactivar la etapa. Los históricos y la captura previa se conservan en carpetas independientes.

## Resultados medidos

Ejecución del 21 de octubre de 2026, Windows 11, Intel Family 6 Model 186, CPython 3.12.10 y TDM-GCC 10.3.0; versiones exactas y hashes en el manifiesto. Semilla 20261014, 6000 propuestas de especies y 6000 de posiciones. Los 12 escenarios son realizaciones distintas con semillas pareadas, no doce repeticiones cronometradas de una sola realización.

Evidencia principal: [escenarios](../resultados/comparacion_posiciones_20261021T160613_735938Z/escenarios.csv), [resumen](../resultados/comparacion_posiciones_20261021T160613_735938Z/resumen.csv), [manifiesto](../resultados/comparacion_posiciones_20261021T160613_735938Z/manifiesto.json), [equivalencia](../resultados/comparacion_posiciones_20261021T160613_735938Z/equivalencia.csv). Referencia anterior: [captura previa](../resultados/posiciones_20261021T155856_224722Z/referencia_previa.json), generada con `capturar_referencia.py` guardado junto a ella. Para repetir la comprobación opcional:

```
python scripts/comparar_posiciones.py --referencia resultados/posiciones_20261021T155856_224722Z/referencia_previa.json
```

Competencia media de doce escenarios por polígono, idéntica con ambos motores:

|Polígono|Plantas|DSATUR solo|+ local especies|+ posiciones|Reducción espacial absoluta media|Reducción espacial % media|
|---|---:|---:|---:|---:|---:|---:|
|P1 (pequeño)|842|988.451534|882.856168|860.064863|22.791305|2.581397%|
|P13 (mediano)|3323|4037.793099|3672.060778|3605.802940|66.257839|1.803905%|
|P5 (grande)|5264|6286.544148|5861.864619|5745.539234|116.325386|1.984649%|

La reducción espacial se calcula respecto de **DSATUR + local de especies**, antes de mover posiciones. La columna porcentual es la media de los doce porcentajes pareados, no el cociente de las medias. Hubo mejora estricta en **36/36 escenarios** y ningún empeoramiento. Rangos observados: P1 1.915691–3.442596%, P13 1.529529–2.202279%, P5 1.682506–2.224458%. No se extrapolan a otros terrenos.

Tiempo total medio por escenario (s), incluyendo la construcción original, asignación y validaciones; sin importaciones, compilación, economía ni escritura de salidas:

|Polígono|Python DSATUR|Python + especies|Python + posiciones|C++ DSATUR|C++ + especies|C++ + posiciones|
|---|---:|---:|---:|---:|---:|---:|
|P1|0.079518|0.171371|0.210697|0.027590|0.075599|0.088675|
|P13|0.747607|0.884482|0.949100|0.132652|0.165336|0.238781|
|P5|1.705389|1.782443|1.894769|0.231227|0.237216|0.354154|

Tiempo adicional **medido dentro de la etapa**, que incluye preparación del índice, propuestas, núcleo, reconstrucción y comprobación del objetivo:

|Polígono|Python medio (s)|C++ medio (s)|Evaluados por motor (12 escenarios)|Factibles por motor|Aceptados por motor|
|---|---:|---:|---:|---:|---:|
|P1|0.031319|0.016877|72000|5680|656|
|P13|0.086999|0.072014|72000|5771|1378|
|P5|0.100278|0.086131|72000|7007|2182|

La etapa C++ acumuló **2.100265 s**, 216000 propuestas y 4216 aceptaciones en 36 escenarios; Python acumuló 2.623163 s con las mismas aceptaciones. El costo de preparación/reconstrucción Python limita la aceleración del paso completo. Los tiempos adicionales no se estiman restando dos ejecuciones completas distintas: sus etapas comunes presentan variación de carga, asignación de memoria y cachés. No sumar columnas de tiempo inclusivas.

Se ejecutaron 216 pipelines (36 escenarios × tres métodos × dos motores) en **121.689107 s de pared**, incluyendo verificaciones cruzadas y exportación de evidencia del comparador. Orden de motores alternado por escenario; métodos siempre DSATUR→especies→posiciones, sin cargas computacionales simultáneas propias durante el benchmark. No se midieron repeticiones independientes para estimar incertidumbre de tiempos.

En los 216 pipelines se verificaron total, cuotas, existentes, unicidad, límites y distancia final. En cada par especies→posiciones las etiquetas completas, compras, costo y presupuesto se conservaron exactamente; todos los escenarios nuevos cumplieron el presupuesto mediante los planes económicos ya existentes. Las 36 distribuciones y trayectorias se guardan como NPZ; los tres métodos coinciden exactamente entre motores según hashes de coordenadas y etiquetas.

## Validación final

- **31/31 pruebas**: 9 del modelo original, 6 económicas, 5 C++ y 11 de sustituciones; cero errores. [Registros y tiempos](../resultados/comparacion_posiciones_20261021T160613_735938Z/pruebas.json) y archivos `verificar_*.py.log` en la misma carpeta.
- **72/72 ejecuciones desactivadas** (36 con cada motor): entradas y etiquetas finales idénticas a la captura previa, diferencia máxima de J igual a cero. [Regresión](../resultados/comparacion_posiciones_20261021T160613_735938Z/regresion_desactivada.csv).
- **1076 archivos históricos** preservados por SHA-256. [Comprobación](../resultados/comparacion_posiciones_20261021T160613_735938Z/historicos_verificados.json).
- Pruebas nuevas: deltas contra recálculo completo y aristas nuevas/eliminadas, radio menor que separación, cada aceptación de una trayectoria contra objetivo y distancias, existentes inmóviles, etiquetas/cuotas/costos, semillas, ambos motores, sitios ocupados/fuera/demasiado cercanos, empates e incrementos rechazados, reutilización de sitios liberados, cero nuevas/candidatas/intentos y errores de entrada. También prueban integración económica con geometría final diferente y exportación de cada J en su grafo correcto.
- Notebook C++ ejecutado con IPython en proceso: **17/17 celdas, cero errores y seis PNG** tanto [activado, P1/P13/P5](../resultados/notebook_cpp_20261021T161130_292588Z/validacion.json) como [desactivado, P1](../resultados/notebook_cpp_20261021T161220_024102Z/validacion.json). Formato nbformat validado; se conservan copias ejecutadas separadas y CSV/PNG en carpetas nuevas. Gráfica de cuatro métodos inspeccionada. No se repitió el kernel externo, cuya limitación del sandbox ya se documentó en fase 1.

La migración C++ queda completada; las sustituciones solicitadas están implementadas y validadas. Tras el commit se detiene el trabajo y se espera autorización para cualquier fase posterior.

## Límites

Geometrías rectangulares simuladas y C provisional del modelo original. El trabajo del compañero sigue pendiente de integrar. Solo se visitan candidatas de la malla existente; una propuesta aleatoria puede repetir pares y rechazar sitios ocupados. Mejoras adicionales dependen del número de candidatas libres, del escenario y del presupuesto de intentos. No implica beneficios observados de supervivencia. Las mediciones corresponden a este equipo y semillas; una medición por método y escenario, sin garantía de aceleración universal. No se implementan fases posteriores sin autorización.
