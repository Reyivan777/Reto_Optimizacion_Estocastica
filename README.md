# Optimización estocástica de reforestación

Abra **modelo_reforestacion.ipynb**. Contiene el desarrollo matemático, la implementación completa y las salidas de una ejecución verificada para el polígono P1 de la tabla del socio formador.

## Archivos

- `modelo_reforestacion.ipynb`: notebook principal, 17 secciones, código editable y resultados guardados.
- `data/`: inventarios de 30 polígonos, especies, costos, porcentajes históricos y huellas de las fuentes.
- `resultados/`: tablas calculadas, imágenes, configuración y vista HTML del notebook.
- `sources/`: referencias originales de solo lectura; no modificadas.
- `scripts/crear_notebook.py`: extracción de datos y construcción del notebook. **Regenerarlo reemplaza el notebook**, incluidas modificaciones manuales; no es necesario para ejecutar el análisis.
- `scripts/ejecutar_notebook.py`: ejecución en kernel limpio y exportación HTML.
- `requirements.txt`: versiones de las dependencias principales utilizadas.

## Ejecución

En VS Code, abra la carpeta del proyecto, abra el notebook y seleccione `.venv/Scripts/python.exe` como entorno. Ejecute todas las celdas en orden. En esta ubicación, cree el entorno siguiendo los pasos siguientes antes de ejecutar. El notebook ya incluye las salidas de la ejecución verificada.

Para trasladarlo a otra computadora, copie el notebook y `data/` juntos; también se recomienda conservar `sources/` y este README. Desde la carpeta copiada:

```shell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Seleccione ese entorno en Jupyter o VS Code. Para verificar sin interfaz:

```shell
.venv\Scripts\python scripts/ejecutar_notebook.py
```

El directorio de trabajo debe ser la carpeta que contiene el notebook y `data/`. Los resultados se regeneran en `resultados/`. No hay rutas temporales o privadas incrustadas en el notebook. El entorno `.venv` no debe copiarse entre computadoras.

## Alcance y supuestos

Se conocen los conteos existentes; solo se simulan coordenadas. La geometría rectangular, aplicar una separación mínima de 3.4 m a todos los pares, el radio de 6 m y la competencia 3/2/1 son supuestos de prueba. La malla candidata de 3.4 m no equivale a la densidad final. Se seleccionan sitios antes de asignar especies; la búsqueda local intercambia especies, no posiciones. La meta de 658 plantas/ha incluye existentes y nuevas; el redondeo y las cuotas se concilian exactamente.

La versión implementa cuotas fijas; la flexibilidad de ±10% y los patrones agrupados quedan documentados como extensiones. La menor competencia calculada no constituye evidencia de mayor supervivencia. Los costos se expresan en unidades monetarias porque las tablas no explicitan moneda.

Los IDs P1–P30 corresponden a la tabla, no a las etiquetas del mapa. La superficie P13=5.05 ha conserva una interpretación editorial por confirmar. La suma tabulada y la referencia aproximada de 183 ha se comparan en el notebook.

Las 12 simulaciones predeterminadas son exploratorias. Los fallos de construcción se guardan sin reemplazarlos; las estadísticas se calculan sobre los escenarios completados, cuyo número se informa. Aumentar las simulaciones requiere medir primero el tiempo de ejecución.

