"""Ejecutar lotes sin abrir VS Code/Jupyter."""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reforestacion.config import perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.experimento import ejecutar_lote,guardar_ejecucion


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--perfil',choices=['rapido','completo'],default='rapido')
    parser.add_argument('--poligonos',default='1',help='1, 4,25 o todos')
    parser.add_argument('--escenarios',type=int)
    parser.add_argument('--presupuesto',choices=['fijo','proporcional'],default='fijo')
    parser.add_argument('--intentos',type=int,default=6000)
    parser.add_argument('--factor',type=int,default=10)
    parser.add_argument('--matriz',type=Path,default=ROOT/'config/competencia.json')
    parser.add_argument('--salida',type=Path,default=ROOT/'resultados/ultima_ejecucion')
    args=parser.parse_args()
    ids='todos' if args.poligonos=='todos' else tuple(int(p) for p in args.poligonos.split(','))
    cambios=dict(poligonos=ids,presupuesto=args.presupuesto,intentos_local=args.intentos,intentos_por_nueva=args.factor)
    if args.escenarios is not None:cambios['escenarios']=args.escenarios
    cfg=perfil(args.perfil,**cambios);datos=Datos(ROOT);C=cargar_competencia(args.matriz,datos.S)
    lote=ejecutar_lote(datos,cfg,C);guardar_ejecucion(args.salida,datos,cfg,C,lote)
    print(lote[['poligono','escenario','estado','detalle']].to_string(index=False))
    print('Resultados:',args.salida.resolve())
    return 1 if lote.estado.ne('ok').any() else 0

if __name__=='__main__':sys.exit(main())
