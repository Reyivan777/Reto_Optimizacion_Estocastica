# Matrices alternativas y sensibilidad — fase 7

## Alcance y evidencia ecológica

La matriz original `config/competencia.json` permanece intacta. Esta fase añade
un experimento independiente; no cambia la economía, DSATUR, búsqueda local,
geometrías, radios, separación, inventario ni supervivencia. El notebook añade
solo una celda documental. No se implementa fase 8.

Fuentes primarias consultadas el 23 de octubre de 2026:

|Recurso|Hallazgo pertinente|Lo que no permite inferir|
|---|---|---|
|Agua: Grossiord et al. (2019), [Tree Physiology, DOI 10.1093/treephys/tpy080](https://doi.org/10.1093/treephys/tpy080); [resumen de los autores en PNNL](https://www.pnnl.gov/publications/prolonged-warming-and-drought-modify-belowground-interactions-water-among-coexisting)|Experimento de calentamiento y reducción de precipitación en un bosque semiárido con árboles y gramíneas. El reparto de fuentes y profundidad de absorción cambió con los tratamientos; los ajustes no evitaron sistemáticamente el estrés.|Una penalización fija entre las diez especies del proyecto, ni que sequía multiplique todos sus pares por el mismo factor.|
|Nutrientes y arquitectura radicular: Nord, Zhang y Lynch (2011), [Functional Plant Biology, DOI 10.1071/FP11130](https://doi.org/10.1071/FP11130)|En frijol, manipular concentración de fósforo y acceso a raíces vecinas distinguió efectos de disponibilidad de recursos y presencia del vecino. Cambió la arquitectura radicular; concentración y volumen requieren control experimental.|Transportar coeficientes de frijol a agaves, nopales, mezquite o yuca; convertir parentesco en absorción o mortalidad medida.|

Estas investigaciones motivan revisar recursos y raíces, pero **no calibran C**.
El catálogo local no contiene humedad por profundidad/temporada, textura y
retención del suelo, nutrientes disponibles, consumo por especie y edad,
perfiles radiculares, solapamiento medido ni respuestas de pares en campo.
No se inventan profundidades ni demandas por especie. Una futura calibración
requiere esas mediciones, controles sin vecino, réplicas y validación externa.
Parentesco puede ser un proxy exploratorio, no una medición de similitud
funcional. La simetría, aditividad, no negatividad y radio fijo siguen siendo
supuestos; facilitación, asimetría y variación temporal quedan sin modelar.

## Configuración matemática

`config/sensibilidad_competencia.json` conserva el orden exacto del catálogo y
marca cada variante como `heuristica_no_calibrada`, con justificación. Se admite
una matriz explícita simétrica, finita, no negativa de 10×10 mediante `matriz`,
o tres `pesos` (exactamente una modalidad). Nombres únicos; `original` reservado.
Una matriz nula es válida para diagnóstico; porcentajes con referencia cero
quedan faltantes, nunca se imputa una mejora.

La familia incluida es

\[
C_{ab}=f+g\,\mathbf1[\operatorname{genero}(a)=\operatorname{genero}(b)]
       +i\,\mathbf1[a=b].
\]

El género se obtiene del primer término del nombre del catálogo, sin editarlo.
La misma especie satisface ambos indicadores. Los parámetros son adimensionales
y elegidos para sensibilidad, sin asignarlos artificialmente a agua, nutrientes
o raíces como tres procesos independientes (eso podría contarlos dos veces).

|Nombre|f|g|i|Misma especie / mismo género distinto / distinto género|
|---|---:|---:|---:|---|
|original|1|1|1|3 / 2 / 1; se carga el JSON original, no se sustituye|
|contraste_moderado|1|0.5|0.5|2 / 1.5 / 1; alternativa principal|
|genero_bajo|1|0.5|1|2.5 / 1.5 / 1|
|genero_alto|1|1.5|1|3.5 / 2.5 / 1|
|identidad_baja|1|1|0.5|2.5 / 2 / 1|
|identidad_alta|1|1|1.5|3.5 / 2 / 1|
|uniforme|1|0|0|1 / 1 / 1; control sin contraste taxonómico|

Las perturbaciones unilaterales ±0.5 son incrementos finitos, no derivadas ni
intervalos de confianza ecológicos. En posiciones fijas, C uniforme hace que
J sea independiente de etiquetas; su solución puede cambiar por desempate.
Con posiciones activadas aún puede reducir la masa de aristas.

En un grafo fijo, la alternativa principal satisface
`C_moderada = 0.5*C_original + 0.5*unos`, de modo que
`J_moderada = 0.5*J_original + 0.5*sum(pesos)`. Preserva el orden matemático
de todas las asignaciones y sirve también como control del efecto de escala.
Las perturbaciones unilaterales sí cambian las preferencias relativas. Al
optimizar posiciones la masa de aristas puede variar, por lo que la equivalencia
de orden de la alternativa principal deja de estar garantizada.

## Comparación e interpretación

Cada matriz produce una solución mediante el pipeline previo, mismo polígono,
índice, semilla, sitios iniciales, base aleatoria y cuotas. Se comprueba el hash
de entradas y se validan cuota, inventario, distancia y presupuesto económico.
Los planes se calculan una vez por polígono y se reutilizan sin depender de C.
En modo fijo se reporta cumplimiento presupuestal, sin exigirlo artificialmente.
Posiciones permanece apagada por defecto; `--optimizar-posiciones` usa mixta.

Para cada solución A y matriz evaluadora B se calcula

\[
J_B(A)=\sum_{(u,v)\in E_A}w_{uv}C^B_{y_u,y_v},\qquad
\Delta_B(A)=J_B(A)-J_B(\mathrm{original}).
\]

Negativo favorece A **bajo la misma B**. No se compara J_A(A) con
J_original(original) para afirmar mejora. Se publican todos los cruces, la
diferencia absoluta y porcentual, fracción de etiquetas nuevas distintas e
igualdad de posiciones finales. Si posiciones está activa se evalúa el grafo
final propio de cada solución. No se altera la distancia ni el radio.

`resumen_pareado.csv` informa solicitados, válidos, excluidos, media, desviación,
SE, IC95% Student puntual y percentiles empíricos de las diferencias, por
polígono/motor/solución/evaluadora. Mejora/empate/empeora usa tolerancia 1e-8.
Una observación no tiene SE/IC. Sin referencia no se inventa diferencia; con
fallos los estadísticos son condicionales a pares completos y se informa su
denominador. Los errores técnicos se propagan. No hay cobertura simultánea,
calibración ni prueba de superioridad ecológica. Doce escenarios son una
comparación exploratoria fija, no una confirmación de precisión de fase 5.
Una solución optimizada bajo B puede perder frente a otra bajo B: búsqueda
acotada, sin reinicios nuevos ni garantía de óptimo global/local certificado.

## Reproducción y salidas

Desde `DSATUR/`:

```shell
python scripts/analizar_sensibilidad.py --motores python,cpp
python scripts/analizar_sensibilidad.py --modo fijo --poligonos 1 --escenarios 1 --motores cpp --optimizar-posiciones
python tests/verificar_sensibilidad.py
python scripts/validar_fase7.py resultados/sensibilidad_fase7_FECHA --snapshot build/fase7_preservados.json
```

Requiere compilar el motor cuando se solicita C++ (`scripts/compilar_cpp.py`).
No hay dependencias nuevas ni fallback silencioso. `--config` admite otro JSON;
`--semilla`, `--escenarios`, `--poligonos` y `--max-corridas` son explícitos.
Cada ejecución crea una carpeta UTC nueva, sin sobrescribir históricos.
El límite predeterminado es 1000 pipelines; se rechaza un lote excesivo antes
de ejecutarlo. El módulo conserva detalles de un solo polígono/índice/motor,
no todos los grafos del lote. Tablas escalares permanecen en memoria.

Se guardan hipótesis y matrices efectivas, planes, escenarios con estados y
hashes de entradas/solución, evaluación cruzada y resumen. Los campos
`peso_i_j` suman pesos de aristas por par **no ordenado** de etiquetas finales:
permiten recalcular J bajo cualquier C simétrica sin guardar grafos. No son
volúmenes de raíces. El manifiesto conserva configuración, semillas, versiones,
base Git, motor y hashes de entradas/código. El hash del JSON externo se registra
además de su copia efectiva. No contiene credenciales ni rutas de fuentes ajenas.
El snapshot de preservación debe capturarse antes de editar, no regenerarse al
validar. El validador principal exige cero exclusiones y comprueba los cruces
mediante las masas, resúmenes, motores, regresión histórica y notebook.

## Resultados y validación

Evidencia principal: `resultados/sensibilidad_fase7_20261023T201037_339060Z/`.
P1/P13/P5 × 12 índices × siete matrices × dos motores: **504/504 pipelines
válidos**, sin exclusiones; **3528 evaluaciones cruzadas**, 294 resúmenes.
Modo económico, semilla 20261014, 6000 propuestas locales, posiciones apagadas.
Las **252 parejas Python/C++** coinciden exactamente en hash de solución y
entradas; objetivos dentro de 1e-8. Cuotas/compras/costos y geometría inicial
permanecen pareados. No se suman resultados como si fueran los 30 polígonos.

Diferencia media de J frente a la solución original, **evaluadas ambas bajo
C original** (un motor; el otro coincide):

|Solución|P1|P13|P5|
|---|---:|---:|---:|
|contraste_moderado|-0.622579|3.109579|-0.342780|
|genero_bajo|2.004718|3.828793|6.643480|
|genero_alto|-2.656606|-1.981472|-4.929409|
|identidad_baja|-2.610992|-1.643868|-1.197339|
|identidad_alta|0.882343|2.382356|-3.204741|
|uniforme|243.893648|803.348030|1252.408912|

Bajo su propia matriz, `genero_alto` mejora frente a la referencia original
12/12, 9/12 y 9/12; diferencias medias -4.558207/-5.070705/-10.104005.
`uniforme` empata 36/36 bajo C uniforme pero empeora 36/36 bajo C original:
la interpretación depende de la métrica. Los IC, percentiles y otros cruces
están completos en los CSV; no se selecciona una matriz como verdad ecológica
por el valor mínimo obtenido bajo su propia hipótesis.

**Sensibilidad numérica de la heurística:** aunque la alternativa moderada
preserva el orden matemático en grafo fijo, su trayectoria no es idéntica.
Bajo C original mejora 15/36, empata 3/36 y empeora 18/36; modifica en promedio
52.3171% de etiquetas nuevas. Diagnóstico P1/índice 0: primera divergencia en
paso 177, vértice 425 (índices desde cero), especies 2/6. Costos originales
1.7333333333333347 y 1.7333333333333352; en la variante ambos se redondean a
1.516666666666668, activando el desempate por cuota restante (35/51).
`diagnostico_afin.json` conserva los valores y
`python scripts/diagnosticar_afin.py` los reproduce exactamente. Se atribuye
a casi empates y redondeo, no a una preferencia ecológica nueva ni a un error
de la identidad matemática. No se modifica el desempate ni los motores:
esa mejora pertenecería a una fase posterior y rompería las regresiones.

Validación final: **66/66 pruebas**, cero fallos: 9 modelo, 6 economía, 5 C++,
16 posiciones, 6 Monte Carlo, 12 supervivencia y 12 sensibilidad. Las nuevas
cubren configuración, matrices generales/nulas/inválidas, suma independiente,
identidad afín, denominador cero, falta de referencia, fallos sin imputación,
errores técnicos, motores, posiciones y exportaciones CLI fijo/económico.
Se repitió únicamente sensibilidad al añadir el control analítico afín;
`pruebas.json` registra esa repetición y sus logs finales.

**144/144 regresiones** contra fase 4, P1/P13/P5 × 12 × ambos motores ×
posiciones apagadas/mixtas: hashes de entrada/solución idénticos y tolerancia
J=1e-8. **1548 archivos previos** preservados por SHA-256, incluidos código,
configuración C, datos, geometrías, históricos y Algoritmo Genético.
Las 3528 evaluaciones y diferencias se recalcularon con las masas por par:
error máximo **1.2732925824820995e-11**. Resúmenes y equivalencia verificados;
36 celdas previas del notebook idénticas, incluidas salidas/metadatos, más una
celda documental nueva; nbformat válido. No se reejecutan celdas intactas.

Las seis carpetas pequeñas adicionales `sensibilidad_fase7_*` son pruebas CLI
independientes (tres pares fijo/económico), con siete matrices y posiciones
mixtas P1/índice 0; no se mezclan con los 504 pipelines principales. La batería
anterior de supervivencia crea dos carpetas nuevas de fase 6: son verificaciones
del ejecutor existente, no nueva funcionalidad ni evidencia histórica editada.

Tiempo del comparador/exportación: **292.042423 s**, excluye planificación e
importaciones; coincidió parcialmente con pruebas y regresiones en otro proceso.
No se usa como benchmark de aceleración. No se midió RSS ni se validó Linux.
Sin comparación exhaustiva de siete matrices con posiciones mixtas en los tres
polígonos; esa opción se verifica en integración P1 y los motores originales
mantienen sus regresiones mixtas. Ningún resultado certifica óptimo espacial.

Persisten rectángulos simulados, matriz heurística y supuestos económicos
heredados. Ningún resultado mide supervivencia, consumo de agua ni adquisición
de nutrientes. No se cambia el escenario de supervivencia de fase 6.
