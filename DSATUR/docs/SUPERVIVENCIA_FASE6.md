# Fase 6: supervivencia y escenarios exploratorios

Implementación independiente sobre `4100608` (fase 5), 23 de octubre de 2026.
No se modifica la decisión económica ni la distribución espacial. El modelo
calcula consecuencias **condicionales a hipótesis**, sin atribuir a DSATUR
un aumento de supervivencia. Fases 7 y 8 quedan pendientes.

## Auditoría y disponibilidad de evidencia

`data/supervivencia_porcentajes.csv` tiene diez filas, una por especie, y tres
columnas anuales 2021/2022/2023. Las diez especies coinciden exactamente con
el catálogo; no hay faltantes, duplicados, valores no finitos ni porcentajes
fuera de [0,100]. 2021 contiene 100 en todas las filas. No hay aumentos entre
columnas. Mínimo observado 72.63%, máximo 100%; último año 2023. No representa
una medición de 2026. El ejecutor verifica el contrato antes de simular;
un aumento se registra, sin rechazarlo como si se conociera una cohorte común.

La transcripción `Presentacion_Socio_Formador.md`, diapositiva 15, denomina
el monitoreo «5% de la superficie» y presenta porcentajes con base 2021=100.
La diapositiva 17 contiene magnitudes decimales por hectárea, aun cuando el
título habla de individuos. Por ejemplo, Lechuguilla tiene 2.1/1.98/1.84 vivos:
2.1×0.9265=1.94565 difiere del último dato; 1.98×0.9265=1.83447 se aproxima,
pero esto no confirma la definición del denominador ni una cohorte seguida.
No convertir esos decimales en tamaños muestrales ni ajustar una binomial a
supuestas observaciones individuales. El CSV no contiene identificadores de
cohorte, parcela, planta, tamaño muestral ni errores de medición.

**Riesgo alto:** interpretar 2023 como supervivencia acumulada o condicional
sin confirmar el seguimiento cambia el horizonte. Se exige una interpretación
declarada en la configuración: el ejemplo usa 2023/100 como probabilidad de
un **periodo hipotético sin duración calibrada**. No multiplica años, no ajusta
una tasa anual, no extrapola una curva temporal ni calcula IC de los porcentajes
observados. Es necesario obtener cohortes, fechas, denominadores enteros y
protocolo de muestreo para estimar incertidumbre histórica o tasas temporales.

`data/especies.csv` tiene precios por unidad de adquisición; no acredita fecha
de vigencia, moneda, transporte, establecimiento, riego, mantenimiento, mano
de obra ni reposición integral. La transcripción de la conversación con el
socio (`Presentación-socio-formador.txt`, apartado económico y reposición)
confirma que se estaban considerando únicamente plantas y que las obligaciones
de reposición dependen del contrato. Los importes generales mencionados no
son costos por especie/polígono; no se incorporan como observaciones.
**Riesgo alto:** tratar adquisición como costo total del programa. El informe
usa u.m. y factores de estrés arbitrarios; hace falta una cotización desglosada
y el contrato para una decisión financiera real.

Las dos transcripciones se consultaron como referencias de solo lectura del
proyecto. Sus SHA-256 coinciden con `data/fuentes_sha256.json`; el registro
`auditoria_fuentes_documentales.json` guarda la comprobación. No se requieren
esas transcripciones externas para volver a ejecutar el modelo sobre los CSV.
La falta de datos calibrables queda registrada; no bloquea escenarios
exploratorios explícitos y sí impide presentar predicciones validadas.

## Formulación y horizonte

Por polígono y especie, n es el inventario conocido, q la compra inicial
conocida y R=n+q la meta del plan económico (o fijo). No se modela inventario
desconocido. El primer periodo tiene supervivencias hipotéticas pE para
existentes y pN para nuevas. Se simula independientemente:

```text
VE ~ Binomial(n, pE), VN ~ Binomial(q, pN)
D = R - VE - VN
K | D ~ Binomial(D, rho)
VR | K ~ Binomial(K, pR)
Vfinal = VE + VN + VR
deficit = R - Vfinal
```

rho es la probabilidad de seleccionar cada vacante para reposición, no una
cuota fraccionaria que se redondea. Cada vacante conserva su especie. Solo hay
un ciclo: las reposiciones que mueren no se reponen otra vez. Si rho>0 se añade
una etapa de evaluación exclusivamente para las reposiciones; los supervivientes
de la primera etapa permanecen vivos por supuesto. No es una comparación de
tratamientos a idéntica fecha de calendario. No se construyen posiciones ni
se certifican restricciones geométricas después de mortalidad/reposición.

