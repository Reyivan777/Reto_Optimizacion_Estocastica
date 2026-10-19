# Reto de Optimización Estocástica — Reforestación

## Estado del proyecto (18 de octubre de 2026)

**Fase:** prototipo funcional con resultados preliminares; en preparación una refactorización didáctica y extensible para el Entregable 2. **Este README documenta el estado actual, no funcionalidades futuras.** El prototipo está centrado en el polígono P1 de la tabla del socio formador. No es un plano georreferenciado ni demuestra mayor supervivencia real.

### Objetivo
Planear la asignación de especies a posiciones dentro de polígonos de reforestación minimizando un índice de competencia, respetando el inventario de plantas existentes y las cantidades objetivo. El reto original también solicita estimar compras cuando se desconoce el inventario: **esa incertidumbre de adquisición no está implementada** en esta versión, que usa conteos conocidos y simula posiciones.

### Datos
- `data/especies.csv`: 10 especies, metas por ha y costos unitarios.
- `data/inventario.csv`: conteos de 10 especies para los 30 polígonos (300 registros) y áreas.
- `data/supervivencia_porcentajes.csv`: porcentajes históricos usados como contexto, no como matriz de competencia ni predicción.
- `data/fuentes_sha256.json`: huellas SHA-256 de documentos fuente, que sirven para identificar versiones; los documentos `sources/` **no están actualmente presentes en la rama main**.
- La meta de referencia es 658 plantas/ha, incluyendo las ya existentes. Se redondea la meta total por polígono y se reparten cuotas por especie conciliando los restos.

### Formulación matemática actual
Para cada polígono `p`:
- Conjuntos: `P={1,...,30}`; `S` (10 especies); `F_p` (posiciones de plantas existentes); `V_p` (posiciones nuevas seleccionadas); `U_p=F_p∪V_p`; `E_p` (pares de posiciones a distancia ≤ radio de interacción). **Las posiciones se almacenan como coordenadas (x,y)**, no vectores binarios de superficie.
- Parámetros: `A_p` área; `D=658` plantas/ha; `T_p=round(A_p D)` meta total; `n_ps` existentes por especie; `R_ps` cuota final; `q_ps=R_ps-n_ps` nuevas; `d_pij` distancia; `d_min=3.4 m` distancia mínima supuesta; `r=6 m` radio supuesto; `C_st` matriz de competencia; `w_pij=max(0,1-d_pij/r)`; `a_pis` especie prefijada en posiciones existentes.
- Variable binaria: `x_pis=1` si asignamos especie `s` a la posición nueva `i∈V_p`; `0` en otro caso. `y_pis=a_pis` para existentes y `y_pis=x_pis` para nuevas.
- Objetivo: minimizar `J = Σ_p Σ_{(i,j)∈E_p} w_pij Σ_s Σ_t C_st y_pis y_pjt` (cada par no dirigido una sola vez).
- Restricciones principales: una especie por posición nueva `Σ_s x_pis=1`; cuotas `n_ps+Σ_{i∈V_p} x_pis=R_ps`; total `Σ_s R_ps=T_p=|F_p|+|V_p|`; respetar especies y posiciones existentes; separación entre posiciones ocupadas ≥ `d_min`; `x_pis∈{0,1}`. La selección geométrica garantiza la distancia, antes de la optimización de especies.
- Índice de competencia: `J=J_FF+J_FV+J_VV` (pares de existentes, mixtos, y nuevos). `J_FF` no cambia al reasignar especies nuevas.

**Matriz C provisional e intercambiable:** penalización 3 entre plantas de la misma especie, 2 entre especies distintas del mismo género y 1 entre géneros distintos. No es un resultado ecológico validado. En futuros trabajos podrán proponerse parámetros basados en agua y nutrientes sin cambiar la estructura del modelo; la prioridad indicada por el profesor es formular y verificar correctamente el modelo.

