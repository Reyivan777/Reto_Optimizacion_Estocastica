# Plan de implementación progresiva

Una fase por solicitud. Leer este documento, ESTADO_IMPLEMENTACION.md, Git y las dependencias antes de continuar. No modificar Algoritmo Genético, datos sincronizados ni evidencia histórica. Python sigue disponible como referencia. No se afirma optimalidad global espacial.

## Solicitud vigente: fase 8 — mejoras y decisión conjunta

Solicitud explícita del 23 de octubre de 2026 sobre `1da57a7`, main limpio.
Ejecutor opcional independiente: DSATUR con tolerancia de casi empates,
reinicios reproducibles de asignación/local y búsqueda conjunta de especies
nuevas en grafo fijo. Se conservan motores, algoritmo histórico, C y economía.
La referencia es candidata; J final no empeora. Presupuesto decimal, bandas,
inventario y total se verifican tras cada cambio económico aceptado.

Contrato conjunto explícito: D≤D_referencia+margen decimal no negativo,
margen=0 e intentos conjuntos=0 por defecto. Se optimiza J en ese conjunto;
no se afirma conservar el desempate de costo mínimo ni óptimo global conjunto.
Sin datos para una función monetaria-ecológica calibrada, no se inventa peso
que sume dinero y J. La configuración 0.02 es sensibilidad, no recomendación.

Aceptación: pruebas finales heredadas/nuevas, regresiones apagada/mixta,
reproducción y equivalencia entre motores, soluciones exportadas recalculables,
matemática y explicación accesibles en informe/CLI/notebook. Evidencia en
[MEJORAS_FASE8.md](MEJORAS_FASE8.md). Tras documentar y crear commit,
detenerse; no retomar fases 2/3 ni modificar Algoritmo Genético.

## Historial: solicitud de fase 7 completada

Solicitud explícita del 23 de octubre de 2026, sobre `c2c0fe4`, main limpio.
Implementar exclusivamente matrices alternativas configurables, análisis de
sensibilidad reproducible y revisión con fuentes de agua, nutrientes y raíces.
Conservar C original, datos, motores, economía, geometrías e históricos.

Implementación independiente: `sensibilidad.py`, `analizar_sensibilidad.py`,
configuración de hipótesis y `validar_fase7.py`. Familia taxonómica explícita
con seis alternativas y referencia original, además de matrices arbitrarias
simétricas. Coeficientes identificados como heurísticos no calibrados; las
fuentes no autorizan inventar mediciones de las diez especies. Comparación
pareada y evaluación cruzada bajo la misma matriz evaluadora; no interpretar
un cambio de escala de J como ganancia ecológica.

Aceptación: validar matrices y especies, semillas/sitios/cuotas idénticos,
invariantes espaciales y económicos, equivalencia Python/C++, regresiones y
preservación por SHA-256. Denominadores y límites explícitos. Evidencia y
resultados en [SENSIBILIDAD_FASE7.md](SENSIBILIDAD_FASE7.md).
Al documentar y crear commit, detenerse. No implementar fase 8 ni retomar 2/3.

## Historial: solicitud de fase 6 completada

Solicitud explícita del 23 de octubre de 2026, sobre `4100608`, main limpio.
Implementar exclusivamente supervivencia esperada y escenarios exploratorios
de mortalidad, reposición, precios y presupuesto. Se auditan el CSV histórico
y los costos disponibles antes de proyectar; no se inventan denominadores ni
una relación causal entre competencia y supervivencia. Los inventarios y
compras iniciales son conocidos; no cambiar motores, geometrías ni economía.

Implementación independiente: `src/reforestacion/supervivencia.py`,
`scripts/explorar_supervivencia.py`, configuración explícita de hipótesis,
pruebas y `scripts/validar_fase6.py`. Referencia: probabilidad hipotética de
un periodo tomada de 2023/100 sin calibración temporal; existentes p=1 por
supuesto. Mortalidad, reposición de un ciclo y estrés de precios/B son opciones
exploratorias sin reoptimizar cuotas ni certificar factibilidad de reposición.

