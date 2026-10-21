import sys,json,hashlib,subprocess
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
root=Path.cwd();sys.path.insert(0,str(root/'src'))
from reforestacion.config import perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.experimento import ejecutar_escenario
out=root/'resultados'/('posiciones_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir()
(root/'build/posiciones_salida.txt').write_text(str(out))
hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'resultados').rglob('*') if p.is_file()}
(out/'historicos_sha256.json').write_text(json.dumps(hashes,indent=2))
d=Datos(root);C=cargar_competencia(root/'config/competencia.json',d.S);rows=[]
for motor in ('python','cpp'):
 for p in (1,13,5):
  for e in range(12):
   f,r=ejecutar_escenario(p,e,d,perfil('completo',motor=motor),C)
   f['entradas_sha256']=hashlib.sha256(r['g']['U'].tobytes()+r['fijas'].tobytes()+r['q'].tobytes()).hexdigest()
   f['solucion_sha256']=hashlib.sha256(r['final'].astype(np.int64).tobytes()).hexdigest();rows.append(f)
  print(motor,p,flush=True)
(out/'referencia_previa.json').write_text(json.dumps(dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),filas=rows),indent=2))
print(out)
