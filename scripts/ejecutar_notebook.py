"""Ejecutar en kernel limpio, guardar outputs y generar vista HTML portable."""
from pathlib import Path
import os, sys, json
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

root=Path(__file__).resolve().parents[1]
os.chdir(root)
# Kernel y archivos de ejecución dentro de la carpeta del proyecto.
jupyter=root/'.jupyter_local'
kernel=jupyter/'kernels'/'reforestacion'
kernel.mkdir(parents=True,exist_ok=True)
(kernel/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
    'display_name':'Reforestación (local)','language':'python'}),encoding='utf-8')
os.environ['JUPYTER_PATH']=str(jupyter)
os.environ['JUPYTER_RUNTIME_DIR']=str(jupyter/'runtime')
os.environ['IPYTHONDIR']=str(jupyter/'ipython')
os.environ['MPLCONFIGDIR']=str(jupyter/'matplotlib')
path=root/'modelo_reforestacion.ipynb'
nb=nbformat.read(path,as_version=4)
for i,c in enumerate(nb.cells):
    if c.cell_type=='code':
        compile(c.source,f'celda_{i}','exec')
client=NotebookClient(nb,timeout=240,kernel_name='reforestacion',resources={'metadata':{'path':str(root)}})
client.execute()
nbformat.validate(nb)
nbformat.write(nb,path)
html,_=HTMLExporter().from_notebook_node(nb)
(root/'resultados'/'modelo_reforestacion.html').write_text(html,encoding='utf-8')
print('Ejecución completa:',sum(c.cell_type=='code' for c in nb.cells),'celdas de código, sin errores.')
for c in nb.cells:
    for output in c.get('outputs',[]):
        if output.output_type=='stream': print(output.text[:1500])
