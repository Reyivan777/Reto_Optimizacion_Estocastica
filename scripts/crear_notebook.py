"""Copia segura del notebook canónico; ya no extrae datos ni depende de sources/."""
from pathlib import Path
import argparse,shutil
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destino',required=True,type=Path,help='Archivo nuevo; nunca sobrescribe uno existente')
    args=p.parse_args()
    if args.destino.resolve()==(ROOT/'modelo_reforestacion.ipynb').resolve() or args.destino.exists():
        p.error('Destino existente: se conserva su contenido. Elija un nombre nuevo.')
    args.destino.parent.mkdir(parents=True,exist_ok=True)
    # Exclusión de creación: protege también ante una carrera entre procesos.
    with args.destino.open('xb') as salida,(ROOT/'modelo_reforestacion.ipynb').open('rb') as entrada:
        shutil.copyfileobj(entrada,salida)
    print(args.destino)

if __name__=='__main__':main()
