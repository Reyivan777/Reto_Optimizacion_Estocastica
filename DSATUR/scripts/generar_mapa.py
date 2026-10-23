"""Genera un mapa autónomo validado, sin cambiar coordenadas ni resultados."""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reforestacion.mapa_interactivo import generar_mapa

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resultados',type=Path,default=ROOT/'resultados')
    parser.add_argument('--salida',type=Path,default=ROOT/'mapa_interactivo_tresbolillo.html')
    parser.add_argument('--poligonos',default='todos')
    parser.add_argument('--reporte',type=Path)
    args = parser.parse_args()
    ids = None if args.poligonos=='todos' else list(map(int,args.poligonos.split(',')))
    print(generar_mapa(ROOT,args.resultados,args.salida,ids,args.reporte))
