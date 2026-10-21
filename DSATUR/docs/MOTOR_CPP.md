# Motor espacial C++17

## Instalación

Desde DSATUR/, con las dependencias Python de config/requirements.txt y un compilador GCC/Clang C++17:

```powershell
# Windows: MinGW-w64/TDM-GCC en PATH; Python y compilador de 64 bits.
python scripts/compilar_cpp.py
python tests/verificar_modelo.py
python tests/verificar_economia.py
python tests/verificar_cpp.py
python scripts/ejecutar_dos_etapas.py --motor cpp --poligonos 5 --escenarios 1 --sin-graficas
```

Linux, viable por diseño (no verificado en este equipo Windows):

```bash
python scripts/compilar_cpp.py --compiler g++
python tests/verificar_cpp.py
python scripts/ejecutar_dos_etapas.py --motor cpp --poligonos 1 --escenarios 12 --sin-graficas
```

El compilador genera build/reforestacion.dll o build/libreforestacion.so. Los binarios y temporales se ignoran en Git. Recompilar tras cambiar cpp/motor.cpp. No utilizar fast-math ni FMA: el script fija -O3 -std=c++17 -ffp-contract=off. Windows fue probado con TDM-GCC 10.3.0 y CPython 3.12.10 x64. MSVC y macOS no se dan por verificados; el script actual usa opciones GCC/Clang. No se necesita CMake, cabeceras Python ni pybind11. ctypes es parte de la biblioteca estándar; esta elección evita una dependencia binaria adicional.

Si el sandbox restringe temporales, crear build/tmp y configurar TMP/TEMP a su ruta absoluta antes de ejecutar las pruebas. Esto corrige un problema del entorno, sin modificar las pruebas originales.

## Selección e integración

El motor predeterminado sigue siendo Python. En el notebook elegir MOTOR="cpp"; esa opción controla tanto el recorrido didáctico como ejecutar_lote y la etapa económica integrada. En código:

```python
cfg = perfil('completo', motor='cpp', poligonos=(5,), escenarios=12)
fila, detalle = ejecutar_escenario(5, 0, datos, cfg, C)
```

La selección explícita no hace fallback silencioso. Una biblioteca ausente o ABI incompatible produce un error con instrucciones. Los manifiestos del ejecutor económico y benchmark registran versión ABI, hashes de fuente/binario y compilador. Las versiones de Python/librerías y los parámetros siguen documentados en cada experimento.

Pipeline: inventario/cuotas económicas → posiciones existentes NumPy → malla y filtro cKDTree → selección dispersa C++ → grafo cKDTree/NetworkX → DSATUR C++ → propuestas NumPy y swaps C++ → validaciones originales y economía exacta Python → CSV/PNG Python. No cambian C, HiGHS, restricciones ni función objetivo.

## Equivalencia y decisiones numéricas

Se preservan el orden de malla, primer índice del máximo, orden de vecinos CSR, saturación, grado ponderado y desempates por cuota e índice. Las coordenadas y las etiquetas existentes se generan exclusivamente con los flujos NumPy originales. Las propuestas locales llaman a rng.choice exactamente una vez por intento, como Python; se pasan como una matriz entera a C++. busqueda_con_propuestas permite entregar una secuencia precalculada y comparar desde la misma asignación inicial.

El grado ponderado se calcula con sum de Python antes de la llamada C++: su algoritmo para floats cambió en CPython 3.12. Rehacerlo como suma secuencial modificó empates en la primera prueba; se detectó y corrigió antes de aceptar la migración. Referencia primaria: [implementación de sum en CPython 3.12](https://github.com/python/cpython/blob/3.12/Python/bltinmodule.c). Los deltas suman cada lista incidente por separado, igual que las expresiones NumPy escalares del modelo. No se redondean costos incrementales ni se añaden tolerancias a desempates.

Aceptación de intercambio: delta < -1e-10. Comprobación del objetivo incremental: atol=1e-7, rtol=0 en C++. Comparación de J e historia entre motores/históricos: tolerancia absoluta 1e-8. Conteos, etiquetas, coordenadas y restricciones discretas se comprueban exactamente. El presupuesto económico se valida con enteros decimales, sin tolerancia monetaria. Las validaciones espaciales conservan la tolerancia geométrica histórica de 1e-8 m. No se promete igualdad entre versiones/compiladores sin repetir las pruebas, ni identidad de RNG C++ porque no se introduce uno.

## Memoria y límites

Los núcleos usan CSR O(N+E), costos/vistos O(N*K), vector de distancias O(candidatas), propuestas O(intentos) y trayectoria O(aceptados); no generan matrices de distancias N². DSATUR escanea los vértices libres sin ordenarlos; selección y DSATUR aún tienen crecimiento cuadrático. No se migran el grafo ya acelerado por cKDTree ni la simulación de existentes porque el perfil prioriza otros componentes. La creación de objetos NetworkX y el generador Python de propuestas siguen limitando la aceleración total.

benchmark_motores.py procesa una distribución a la vez, escribe filas JSONL inmediatamente y conserva solo ultima_distribucion.csv. La memoria no crece con el número de escenarios por acumulación de grafos. El ejecutor normal también retiene filas resumen y un detalle por vez, sin acumular todas las distribuciones. Para experimentos grandes puede usarse el patrón del benchmark: consumir y guardar cada fila; no construir listas de detalles. La paralelización y la justificación estadística pertenecen a fase 5.

RSS incluye Python, librerías, NetworkX y C++; no es solo memoria de arrays. Se informa el máximo residente del proceso con GetProcessMemoryInfo en Windows (ru_maxrss en Linux), y la memoria inicial. No se usa tracemalloc como sustituto de memoria nativa. La DLL se carga antes de comenzar el tiempo de trabajo medido; los benchmarks no incluyen importaciones ni compilación. La primera exportación y todas las conversiones/propuestas/validaciones sí se incluyen. Sin PNG para medir el motor; las figuras permanecen disponibles en notebook/ejecutor.

## Reproducción

```bash
python scripts/perfilar_python.py --poligono 5
python scripts/benchmark_motores.py --progresivo --presupuesto-segundos 600
python scripts/validar_historico_cpp.py
python scripts/verificar_notebook_cpp.py --en-proceso
```

Cada comando crea su propia carpeta nueva. El presupuesto del benchmark decide si puede programar la escala siguiente usando tiempos ya observados; esa estimación se registra exclusivamente como decisión de recursos. Las aceleraciones siempre son cocientes de dos tiempos efectivamente medidos. 10000 escenarios de P1 son 10000 ejecuciones; 10000 por cada uno de los 30 serían 300000, y no se confunden.

El notebook se validó con IPython en proceso: 17 celdas de código, seis PNG embebidos y 30 polígonos económicamente/espacialmente factibles. Sin --en-proceso se intenta un kernel Jupyter externo con el mismo intérprete; ese modo no logró iniciar celdas en este sandbox y fue interrumpido, por lo que sigue pendiente validarlo fuera de él.
