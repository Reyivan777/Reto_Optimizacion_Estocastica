# Plan de implementación progresiva

Una fase por solicitud. Leer este documento, ESTADO_IMPLEMENTACION.md, Git y las dependencias antes de continuar. No modificar Algoritmo Genético, datos sincronizados ni evidencia histórica. Python sigue disponible como referencia. No se afirma optimalidad global espacial.

|Fase|Objetivo y alcance|Dependencias|Aceptación|
|---|---|---|---|
|1|Perfilar Python; migrar selección dispersa, DSATUR y deltas/intercambios a C++17; selector de motor, notebook, compilación y mediciones.|Código actual, compilador C++17, NumPy/SciPy.|Entradas y propuestas comunes, invariantes y regresiones verificadas, benchmarks por etapa/pared/memoria, notebook ejecutable.|
|2|Importar geometrías reales GeoJSON, CRS proyectado, contornos/agujeros y existentes georreferenciadas; conservar modo simulado.|Geometrías verificadas, CRS y origen del inventario.|Geometrías irregulares reales verificadas, áreas contrastadas y separación válida. Imágenes no sustituyen datos.|
|3|Mapas HTML individuales/global real, leyendas, filtros y comparación inicial/final; exportar PNG.|Fase 2 para mapa global geográfico; evaluar renderizado masivo.|Mapas reproducibles desde resultados, legibles y fluidos sin posiciones geográficas inventadas.|
|4|Explorar movimientos de nuevas plantas, sustituciones de candidatas y actualización incremental de grafo.|Motor validado y límites de fase 2.|Existentes fijas, cuotas exactas, pertenencia y distancia; medir beneficio y costo frente a posiciones fijas.|
|5|Escalar Monte Carlo espacial, convergencia, error estándar, IC y percentiles; evaluar paralelismo/agregación.|Motor y benchmarks; inventario conocido documentado.|Número de escenarios justificado estadísticamente, semillas y denominadores; sin compras aleatorias automáticas.|
|6|Supervivencia esperada y escenarios exploratorios de mortalidad, reposición, precios y presupuesto.|Auditar CSV histórico y disponibilidad de costos reales.|Separar observaciones, proyecciones e hipótesis; sin causalidad competencia-supervivencia no validada.|
|7|Matriz alternativa configurable y sensibilidad; revisar agua, nutrientes y raíces con fuentes.|Documentar supuestos y evidencia; conservar C original.|Coeficientes heurísticos identificados y comparación reproducible; no inventar mediciones.|
|8|Mejoras DSATUR/local, reinicios y decisiones económicas conjuntas; interfaz, exportaciones e informe.|Fases anteriores, datos suficientes y baselines.|Proyecto reproducible, pruebas finales, documentación matemática y presentación comprensible.|

## Diseño de fase 1

Base Git: 49b17fa, main, checkout inicialmente limpio. Referencia económica: docs/VALIDACION_ECONOMICA.md; referencia espacial: docs/MODELO_CUOTAS_FIJAS_HISTORICO.md y resultados guardados.

Interfaz C ABI mediante ctypes de biblioteca compartida C++17: no requiere pybind11 ni paquetes nuevos. Python valida buffers contiguos, conserva NumPy RNG y entrega propuestas idénticas a C++. Adyacencias CSR conservan orden de aristas. Sin fast-math ni contracción FMA. Desempates originales y tolerancia local -1e-10. Candidatas y DSATUR siguen cuadráticos, con menores constantes y sin matriz densa de distancias. Economía permanece en SciPy/HiGHS.

Orden: línea base y perfil → núcleos e integración → equivalencia y fallos → benchmarks 1/12 y escalamiento 100/1000/10000 según recursos → notebook y regresión histórica → documentación, pruebas y commit. No avanzar a fase 2 en esta solicitud.

Medir en el mismo equipo, sin profiler durante benchmarks, tiempo completo y por etapa, exportación y memoria de proceso. Separar costo de propuestas Python, conversiones y núcleo nativo. Una escala de 10000 escenarios de un polígono NO representa 10000 por cada uno de los 30. No extrapolar aceleraciones como mediciones. Procesar un escenario a la vez y guardar filas sin retener distribuciones.
