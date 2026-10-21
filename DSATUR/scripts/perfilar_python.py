"""Record cProfile separately: instrumented times are not speedup benchmarks."""
import argparse
import cProfile
from datetime import datetime,timezone
from pathlib import Path
import pstats
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.experimento import ejecutar_escenario,guardar_detalle_poligono

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--poligono',type=int,default=5)
    p=parser.parse_args().poligono
    ruta=ROOT/'resultados'/('perfil_python_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    ruta.mkdir(exist_ok=False)
    d=Datos(ROOT);cfg=perfil('completo',escenarios=1);C=cargar_competencia(ROOT/'config/competencia.json',d.S)
    profiler=cProfile.Profile();profiler.enable()
    f,r=ejecutar_escenario(p,0,d,cfg,C)
    guardar_detalle_poligono(ruta,d,f,r,C,graficas=False)
    profiler.disable();profiler.dump_stats(str(ruta/'python.prof'))
    with (ruta/'perfil.txt').open('w',encoding='utf-8') as stream:
        pstats.Stats(profiler,stream=stream).sort_stats('cumulative').print_stats(60)
    archivo=ruta/'perfil.txt'
    archivo.write_text(archivo.read_text(encoding='utf-8').rstrip()+'\n',encoding='utf-8')
    print(ruta)
