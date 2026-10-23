DESTINO EN GITHUB: crear DSATUR_realista/ en la raíz del repositorio y copiar el contenido completo de esta carpeta conservando las subcarpetas.

Archivos: datos/poligonos.csv (superficies según inventario del ZIP); crear_geometrias.py (geometrías esquemáticas exactas en área); ejecutar.py (colocación tresbolillo y comparación); requirements.txt (dependencias Python). El motor C++ del ZIP se incorpora copiando cpp/motor.cpp y src/reforestacion/motor_cpp.py, algoritmos.py y datos.py, más scripts/compilar_cpp.py; esas copias no están incluidas en este paquete individual.

Las geometrías son aproximaciones dibujadas a partir del plano y escaladas a las áreas del inventario CSV. Solo se usan P1–P30. El código genera sitios a separación elegida entre 3.4 y 4.0 m y exporta coordenadas y métricas. Para el motor C++ se requiere compilar el código C++17 del ZIP.

Nota: al copiar este paquete, mantener estructura:
DSATUR_realista/
  README.txt
  requirements.txt
  datos/poligonos.csv
  crear_geometrias.py
  ejecutar.py

Instalar: python -m pip install -r requirements.txt
Crear geometría: python crear_geometrias.py
Ejecutar demostración espacial: python ejecutar.py --separacion 3.7 --escenarios 1