Aceptación: distinguir porcentajes observados, esperanzas condicionales e
hipótesis; límites de costos/denominadores; dinero decimal por polígono;
semillas separadas de fase 5 y agregados completos. Cumplida con 54/54 pruebas,
144 regresiones espaciales, 1461 archivos previos preservados y 180000
realizaciones sin exclusión. Fórmulas/resultados/límites en
[SUPERVIVENCIA_FASE6.md](SUPERVIVENCIA_FASE6.md).
Al documentar y crear commit, detenerse. No implementar fases 7/8.

## Historial: solicitud de fase 5 completada

Solicitud explícita del 23 de octubre de 2026, sobre `a323ddf`, checkout limpio.
Implementar exclusivamente Monte Carlo espacial: escalamiento con tamaño
justificado por piloto independiente, convergencia, error estándar, IC y
percentiles; evaluar procesos y agregación pareada. Inventario, compras y
cuotas económicas permanecen conocidos, sin aleatorizarlos. No modificar
geometrías aportadas, algoritmos previos, históricos ni Algoritmo Genético.

Implementación: ejecutor independiente `scripts/escalar_monte_carlo.py`,
módulo `monte_carlo.py`, pruebas, celda documental de notebook y documentación.
Piloto 30, confirmación fija 100–1000, objetivo configurable de precisión de
la media J final; los límites no equivalen a precisión alcanzada. Semillas
por índice independientes del proceso, agregados solo con todos los polígonos
solicitados y conteos explícitos; sin parada opcional ni reemplazo de fallos.
Aceptación y resultados medidos en [MONTE_CARLO_FASE5.md](MONTE_CARLO_FASE5.md).
Al validar y registrar commit, detenerse: no implementar fase 6.

## Historial: solicitud de fase 4 completada

Base remota verificada: `484f01f` de main (23 de octubre de 2026). Integrar la
rama previa `36046d7` de sustituciones, preservando geometrías aportadas e
históricos. Añadir vecindad `mixta` de sustituciones e intercambios entre plantas
nuevas con especie fija, deltas incidentes Python/C++, configuración explícita,
CLI y notebook. Conservar modo previo `sustituciones`, etapa apagada por defecto,
RNG separados y objetivo original. Diagnóstico: [DIAGNOSTICO_FASE4.md](DIAGNOSTICO_FASE4.md).

La interfaz de pertenencia permite validar la fase sobre el rectángulo actual;
integrar las geometrías del compañero no es indispensable ni parte de este
alcance. Verificar cuotas, existentes, pertenencia, separación, compras y
presupuesto; comparar cuatro métodos con ambos motores y mismas propuestas.
Preservar regresiones apagada y de solo sustituciones. Al documentar resultados
y commit, detenerse. La próxima fase recomendada es 5 y requiere otra solicitud.

## Antecedente: sustitución de posiciones candidatas (21 de octubre)

La migración C++17 está **completada y validada**. Las geometrías aproximadas son responsabilidad de otro integrante; no editar sus archivos ni implementar contornos. Los mapas HTML quedan **pospuestos** hasta integrar ese trabajo. La siguiente fase activa es la optimización de posiciones (fase 4 adelantada), exclusivamente sustitución discreta de candidatas; no requiere esperar las geometrías nuevas.

Base reproducible: `d29c169`, rama independiente `optimizacion-posiciones-candidatas`. Conservar DSATUR y el objetivo original; etapa adicional apagada por defecto. Implementar interfaz `Terreno.contiene`, rectángulo actual, vecindades dispersas estáticas y ocupación dinámica, deltas incidentes Python/C++, propuestas NumPy separadas y reconstrucción final del grafo. No mover existentes ni cambiar etiquetas, cuotas, costos, presupuesto o C.

Aceptación: pruebas de invariantes/deltas/semillas/ambos motores/sin movimientos, regresión desactivada contra referencia previa y tres métodos pareados en P1/P13/P5 × 12 escenarios. Medir reducciones, intentos/factibles/aceptados, tiempo adicional y total; guardar evidencia nueva. Actualizar notebook, CLI y documentación; pruebas finales, commit y detenerse. Desplazamientos continuos, alternancia, nuevos modelos Monte Carlo y supervivencia quedan fuera de esta solicitud.

Alcance de sustituciones completado: 31/31 pruebas, 72/72 regresiones desactivadas y 36/36 escenarios con mejora adicional, igualdad exacta Python/C++. Evidencia, tiempos y límites en [OPTIMIZACION_POSICIONES.md](OPTIMIZACION_POSICIONES.md). Tras el commit, esperar autorización; no avanzar a los otros movimientos de fase 4.

