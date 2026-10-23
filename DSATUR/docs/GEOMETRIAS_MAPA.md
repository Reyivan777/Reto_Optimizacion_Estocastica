# Correspondencia y mapas — fases 2/3

Validación del 23 de octubre de 2026. Alcance exclusivo DSATUR. Se conserva la
implementación existente, sus motores, economía, semillas y resultados históricos.
No se implementan cambios de fases 4–8.

## Diagnóstico comprobado

La base local `de825f0` estaba limpia, siete commits por delante del origin
conocido. Tras consultar GitHub se encontró `c175c0d`, cuyo único cambio era el
HTML recibido. Se incorporó por merge, conservando ambas historias.

Se leyó completamente el documento de 6,354,942 bytes: estructura, imagen PNG,
diagrama, matriz, 120,160 puntos y toda su lógica de interacción. El objeto `D`
mezclaba inventarios del polígono mostrado con superficies ajenas y posiciones
recalculadas. Las áreas de 29/30 y las composiciones de 30/30 no coincidían.
Incluso P21, con 8 ha y 5264 plantas correctas, fallaba en especies.

|ID|Área original (ha)|HTML recibido (ha)|Plantas originales|HTML recibido|
|---|---:|---:|---:|---:|
|P1|1.28|5.40|842|3553|
|P2|6.64|7.52|4369|4948|
|P5|8.00|7.56|5264|4974|
|P27|8.00|1.28|5264|1042|

Las existentes por especie sí correspondían al ID mostrado en los 30 casos.
Por ello, P1 no era simplemente la distribución de P30 con otra etiqueta: tenía
sus propias 165 existentes junto a una superficie de 5.40 ha. P27 atribuía
1.28 ha a sus 1042 existentes. Además, el área HTML de P29 (6.54 ha) no existe
en el catálogo actual. No hay una permutación unívoca que repare estos datos.

El commit recibido **no incluye el generador original**. Se comprueba la mezcla
de fuentes en la salida, pero no se puede atribuir con certeza a `zip`, a una
ordenación lexicográfica u otra instrucción concreta ausente. El código JS
consumía esa mezcla sin validar procedencia y suponía índices con `sel-1`.
No se presenta una hipótesis de ordenamiento como causa demostrada.

La corrección reemplaza ese ensamblado no trazable por
`src/reforestacion/mapa_interactivo.py`: para cada entero p se abre expresamente
`resultados/P{p}/distribucion.csv`, su comparación y sus metadatos. Geometrías,
áreas, inventarios y cuotas se consultan por p. El orden solo controla presentación.
No se ordenan listas de archivos para emparejarlas por posición. El plano PNG
original se conserva separado, sin cambiar sus píxeles ni superponer históricos.

Auditoría reproducible: `python scripts/auditar_html_anterior.py --revision c175c0d`.
El CSV [html_recibido.csv](validacion_mapa/html_recibido.csv) contiene los 30 casos,
incluidas las asociaciones ambiguas por áreas repetidas.

## Integración del cambio remoto concurrente

La consulta final de origin encontró `ac9bb20` y `f46028b` de otro integrante,
que reemplazan el HTML mientras se trabajaba. Se revisó íntegramente esa nueva
versión de 6,387,680 bytes. Sus 30 áreas y totales ya coinciden, sus existentes
por especie también, y sus puntos están dentro de los esquemas aproximados.
Sin embargo, las 30 composiciones finales difieren de las cuotas originales y
sus coordenadas no son las históricas. No incluye generador, semilla ni archivos
CSV de esa ejecución que permitan reconciliar esas diferencias.

