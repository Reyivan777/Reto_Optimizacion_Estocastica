# Fase 8: reinicios y composición conjunta acotada

Implementada el 23 de octubre de 2026 sobre `1da57a7`, exclusivamente en DSATUR.
Leídos README, plan, estado, implementación y pruebas heredadas. No se cambian
algoritmos previos, C, economía, motores, geometrías ni archivos históricos.

## Uso e interpretación

Desde DSATUR, instalar `python -m pip install -r config/requirements.txt`.
C++ requiere compilar previamente con `python scripts/compilar_cpp.py`.

```shell
# Referencia + tres reinicios/local, sin cambios de composición
python scripts/optimizar_fase8.py --motor cpp
# Sensibilidad conjunta explícita, margen de desviación total 0.02
python scripts/optimizar_fase8.py --motor cpp --intentos-conjuntos 6000 --margen-desviacion 0.02
# Posiciones mixtas previas opcionales, antes de mejorar asignación
python scripts/optimizar_fase8.py --motor cpp --poligonos 1 --escenarios 1 --optimizar-posiciones
python tests/verificar_mejoras.py
python scripts/validar_fase8.py resultados/mejoras_fase8_20261023T202903_615483Z --snapshot resultados/mejoras_fase8_20261023T202903_615483Z/preservados_sha256.json
```

Sin opciones se usa Python; tres reinicios, 6000 propuestas locales por reinicio,
12 escenarios P1/P13/P5, semilla 20261014, cero intentos conjuntos y margen cero.
`--reinicios 0 --intentos-conjuntos 0` conserva exactamente la referencia.
`--max-corridas` limita asignaciones (referencia+reinicios) antes de crear salidas;
los intentos locales/conjuntos son presupuestos adicionales explícitos.
Biblioteca ausente y errores técnicos se propagan, sin fallback. Fallos de
construcción/límites conservan índice y estado, sin imputar J ni reemplazarlos.

La referencia es el plan económico lexicográfico anterior seguido de DSATUR,
local y, si se solicita, posiciones mixtas. Reinicios y cambios conjuntos usan
ese mismo grafo final. Plantas existentes, coordenadas y total se conservan.
La composición conjunta vuelve a decidir compras de adquisición para ese
escenario; no modela muerte ni reposición. No hay datos para recomendar un
margen o sumar dinero y competencia mediante un peso ecológico calibrado.

## Formulación y decisiones

Se minimiza el mismo objetivo

$$J(y)=\sum_{(i,j)\in E} w_{ij}C_{y_i,y_j}.$$

DSATUR conserva selección por saturación, grado ponderado e índice. Entre
especies factibles cuyo costo incremental está a lo sumo 1e-10 sobre el mínimo,
prefiere máxima cuota pendiente y sortea empates con NumPy. Esto contiene la
sensibilidad a casi empates detectada en fase 7, sin prometer invariancia bajo
cambios de escala de C: la tolerancia es absoluta en unidades de J.
Cada reinicio construye otra asignación y ejecuta la búsqueda local existente
con 6000 swaps. No se migra este DSATUR experimental a C++: se comparte Python
para construcción tolerante, mientras geometría, referencia y swaps usan el
motor seleccionado. No se altera ABI ni el comportamiento predeterminado.

Se conserva el mejor de referencia y reinicios, evaluado de nuevo con J completo.
Solo se sustituye el incumbente con descenso mayor a 1e-10. Tener más intentos
permite mejorar; esta comparación no demuestra superioridad con igual cómputo.

La etapa conjunta cambia una especie de una planta nueva por propuesta. Para
x_s=conteo final, n_s=inventario y R_s=cuota original, exige exactamente:

$$\sum_s x_s=\sum_s R_s,\quad
\max(n_s,\lceil0.9R_s\rceil)\le x_s\le\lfloor1.1R_s\rfloor,$$
$$q_s=x_s-n_s\ge0,\quad \sum_s c_s q_s\le B,$$
$$D(x)=\sum_{s:R_s>0}|x_s-R_s|/R_s\le D(x^{ref})+\epsilon.$$