|Fase|Objetivo y alcance|Dependencias|Aceptación|
|---|---|---|---|
|1 — completada|Migración C++17 y benchmarks validados.|Código actual, compilador C++17, NumPy/SciPy.|Evidencia en MOTOR_CPP.md y BENCHMARKS_CPP.md.|
|2 — otro integrante|Geometrías aproximadas; integración futura mediante adaptador.|Trabajo y geometrías verificadas del compañero.|No implementar ni modificar sus archivos en esta fase.|
|3 — pospuesta|Mapas HTML individuales/global.|Geometrías integradas.|Esperar una solicitud posterior.|
|4 — completada|Sustituciones e intercambios discretos de candidatas para plantas nuevas, opcionales tras DSATUR/local de especies.|Motor validado, interfaz de pertenencia; rectángulo actual.|36/36 pruebas; 72 regresiones apagadas, 216 comparaciones previas, 36/36 escenarios mejorados y equivalencia exacta Python/C++; evidencia en OPTIMIZACION_POSICIONES.md.|
|5 — completada|Escalar Monte Carlo espacial, convergencia, error estándar, IC y percentiles; evaluar paralelismo/agregación.|Motor y benchmarks; inventario conocido documentado.|Piloto 30 y confirmación independiente 100 por P1/P13/P5; precisión verificada, semillas/denominadores, procesos equivalentes y compras fijas. Evidencia en MONTE_CARLO_FASE5.md.|
|6 — completada|Supervivencia esperada y escenarios exploratorios de mortalidad, reposición de un ciclo, precios y presupuesto.|CSV auditado; costos disponibles solo de adquisición, sin denominadores históricos calibrables.|Observaciones, proyecciones e hipótesis separadas; 54/54 pruebas, 144 regresiones y evidencia en SUPERVIVENCIA_FASE6.md. Sin causalidad competencia-supervivencia no validada.|
|7 — completada|Matriz alternativa configurable y sensibilidad; revisión de agua, nutrientes y raíces con fuentes primarias.|Supuestos explícitos, C original conservada; sin calibración local disponible.|Comparación cruzada reproducible de siete matrices, coeficientes heurísticos identificados y validación en SENSIBILIDAD_FASE7.md; sin inventar mediciones.|
|8 — completada|DSATUR tolerante, reinicios/local y composición conjunta acotada; CLI, notebook, CSV/NPZ e informe.|Referencias y economía de fases anteriores; margen explícito sin peso ecológico inventado.|78/78 pruebas, 144 regresiones; evidencia recalculada y equivalencia de motores en MEJORAS_FASE8.md. Sin óptimo global ni cambio automático de fase.|

## Diseño histórico de fase 1 (completado; prioridad sustituida arriba)

Base Git: 49b17fa, main, checkout inicialmente limpio. Referencia económica: docs/VALIDACION_ECONOMICA.md; referencia espacial: docs/MODELO_CUOTAS_FIJAS_HISTORICO.md y resultados guardados.

Interfaz C ABI mediante ctypes de biblioteca compartida C++17: no requiere pybind11 ni paquetes nuevos. Python valida buffers contiguos, conserva NumPy RNG y entrega propuestas idénticas a C++. Adyacencias CSR conservan orden de aristas. Sin fast-math ni contracción FMA. Desempates originales y tolerancia local -1e-10. Candidatas y DSATUR siguen cuadráticos, con menores constantes y sin matriz densa de distancias. Economía permanece en SciPy/HiGHS.

Orden: línea base y perfil → núcleos e integración → equivalencia y fallos → benchmarks 1/12 y escalamiento 100/1000/10000 según recursos → notebook y regresión histórica → documentación, pruebas y commit. No avanzar a fase 2 en esta solicitud.

Medir en el mismo equipo, sin profiler durante benchmarks, tiempo completo y por etapa, exportación y memoria de proceso. Separar costo de propuestas Python, conversiones y núcleo nativo. Una escala de 10000 escenarios de un polígono NO representa 10000 por cada uno de los 30. No extrapolar aceleraciones como mediciones. Procesar un escenario a la vez y guardar filas sin retener distribuciones.