La [auditoría adicional](validacion_mapa/html_remoto_f46028b.csv) registra cada
caso. Se conserva el commit remoto como ancestro mediante merge normal; su
[HTML exacto sigue consultable en Git](https://github.com/Reyivan777/Reto_Optimizacion_Estocastica/blob/f46028ba8d5c36276e01d2dd5d8a147fa1f44b07/DSATUR/mapa_interactivo_tresbolillo.html).
Se integra la corrección de áreas/totales, el plano y el diagrama de referencia.
El conflicto del artefacto generado se resuelve regenerándolo desde CSV
validados, sin sustituir las fuentes ni importar como cuotas verificadas una
composición sin procedencia. No se usa force push ni se reescribe la historia.

## Geometría y exportación

`crear_geometrias.py` ahora lee `data/poligonos_aproximados.csv`, corrigiendo la
ruta inexistente `datos/poligonos.csv`. La regeneración da el mismo GeoJSON
aportado: 30 IDs únicos, superficies concordantes y contornos válidos. No se
modifica ese archivo de referencia. `--salida build/archivo.geojson` permite
comprobarlo sin sobrescribirlo.

El modo predeterminado `simulada` conserva el rectángulo, generador, flujos
aleatorios y algoritmo originales. El modo opcional `aproximada` utiliza los
esquemas de seis vértices del GeoJSON, escalados por área, con centros,
aspectos y ángulos del plano. Estos esquemas **no son un trazado topográfico**.
Se construye la malla triangular dentro del contorno, incluidos agujeros,
se filtra contra existentes y se comprueba separación mínima de 3.4 m.
Se corrigió también la validación de demanda negativa y la posibilidad de
seleccionar dos veces una candidata por empates al agotar distancias.

El adaptador `terrenos.py` se integra en `ejecutar_escenario`. Resta el mínimo
x/y del contorno para trabajar localmente y guarda `origen_m`. La inversa es
`xy_destino = xy_local + origen_m`; la traslación conserva todas las distancias.
No se transfieren posiciones históricas a los contornos aproximados. Nuevas
existentes simuladas se generan solo en ese modo, respetando el inventario;
si se aporta un CSV se preservan sus posiciones, orden y especies. Una planta
fuera del contorno o demasiado próxima causa rechazo, sin recolocación silenciosa.

El modo `georreferenciada` requiere GeoJSON, CRS origen y destino explícitos,
destino proyectado en metros y posiciones existentes medidas en ese destino.
Pyproj usa `always_xy=True`; Shapely valida polígonos y multipolígonos. No se
asigna EPSG a los esquemas aproximados. Un archivo marcado `aproximado` se
rechaza como georreferenciado. El área debe concordar con el modelo a tolerancia
relativa 1e-6; no se escala un levantamiento para ocultar una discrepancia.
El usuario debe reconciliar áreas/inventario antes de usar datos incompatibles.

Las nuevas exportaciones añaden `distribucion_inicial.csv`, con posiciones y
especies aleatorias y columna `especie_dsatur`, y `metadatos.json`, con ID,
escenario, área, origen, contorno, semilla/configuración, matriz, catálogo,
motor y SHA-256 de inicial/final/comparación. Así se recalculan los tres J.
Los exportadores se usan sobre carpetas nuevas, nunca sobre los históricos.

## Mapa y validación

El HTML autónomo contiene datos generados, sin copia manual de coordenadas.
Plantilla, CSS y JS residen en `visualizacion/`; carga/validación están separadas
del renderizado. Canvas agrupa trazados por especie y condición; evita 120419
nodos DOM. El archivo corregido ocupa aproximadamente 4.3 MB, sin dependencias
de red, frente a 6.35 MB del recibido.

La vista global muestra 30 paneles con escalas locales independientes, sin
afirmar posición o vecindad geográfica. El modo individual ajusta el terreno;
permite filtros de especie y existentes/nuevas, zoom, arrastre, tabla por especie,
J por método, FF/FV/VV, matriz, semillas y hashes. Exporta el lienzo PNG y el CSV
filtrado. La tabla indica composición completa de la selección y el encabezado
indica el número visible. La distribución inicial solo se habilita cuando está
exportada para toda la selección.

Cada generación escribe JSON/CSV comparativos; si hay un fallo, elimina la
salida designada anterior y aborta, evitando publicar un mapa obsoleto. No se
modifican las fuentes. Mismos bytes de entrada y plantilla producen los mismos
bytes de HTML: no incluye fecha, carpeta de ejecución ni ruta absoluta.

El [reporte histórico](validacion_mapa/historicos.csv) cubre los 30 IDs, áreas,
total, histograma completo, existentes/nuevas por especie, geometría utilizada,
límites/dimensiones, pertenencia, separación, coordenadas únicas, competencia
final recalculada desde aristas, métricas MC, costo y presupuesto y hashes.
Total verificado: **120419**, de ellos **23569 existentes y 96850 nuevas**.
Separación observada mínima 3.399999999999915 m, dentro de tolerancia 1e-8 m.

Los históricos carecen de sidecar de hashes/área (estos campos también se marcan `no_disponible`, con preservación independiente por Git/SHA-256) y de CSV inicial: la inmutabilidad entre inicial/final y
J inicial/intermedio se marcan `no_disponible` en la auditoría del exportado,
sin convertir esa ausencia en aprobación. La [regresión 360](validacion_mapa/regresion_360.csv)
reprodujo independientemente todos sus J_base/J_dsatur/J_final con diferencia
máxima 9.094947017729282e-13, tolerancia 1e-8. En escenario 0 se compararon
además coordenadas y especies finales contra los 30 CSV históricos. Las nuevas
exportaciones sí permiten verificar directamente inicial/DSATUR/final e
inmutabilidad de las existentes.

## Evidencia y reproducción

Desde `DSATUR/`, instalar `config/requirements.txt` y compilar C++ si se usa.

```shell
python scripts/crear_geometrias.py --salida build/poligonos_reproducidos.geojson
python scripts/generar_mapa.py --reporte docs/validacion_mapa/historicos.json
python scripts/ejecutar_dos_etapas.py --poligonos 1,5 --escenarios 1 --mapa --sin-graficas
python scripts/ejecutar_dos_etapas.py --poligonos todos --motor cpp --geometria aproximada --mapa --sin-graficas
python tests/verificar_modelo.py
python tests/verificar_economia.py
python tests/verificar_cpp.py
python tests/verificar_posiciones.py
python tests/verificar_monte_carlo.py
python tests/verificar_supervivencia.py
python tests/verificar_sensibilidad.py
python tests/verificar_mejoras.py
python tests/verificar_mapa.py
python scripts/validar_integracion_mapa.py
```

**91/91 pruebas**, nueve baterías: 78 originales y 13 nuevas. Incluyen IDs,
áreas, cambio de archivo con total igual, mutación de especie/coordenadas,
contornos/agujeros, CRS inválido, inventario medido, rechazo de hashes,
economía P5, motores equivalentes, HTML idéntico y GeoJSON reproducido.
[Logs y conteos](validacion_mapa/pruebas.json) acompañan cada batería.

Se construyeron **30/30** esquemas aproximados, escenario 0, con cuotas fijas;
[reporte](validacion_mapa/aproximada_30.json) y [resultados](validacion_mapa/aproximada_30.csv).
Mantienen los costos/cuotas originales; el modo fijo sigue informando los seis
incumplimientos presupuestarios conocidos. No se atribuye factibilidad económica
a esos seis casos. La prueba económica usa las cuotas MILP y valida presupuesto.

El notebook ejecutó **18 celdas de código sin errores** en Python/simulada y
C++/aproximada, seleccionando P1/P5 en modo económico, exportando y generando sus
mapas. Validación con IPython en proceso; **no se certifica kernel Jupyter externo**.
No se sustituyeron las salidas históricas incrustadas del notebook.

En Chromium integrado se comprobaron selección, filtro P1/Agave salmiana existente
(46 plantas), área P1=1.28, P27=8, CSV descargado idéntico a P1 y PNG válido de
P27 (1012×800), inicial disponible en aproximada y zoom. Sin errores JS.
[Registro](validacion_mapa/navegador.json), [captura P1](validacion_mapa/P1_verificado.png)
y [PNG exportado P27](validacion_mapa/P27_exportado.png).

Se preservaron por SHA-256 **1836 archivos preexistentes** de resultados y
Algoritmo Genético. [Manifiesto](validacion_mapa/preservados_sha256.json) y
[control](validacion_mapa/preservacion.json). Las baterías heredadas crean algunas
carpetas nuevas de prueba con nombres de otras fases; se trasladan a `build/`
como temporales, sin publicar nuevos experimentos ni alterar sus módulos.

## Límites pendientes

No existen datos suficientes para certificar georreferenciación real, límites
medidos, precisión de colindancias o posiciones existentes reales. El soporte
CRS se prueba con una geometría sintética declarada expresamente como fixture,
sin atribuirle ubicación del proyecto. Faltan levantamiento, CRS, medición e
inventario espacial compatibles y confirmación del socio. Las densidades y C
siguen siendo supuestos del modelo; no se demuestra optimalidad espacial ni
una relación causal con supervivencia. No se amplía ninguna fase 4–8.
