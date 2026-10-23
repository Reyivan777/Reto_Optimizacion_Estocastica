"""Genera polígonos esquemáticos escalados al área indicada por el CSV."""
import argparse, csv, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'data'/'poligonos_aproximados.csv'; dst=ROOT/'data'/'poligonos_aproximados.geojson'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--salida',type=Path,default=dst,help='Elegir otra ruta para verificar sin sobrescribir el GeoJSON')
dst=parser.parse_args().salida
features=[]
for r in csv.DictReader(src.open(encoding='utf-8-sig')):
    area=float(r['area_ha'])*10000; ar=float(r['aspecto']); w=math.sqrt(area*ar); h=area/w
    raw=[(-.50*w,-.48*h),(.42*w,-.50*h),(.52*w,-.12*h),(.48*w,.46*h),(-.38*w,.52*h),(-.52*w,.08*h)]
    a0=abs(sum(raw[i][0]*raw[(i+1)%6][1]-raw[(i+1)%6][0]*raw[i][1] for i in range(6)))/2
    f=math.sqrt(area/a0); ang=math.radians(float(r['angulo'])); cx=(float(r['cx_px'])-300)*3; cy=(610-float(r['cy_px']))*3
    ring=[]
    for x,y in raw:
        x*=f; y*=f; ring.append([cx+x*math.cos(ang)-y*math.sin(ang),cy+x*math.sin(ang)+y*math.cos(ang)])
    ring.append(ring[0]); features.append({'type':'Feature','properties':{'id':int(r['id']),'area_ha':area/10000,'aproximado':True},'geometry':{'type':'Polygon','coordinates':[ring]}})
dst.parent.mkdir(parents=True,exist_ok=True)
dst.write_text(json.dumps({'type':'FeatureCollection','name':'poligonos_aproximados','features':features},indent=2),encoding='utf-8')
print(f'GeoJSON listo: {dst}')