Las esperanzas exactas bajo esos supuestos son:

```text
E[V0] = n*pE + q*pN
E[D] = R - E[V0]
E[K] = rho*E[D]
E[Vfinal] = E[V0] + pR*E[K]
E[deficit] = R - E[Vfinal]
```

No se redondean las esperanzas a compras enteras. La simulación sí mantiene
conteos enteros y 0≤VR≤K≤D≤R. No garantiza alcanzar R; ni siquiera reponer todas
las muertes lo garantiza cuando pR<1. Independencia entre plantas, especies y
polígonos es una hipótesis: no representa sequías comunes, plagas, incertidumbre
de parámetros ni heterogeneidad espacial. J y la matriz C no intervienen en
estas probabilidades. A igual inventario y cuotas, cambiar solo la distribución
DSATUR no genera un beneficio de supervivencia en este modelo.

Con precios de catálogo c, factores fI/fR y presupuesto B escalado por fB:

```text
costo_inicial = sum(q*c*fI)
costo_reposicion = sum(K*c*fR)
costo_total = costo_inicial + costo_reposicion
presupuesto_escenario = B*fB
```

Se comparan importes decimales sin tolerancia monetaria en cada realización y
polígono. Se informa exceso, saldo y frecuencia de exceso. El presupuesto es
una referencia conjunta de adquisición inicial y reposiciones en el escenario,
sin actualización temporal, descuento ni fondo adicional. Las compras de
reposición representan una necesidad exploratoria **sin recorte presupuestario**:
si exceden B se reporta y no se presentan como plan factible. No se autoriza
gasto, no se reparan cuotas con precios nuevos ni se transfieren saldos entre
polígonos. `cumple_compra_inicial` no certifica financiación de reposiciones.

## Configuración y reproducción

Desde `DSATUR/`, con las dependencias ya existentes:

```shell
python scripts/explorar_supervivencia.py --poligonos 1,13,5 --escenarios 1000
python scripts/explorar_supervivencia.py --poligonos todos --escenarios 1000
python scripts/explorar_supervivencia.py --modo fijo --poligonos 1,5 --escenarios 1000
python scripts/explorar_supervivencia.py --hipotesis config/escenarios_supervivencia.json
python tests/verificar_supervivencia.py
python scripts/validar_fase6.py resultados/supervivencia_fase6_FECHA
```

Configuración versionada: `config/escenarios_supervivencia.json`. Nombre,
justificación, interpretación y horizonte son obligatorios. Se puede elegir
una columna histórica y factores; la API admite probabilidades por especie.
Los factores no se recortan silenciosamente si producen p>1. Los valores
predeterminados de `Hipotesis` también quedan expandidos en el manifiesto.

Las seis hipótesis incluidas son referencia transportada (pE=1, rho=0),
mortalidad alta (pN×0.8), mortalidad de existentes (pE=0.9), reposición de todas
las vacantes una vez (rho=1), precios de adquisición +25%, y presupuesto -20%.
Los porcentajes de estrés son elecciones ilustrativas, no mediciones ni
recomendaciones. Sin datos adicionales no se selecciona una hipótesis como
la más probable. En reposición pR=2023/100 por el mismo supuesto de transporte.

La semilla 20261014 y `SeedSequence([semilla,6,poligono,indice]).spawn(4)`
separan existentes/nuevas/selección de reposiciones/supervivencia de reposición,
sin tocar flujos espaciales. Las hipótesis usan los mismos flujos por stock:
el orden del lote no cambia los resultados y modificar solo precios o B
preserva exactamente las vidas simuladas. No se presupone dominancia muestra
a muestra al cambiar probabilidades de una binomial.

El tamaño fijo de 1000 realizaciones por hipótesis/polígono es un presupuesto
computacional para esta exploración, no la confirmación espacial de fase 5 ni
un ajuste a observaciones históricas. Se exporta SE e IC95% puntual de Student
de la **media Monte Carlo condicional** mediante la rutina validada de fase 5.
Los percentiles 5/25/50/75/95 describen resultados simulados, no incertidumbre
histórica. No hay parada opcional ni garantía de precisión general. Frecuencias
0 o 1 y su SE empírico cero no certifican probabilidades extremas en general.

## Resultados medidos

Ejecución principal nueva:
`resultados/supervivencia_fase6_20261023T195729_586867Z/`.
30 polígonos, 1000 índices por hipótesis: **180000 realizaciones**, 6000 agregados
completos (1000 por hipótesis). No son 180000 plantaciones adicionales.
Las compras económicas iniciales cuestan 2277016 u.m.; presupuesto base total
2287625 u.m.; meta total 120419 plantas. Se verifica cada polígono por separado.

