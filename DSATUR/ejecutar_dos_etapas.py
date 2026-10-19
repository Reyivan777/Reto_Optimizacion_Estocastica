"""Interfaz reproducible opcional; el notebook sigue siendo la interfaz didáctica."""
import argparse
from pathlib import Path
from reforestacion.config import perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.dos_etapas import ejecutar

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modo',choices=['fijo','economico'],default='economico')
    parser.add_argument('--etapa',choices=['economica','ambas'],default='ambas')
    parser.add_argument('--poligonos',default='todos',help='todos o IDs separados por coma')
    parser.add_argument('--escenarios',type=int,default=1)
    parser.add_argument('--sin-comparacion',action='store_true')
    parser.add_argument('--sin-graficas',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent; datos=Datos(root)
    ids='todos' if args.poligonos=='todos' else tuple(map(int,args.poligonos.split(',')))
    cfg=perfil('completo',poligonos=ids,escenarios=args.escenarios)
    C=cargar_competencia(root/'config/competencia.json',datos.S)
    ruta,_,_,_=ejecutar(datos,cfg,C,modo=args.modo,etapa=args.etapa,
        comparar=not args.sin_comparacion,graficas=not args.sin_graficas,
        progreso=lambda f:print(f"P{f['poligono']} e={f['escenario']}: {f['estado_factibilidad']}",flush=True))
    print(ruta)
