# Diagnóstico previo a la fase 4 — 23 de octubre de 2026

Revisión realizada antes de cambiar los núcleos: README completo, plan, estado,
notebook (34 celdas), módulos Python, C++17, configuración, datos y cuatro
baterías de pruebas. Se revisaron Git local y remoto, y las dependencias entre
economía, construcción espacial, asignación, búsqueda local y exportación.

## Discrepancias encontradas

- El checkout inicial estaba limpio en `optimizacion-posiciones-candidatas`,
  commit `36046d72c5e0aeafc2346a91280dcb9071063295`, no en `main`.
- `main` local y `origin/main` almacenado apuntaban a `d29c169`. Tras consultar
  GitHub y actualizar la referencia, el remoto real es
  `484f01f5a657812be8102d56c243770f10d4034b`. Sus cinco commits posteriores
  agregan cuatro archivos de geometrías; no cambian el pipeline original.
- La rama de candidatas ya implementa sustituciones discretas Python/C++,
  configuración, CLI, notebook y evidencia de 31 pruebas y 36 escenarios
  pareados. Ese trabajo no estaba integrado en `main`. Se integra conservando
  su historial y sus resultados, sin reimplementar las sustituciones.
- El registro de esa rama no incluía el identificador de su commit de cierre.
  Sus restricciones históricas de alcance eran solo sustituciones. La solicitud
  actual autoriza completar fase 4 e incluye intercambios de posiciones nuevas.
- El README de main afirma que no se modificaron config/experimento, aunque la
  fase 1 sí los modificó. La versión integrada corrige esa descripción.
- Hay GeoJSON/CSV aproximados y `geometria_real.py`, pero el ejecutor y notebook
  siguen construyendo rectángulos. No equivale a una fase 2 integrada/verificada.
  `crear_geometrias.py` referencia `datos/poligonos.csv`, ausente en el árbol
  revisado. Se documenta sin reparar ni ejecutar trabajo ajeno en esta fase.

## Estado funcional y alcance autorizado

Existente y reutilizable: MILP económico, flujos RNG independientes, DSATUR y
swaps de especies, construcción con cKDTree, validador de cuotas/distancias,
CSR de candidatas/ocupación dinámica y sustituciones con delta incidente.
La interfaz `Terreno.contiene` permite comprobar pertenencia sin depender de
geometrías geográficas nuevas. Las sustituciones rechazan destinos ocupados.

Falta completar: intercambio de posiciones entre dos plantas nuevas, selector
explícito que preserve sustituciones previas, deltas y núcleo nativo para esos
intercambios, trazabilidad de ambos tipos, pruebas y comparación nueva.
Un intercambio conserva la especie de cada planta y permuta coordenadas;
conserva el conjunto ocupado y, por tanto, pertenencia y separación. Aunque
equivale a permutar especies en sitios fijos para J, complementa las
sustituciones cuando la ocupación ya ha cambiado. No se afirma una vecindad
ecológica diferente ni optimalidad.

Diseño: un pase de propuestas planta/candidata; destino libre implica
sustitución, ocupado por otra nueva permite intercambio si se habilita.
CSR estático y ocupación/sitios dinámicos; excluir el par intercambiado al
calcular delta porque C es simétrica. No cambiar etiquetas, existentes, cuotas,
costos, C ni RNG anteriores. Reconstruir el grafo solo al finalizar, verificar
delta acumulado y revalidar factibilidad. Mantener apagada la etapa por defecto
y conservar el modo de solo sustituciones como referencia reproducible.

Validación prevista: pruebas originales y nuevas, regresión desactivada y del
modo sustituciones, comparación pareada posiciones fijas/sustituciones/mixto
en P1/P13/P5 con ambos motores; piloto antes del experimento de 12 escenarios.
Salidas en carpetas nuevas. Preservar hashes de datos, geometrías aportadas,
algoritmo genético e históricos de ambas ramas. No iniciar fases 5–8.