|Hipótesis|Vivos finales esperados|Déficit esperado|Adquisición total esperada (u.m.)|
|---|---:|---:|---:|
|Referencia transportada|107354.854000|13064.146000|2277016.0000|
|Mortalidad alta|90597.683200|29821.316800|2277016.0000|
|Mortalidad de existentes|104997.954000|15421.046000|2277016.0000|
|Reposición, un ciclo|118318.738063|2100.261937|2584913.5168|
|Precios +25%|107354.854000|13064.146000|2846270.0000|
|Presupuesto -20%|107354.854000|13064.146000|2277016.0000|

En reposición se esperan **13064.146** adquisiciones adicionales, con costo de
307897.5168 u.m. Los precios +25%, el presupuesto -20% y la reposición excedieron
el presupuesto individual en los **1000/1000 índices de cada uno de los 30
polígonos**. En las otras tres hipótesis el costo inicial es fijo y factible;
no hay adquisiciones adicionales. No se concluye factibilidad operativa ni
costos integrales a partir de esas comprobaciones.

Para los agregados de los 30 polígonos, la media simulada de vivos de referencia
fue 107358.031, SE 3.257580, IC95% [107351.638516,107364.423484]; con reposición,
118318.441, SE 1.385743, IC95% [118315.721700,118321.160300]. Las esperanzas
analíticas permiten comprobar el simulador sin depender de un IC. Cambiar
solo precios/B produjo exactamente las mismas vidas por índice. El tiempo
de simulación/exportación fue **40.169264 s**, sin planificación/importaciones
previas ni pruebas/regresión. No es un benchmark comparativo de motores.

## Salidas y validación

Cada ejecución crea una carpeta UTC nueva; no sobrescribe resultados previos:

- `auditoria_historico.json`: esquema, cobertura y límites del CSV.
- `hipotesis.json`, `planes.json`: supuestos y planes económicos reutilizados.
- `proyeccion_por_especie.csv`, `proyeccion_por_poligono.csv`: esperanzas analíticas,
  stocks, probabilidades, metas, déficits y costos por origen.
- `simulaciones.csv`: realizaciones enteras, compras totales, saldo y exceso.
- `estadisticas.csv`, `riesgo_presupuesto.csv`: IC/SE/percentiles y denominadores;
  las medias se comparan con las esperanzas analíticas cuando corresponde.
- `agregado_subconjunto.csv`, `estadisticas_agregadas.csv`: suma solo de los
  polígonos solicitados por índice y `todos_cumplen_presupuesto`, sin compensación.
- `manifiesto.json`: base Git, versiones, fuentes/código/configuración por SHA-256,
  semilla, interpretación, horizonte, supuestos efectivos y alcance de tiempos.

Validación final: **54/54 pruebas**, cero fallos: 9 modelo, 6 economía, 5 C++,
16 posiciones, 6 Monte Carlo y 12 supervivencia. Incluye vectores inválidos,
probabilidades 0/1, stocks cero, fracción de reposición, mortalidad total,
presupuesto decimal exacto, no mutación, semillas, reproducción CLI y suma por
índice. La distribución simulada se contrasta con media y varianza binomiales
derivadas para una instancia conocida de reposición.

El validador recalcula las esperanzas por sitio independientemente, revisa
**720** medias Monte Carlo contra la esperanza (límite de comprobación de seis
SE, no criterio de precisión), conteos, agregados y fuentes. Ejecuta **144**
regresiones espaciales P1/P13/P5 × 12 índices × dos motores × posiciones
apagadas/mixtas, contra la evidencia de fase 4 usada también en fase 5. Se
conservan hashes de entradas/soluciones y tolerancia J de 1e-8. Las **35 celdas
anteriores del notebook**, incluidas salidas y metadatos, permanecen idénticas;
solo se añade una explicación opcional, sin volver a ejecutar sus celdas.

Se preservan **1461 archivos previos** por SHA-256 (datos, geometrías, C++,
configuración anterior, módulos, históricos y todo Algoritmo Genético).
`pruebas.json`, logs, `regresion_espacial.csv`, `preservados_sha256.json` y
`validacion.json` contienen evidencia de la ejecución de validación. El
snapshot opcional del validador debe capturarse antes de trabajar; no se
reconstruye retrospectivamente para certificar preservación.

El commit de esta entrega cierra exclusivamente la fase 6. Sin push ni avance
a matrices alternativas, calibración de C o mejoras de la fase 7/8.
