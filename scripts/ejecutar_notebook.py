"""Ejecuta una copia con el mismo intérprete; el notebook fuente se conserva."""
from pathlib import Path
import argparse,sys,tempfile,json,os
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida',type=Path,default=ROOT/'resultados/ejecucion_notebook')
    parser.add_argument('--sin-kernel',action='store_true',help='Ejecutar con IPython en proceso, sin sockets Jupyter')
    args=parser.parse_args();out=args.salida.resolve();out.mkdir(parents=True,exist_ok=True)
    nb=nbformat.read(ROOT/'modelo_reforestacion.ipynb',as_version=4)
    if args.sin_kernel:
        from IPython.core.interactiveshell import InteractiveShell
        from IPython.utils.capture import capture_output
        shell=InteractiveShell.instance()
        shell.enable_gui=lambda gui=None: None  # backend inline: no GUI ni sockets
        shell.run_line_magic('matplotlib','inline')
        original=Path.cwd()
        os.chdir(ROOT)
        try:
            contador=0
            for cell in nb.cells:
                if cell.cell_type != 'code':continue
                contador+=1
                with capture_output() as captured:
                    result=shell.run_cell(cell.source,store_history=True)
                if result.error_before_exec or result.error_in_exec:
                    raise RuntimeError(f'Celda {contador} falló') from (result.error_before_exec or result.error_in_exec)
                cell.execution_count=contador
                cell.outputs=[]
                if captured.stdout:cell.outputs.append(nbformat.v4.new_output('stream',name='stdout',text=captured.stdout))
                if captured.stderr:cell.outputs.append(nbformat.v4.new_output('stream',name='stderr',text=captured.stderr))
                for item in captured.outputs:
                    cell.outputs.append(nbformat.v4.new_output('display_data',data=item.data,metadata=item.metadata))
        finally:os.chdir(original)
    else:
        with tempfile.TemporaryDirectory() as temporal:
            kernel=Path(temporal)/'kernels'/'reforestacion';kernel.mkdir(parents=True)
            (kernel/'kernel.json').write_text(json.dumps(dict(argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],display_name='Reforestación',language='python')))
            anterior=os.environ.get('JUPYTER_PATH')
            os.environ['JUPYTER_PATH']=temporal+(os.pathsep+anterior if anterior else '')
            try:
                NotebookClient(nb,timeout=300,kernel_name='reforestacion',resources={'metadata':{'path':str(ROOT)}}).execute()
            finally:
                if anterior is None:os.environ.pop('JUPYTER_PATH',None)
                else:os.environ['JUPYTER_PATH']=anterior
    nbformat.validate(nb)
    nbformat.write(nb,out/'modelo_reforestacion_ejecutado.ipynb')
    html,_=HTMLExporter().from_notebook_node(nb)
    (out/'modelo_reforestacion.html').write_text(html,encoding='utf-8')
    print('Notebook ejecutado y HTML:',out)

if __name__=='__main__':main()