### Funcionamiento del prototipo
1. Cargar inventario y metas y verificar integridad.
2. Para P1, aproximar el área con un rectángulo de superficie equivalente; simular coordenadas de las 165 plantas existentes conservando sus especies y conteos.
3. Crear una malla triangular de candidatas, descartar posiciones demasiado cercanas y seleccionar por dispersión geométrica las 677 posiciones nuevas. La selección de sitios **no optimiza la competencia conjuntamente con las especies**.
4. Construir el grafo espacial, conectando posiciones a menos de 6 m y aplicando `C` y pesos por distancia.
5. Comparar asignación aleatoria de especies (referencia), DSATUR adaptado (heurística de asignación que prioriza saturación de vecinos y menor incremento de competencia, respetando cuotas) y búsqueda local.
6. Búsqueda local: desde DSATUR, muestrear dos posiciones **nuevas** distintas uniformemente al azar; omitir si tienen la misma especie; calcular `ΔJ=J_despues-J_antes` usando aristas incidentes; intercambiar especies **solo si ΔJ<0**. No se mueven plantas existentes ni cambian las cantidades por especie. Se prueban **6,000 propuestas** por defecto; no necesariamente son 6,000 intercambios aceptados. No certifica óptimo local ni global.
7. Monte Carlo espacial: repetir el proceso en **12 escenarios de posiciones simuladas**, conservando las cantidades; en cada escenario comparar asignación aleatoria, DSATUR y DSATUR+búsqueda local. Esta simulación **no** estima incertidumbre de conteos ni compras.

### Resultados guardados (P1)
- Área: **1.28 ha**; existentes: **165**; nuevas: **677**; meta final: **842**.
- Índice escenario 0: aleatoria **1089.007**, DSATUR **991.748**, DSATUR + búsqueda local **874.525**; mejora frente a la referencia aleatoria **19.70%**.
- Monte Carlo: **12/12 escenarios completados**, mejora media frente a referencia aleatoria **20.15%** (rango aprox. **19.25%–21.24%**). Solo corresponde a supuestos actuales.
- Costo de adquisición P1: **15,903.5 unidades monetarias**; la fuente no especifica moneda.
- Se calcularon cuotas para los **30 polígonos**: **183.01 ha**, **23,569 existentes**, **120,419 meta total**, **96,850 nuevas**. **No se han optimizado espacialmente los 30 polígonos; únicamente P1.**
- `resultados/` contiene gráficos `01_poligono.png` (geometría), `02_existentes.png` (existentes simuladas), `03_candidatas.png` (posiciones posibles), `04_grafo.png` (vecindades), `05_especies.png` (matriz conceptual), `06_busqueda_local.png` (descensos al aceptar intercambios), `07_distribucion_final.png` (solo nuevas / todas), `08_comparacion.png` (métodos), `09_monte_carlo.png` (12 escenarios); y CSV de cuotas, distribución, comparación, estadísticas y configuración.
- La gráfica de búsqueda local representa **propuestas** en eje X y **competencia J** en eje Y: tramos planos = ninguna mejora aceptada; descensos = intercambio aceptado.

### Límites y precauciones
- Geometría rectangular, posiciones inventadas, `d_min=3.4m`, `r=6m`, pesos espaciales y matriz C son supuestos exploratorios. El contorno real, coordenadas, topografía, agua, nutrientes y separación específica por especie no se han incorporado.
- El modelo usa cuotas fijas. La variación permitida de ±10% indicada en la presentación del socio formador aún no está implementada.
- Los 12 escenarios son exploratorios y la variación mezcla posiciones simuladas, referencia aleatoria y propuestas aleatorias de mejora; no equivale a evidencia de supervivencia ni al objetivo original de compra bajo inventario incierto.
- P13 = 5.05 ha es interpretación editorial pendiente de confirmar; las etiquetas del mapa no coinciden necesariamente con IDs de la tabla. Las superficies tabuladas suman 183.01 ha frente a la referencia aproximada de 183 ha.
- La referencia presupuestal por hectárea no está impuesta como restricción. Los costos de adquisición no incluyen transporte, riego, mantenimiento ni reposición.
- El archivo `sources/` es necesario para **regenerar** el notebook con `scripts/crear_notebook.py`, pero actualmente **no está subido**. El notebook existente sí usa `data/` para ejecutar cálculos. `resultados/modelo_reforestacion.html` puede generarse con el script de ejecución, pero **no está versionado actualmente**.