El margen epsilon se lee como decimal exacto (`--margen-desviacion`, cero por
defecto); D se compara con Fraction y moneda con enteros decimales comunes.
La etapa conjunta no exige costo ≤ costo de referencia: puede usar saldo
presupuestal para reducir J. Tampoco conserva necesariamente el desempate de
costo mínimo del MILP. El certificado del plan de referencia NO se transfiere
al resultado conjunto. Aun con epsilon=0, se exploran solo composiciones
alcanzables por cambios unitarios factibles; no se certifica óptimo conjunto.

Para cambiar a de especie r a s, el delta exacto en grafo fijo es

$$\Delta J=\sum_{j:(a,j)\in E}w_{aj}(C_{s,y_j}-C_{r,y_j}).$$

Se acepta solo delta < -1e-10 tras verificar todas las restricciones. Las aristas
fija-fija nunca cambian. Al terminar se recalculan J, histograma, fijas,
pertenencia, separación, bandas y presupuesto. Sin búsqueda exhaustiva ni
certificado de óptimo local/global; no hay alternancia con geometría posterior.

Flujos separados: SeedSequence([semilla,8,polígono,escenario,reinicio]).spawn(2)
para construcción y swaps; índice reservado 2147483647 para composición.
Los flujos anteriores permanecen intactos. Solo se retiene un grafo a la vez,
además de tablas resumen y distribución del escenario cero.

## Exportaciones e interfaz

El CLI crea una carpeta nueva por ejecución. `INFORME.md` presenta comparación
y límites; `escenarios.csv` da J de referencia/reinicios/final, costos, D y
tiempos. Los campos de etapas `local_*`, `posiciones_*`, J_dsatur y
J_local_especies describen exclusivamente el pipeline de referencia; las
mejoras posteriores están en J_reinicios/J_final y `trayectorias.csv`.
`cuotas.csv` distingue original, referencia, final, inventario y compras.
`distribuciones_escenario0.csv` contiene coordenadas/especies finales.
Cada NPZ guarda ambos etiquetados, sitios, aristas, pesos, C, R/n/x y límites
para auditoría independiente. Las coordenadas son metros de rectángulo simulado,
sin georreferenciación. No se generan mapas HTML de fase 3.

`resumen_pareado.csv` publica diferencias final−referencia, SE, IC95% Student
puntuales y percentiles empíricos con válidos/solicitados/excluidos. Cero/una
observación no producen un IC inventado. Los IC son exploratorios bajo el
modelo y de la media de diferencias, sin precisión confirmatoria ni cobertura
simultánea. Selección de incumbente implica ausencia de empeoramiento por
construcción. No demuestra mejora ecológica ni supervivencia.
`manifiesto.json` identifica parámetros, base Git, fuentes por SHA-256,
versiones y biblioteca. El notebook añade una celda documental opcional;
37 celdas anteriores, salidas y metadatos permanecen idénticos.

## Evidencia medida

Principal C++: `resultados/mejoras_fase8_20261023T202903_615483Z/`.
P1/P13/P5 × 12 escenarios; 3 reinicios × 6000 swaps más 6000 propuestas
conjuntas, epsilon=0.02, posiciones apagadas. **36/36 válidos**, sin exclusión;
**36/36 mejoran** frente a la referencia original. Comparación Python completa
en `mejoras_fase8_20261023T202913_687511Z/`: **36 parejas** con sitios y
soluciones idénticos por SHA-256, diferencia J bajo 1e-8.

