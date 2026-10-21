"""Execute an independent notebook copy, preserving committed historical outputs."""
from datetime import datetime,timezone
from pathlib import Path
import nbformat
from nbclient import NotebookClient
import json
import sys
import argparse
import os
from time import perf_counter
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--en-proceso',action='store_true',help='IPython sin sockets de kernel externo')
    args=parser.parse_args()
    ruta=ROOT/'resultados'/('notebook_cpp_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    ruta.mkdir(exist_ok=False)
    nb=nbformat.read(ROOT/'modelo_reforestacion.ipynb',as_version=4)
    nb.cells[1].source=nb.cells[1].source.replace('MOTOR = "python"','MOTOR = "cpp"')
    for cell in nb.cells:
        if cell.cell_type=='code':cell.outputs=[];cell.execution_count=None
    kernels=ROOT/'build'/'kernels'; spec=kernels/'reforestacion_cpp';spec.mkdir(parents=True,exist_ok=True)
    (spec/'kernel.json').write_text(json.dumps(dict(argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
        display_name='Reforestacion CPP validation',language='python')),encoding='utf-8')
    km=KernelManager(kernel_name='reforestacion_cpp',kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernels)]))
    inicio=perf_counter()
    try:
        if args.en_proceso:
            from IPython.core.interactiveshell import InteractiveShell
            from IPython.utils.capture import capture_output
            shell=InteractiveShell.instance();os.chdir(ROOT)
            import matplotlib
            matplotlib.use('module://matplotlib_inline.backend_inline')
            from matplotlib_inline.backend_inline import configure_inline_support
            configure_inline_support(shell,'inline')
            count=0
            for cell in nb.cells:
                if cell.cell_type!='code':continue
                count+=1
                with capture_output() as captured:
                    result=shell.run_cell(cell.source,store_history=True)
                cell.execution_count=count; cell.outputs=[]
                if captured.stdout:cell.outputs.append(nbformat.v4.new_output('stream',name='stdout',text=captured.stdout))
                if captured.stderr:cell.outputs.append(nbformat.v4.new_output('stream',name='stderr',text=captured.stderr))
                for rich in captured.outputs:
                    cell.outputs.append(nbformat.v4.new_output('display_data',data=rich.data,metadata=rich.metadata))
                result.raise_error()
                print(f'Celda {count}: OK',flush=True)
        else:
            NotebookClient(nb,km=km,timeout=600,startup_timeout=60,resources={'metadata':{'path':str(ROOT)}}).execute()
    finally:
        nbformat.write(nb,ruta/'modelo_reforestacion_cpp.ipynb')
    (ruta/'validacion.json').write_text(json.dumps(dict(motor='cpp',metodo='IPython en proceso' if args.en_proceso else 'kernel externo',
        celdas_ejecutadas=sum(c.cell_type=='code' for c in nb.cells),errores=0,segundos=perf_counter()-inicio),indent=2)+'\n',encoding='utf-8')
    print(ruta,flush=True)