## Estructura y ejecución
- `modelo_reforestacion.ipynb`: notebook con formulación, implementación y resultados guardados (17 secciones).
- `scripts/crear_notebook.py`: regenera notebook y extracción de datos **solo si se restauran las fuentes**; **sobrescribe** el notebook y cualquier cambio manual.
- `scripts/ejecutar_notebook.py`: ejecuta notebook con kernel limpio y exporta HTML.
- `requirements.txt`: dependencias fijadas.
- `data/`: datos de entrada.
- `resultados/`: tablas, figuras y configuración.

En la raíz del repositorio, en Windows:
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts/ejecutar_notebook.py
```
Alternativamente, abrir `modelo_reforestacion.ipynb` en VS Code/Jupyter y ejecutar las celdas con el entorno configurado. El notebook espera que el directorio de trabajo sea la raíz que contiene `data/`. El comando de ejecución sobrescribe el notebook con sus nuevas salidas y genera `resultados/modelo_reforestacion.html`; evitar ejecutarlo sobre trabajo no guardado.

## Plan aprobado para el siguiente desarrollo (NO IMPLEMENTADO)
1. **Refactorización didáctica:** secciones claras; tablas de conjuntos, índices, parámetros, variables, objetivo y restricciones; equivalencia entre notación matemática y Python; ejemplos P1.
2. **Separación de matriz C:** configuración editable y validada, sin incrustar pesos en la heurística; mantener C=3/2/1 hasta recibir coeficientes fundamentados en agua/nutrientes.
3. **Generalización a P1, varios o 30 polígonos:** configuración de selección, procesamiento independiente, diagnósticos de factibilidad, tablas agregadas, límites de rendimiento y pruebas de escala; no afirmar ejecuciones de polígonos no procesados.
4. **Instrumentación de búsqueda local:** registrar propuestas, pares distintos, rechazados y aceptados, mejora y tiempos; comparar 6,000 intentos fijos con propuestas proporcionales a `|V_p|` (factor configurable). Conservar criterio `ΔJ<0`; no introducir cambios de heurística sin comparativas.
5. **Gráficas simplificadas:** cuatro principales (existentes, final, comparación, Monte Carlo), las otras diagnósticas.
6. **Validación:** entorno limpio, semillas, cuotas, posiciones fijas, distancia, identidad de objetivos, deltas de intercambios, reproducibilidad y al menos un polígono adicional de tamaño razonable. Registrar errores y limitaciones.
7. **Documentación:** actualizar README y reporte de resultados solo con datos efectivamente obtenidos. Si falta `sources/`, resolver esa dependencia sin inventar fuentes; proteger el notebook contra sobreescritura accidental.

## Extensiones posteriores (FUERA DEL SIGUIENTE COMMIT)
- Optimizar simultáneamente **sitios y especies** (actualmente los sitios se eligen antes).
- Permitir cuotas finales por especie en margen ±10% manteniendo la meta total.
- Modelar probabilísticamente **inventarios desconocidos** y compras/risgo de faltantes usando datos apropiados, separado de Monte Carlo espacial.
- Justificar/calibrar la matriz de competencia con agua y nutrientes, añadir condiciones geográficas reales y comparar más heurísticas.

## Historial conceptual
- Primera entrega: investigación, formalización conceptual, grafos y Monte Carlo de adquisición propuesto.
- Tras junta con socio formador: datos de 10 especies, 30 polígonos, supervivencia y costos; prototipo con inventarios conocidos.
- 15 oct 2026: archivos CSV, scripts y salidas guardadas en GitHub.
- 18 oct 2026: actualización de README con explicación explícita del modelo, resultados, limitaciones y plan del próximo commit. **Esta actualización es documentación; no cambia el algoritmo.**