|Polígono|Media J referencia|Media J tras reinicios|Media J final|Reducción relativa media|IC95% diferencia J|
|---|---:|---:|---:|---:|---|
|P1|882.856168|879.201686|878.492372|0.493019%|[-6.692618,-2.034975]|
|P13|3672.060778|3665.537343|3659.690432|0.336552%|[-15.857005,-8.883688]|
|P5|5861.864619|5853.988719|5845.442260|0.279971%|[-21.764414,-11.080305]|

Cambios conjuntos aceptados P1/P13/P5: 27/171/293. Costo final medio
15904.00/62551.541667/99997.833333 u.m., frente a referencias
15903.50/62549.50/99995.00: se usa parte del saldo, sin exceder B individual.
Tiempo medio adicional C++ 0.394562/1.668327/3.574476 s; total medio
0.465003/1.871946/3.863500 s. Pared del lote 75.332482 s C++ y
112.505912 s Python. Ejecuciones parcialmente concurrentes con otras tareas;
no son un benchmark de aceleración, no se midió RSS ni se probó Linux.

Prueba conjunta adicional: `mejoras_fase8_20261023T203041_559780Z/`, los
30 polígonos × un escenario, cero reinicios y 1000 intentos conjuntos,
epsilon=0.02: **30/30 válidos**, incluye restricciones presupuestales de P12/P23.
Control predeterminado `mejoras_fase8_20261023T203152_428797Z/`: seis escenarios
P1/P13/P5, tres reinicios, conjunta apagada; D y cuotas conservadas y J final
coincide con J_reinicios de las parejas del lote principal.
No se mezclan sus muestras con los 12 índices principales.
Para auditar cada carpeta sin repetir las baterías:
`python scripts/validar_fase8.py resultados/CARPETA --solo-exportaciones`.
La auditoría reconstruye B a partir de área y tarifa decimales originales;
no interpreta el ruido float del CSV presupuestal histórico como precisión
monetaria adicional. Esto corrigió un rechazo técnico inicial de auditoría
(precisión excesiva), sin cambiar decisiones ni ampliar presupuesto.

El ensayo preliminar `mejoras_fase8_20261023T202832_824732Z/` se repitió tras
corregir porcentajes heredados al nuevo J/costo; conserva aviso explícito.
No es evidencia final ni se usan sus tiempos. Otras carpetas pequeñas provienen
de pruebas CLI. No se sobrescribe evidencia de fases anteriores.

## Validación y cierre

**78/78 pruebas**, ocho baterías (9 modelo, 6 economía, 5 C++, 16 posiciones,
6 Monte Carlo, 12 supervivencia, 12 sensibilidad y 12 mejoras). Logs y tiempos
en `pruebas.json` y `pruebas_*.log` de la carpeta principal. Nuevas pruebas:
deltas contra suma completa con C general, casi empates, cuotas/fijas,
parámetros, cero opciones, reproducción/monotonía, ambos motores con/sin
posiciones, cambio económico aceptado, rechazo por D/B, sin nuevas/aristas,
propagación de errores y exportaciones CLI.

**144/144 regresiones** contra fase 4: 72 posiciones apagadas y 72 mixtas,
P1/P13/P5 × 12 × ambos motores; hashes de entradas/soluciones idénticos,
tolerancia J 1e-8. **1647 archivos previos preservados** por SHA-256, incluidos
datos, geometrías, C, motores, resultados y Algoritmo Genético. El snapshot
excluye únicamente archivos documentales/notebook previstos para actualizar.
Los 36 NPZ principales se recalcularon independientemente con máximo error J
9.094947017729282e-13. Se auditan además los 36 Python, 30 de todos los
polígonos y seis controles; ver `auditoria_adicional.json`.

La exactitud económica y espacial no calibra C ni los rectángulos y no prueba
supervivencia. Continúan pendientes confirmaciones externas de bandas, moneda,
precios y geometrías. La fase 8 usa solo datos disponibles con alcance
heurístico explícito. README, plan y estado persistente actualizados; commit
local, sin push. Detenerse: no retomar fases 2/3 automáticamente.
