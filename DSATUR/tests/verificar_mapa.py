"""Regresiones de asociación, geometrías y exportación desde fuentes reales."""
import json
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest
from dataclasses import replace
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box, mapping
from scipy.spatial import cKDTree
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reforestacion.mapa_interactivo import construir_datos,generar_mapa,leer_distribucion
from reforestacion.terrenos import cargar_geometrias,TerrenoPoligonal
from reforestacion.geometria_real import candidatos_tresbolillo
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.config import perfil
from reforestacion.experimento import ejecutar_escenario,guardar_detalle_poligono
from reforestacion.dos_etapas import ejecutar


class PruebasMapa(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=Datos(ROOT);cls.cfg=perfil('completo',escenarios=1)
        cls.C=cargar_competencia(ROOT/'config/competencia.json',cls.d.S)
        cls.payload,cls.reporte=construir_datos(ROOT,ROOT/'resultados')

    def test_30_ids_areas_cuotas_existentes_competencia(self):
        self.assertEqual(list(self.payload['poligonos']),[f'P{p}' for p in range(1,31)])
        self.assertTrue(all(r['estado']=='pasa' for r in self.reporte))
        for p in range(1,31):
            m=self.payload['poligonos'][f'P{p}'];a,n,R,q=self.d.poligono(p,self.cfg)
            self.assertEqual(m['id'],p);self.assertEqual(m['area_ha'],a)
            np.testing.assert_array_equal(m['conteos'],R)
            np.testing.assert_array_equal(m['existentes'],n)
            U,y,nf=leer_distribucion(ROOT/f'resultados/P{p}/distribucion.csv',self.d.S)
            np.testing.assert_array_equal(np.asarray(m['puntos'])[:,:2],U)
            np.testing.assert_array_equal(np.asarray(m['puntos'])[:,2],y)
            self.assertEqual(m['nf'],nf)
        self.assertEqual(self.payload['poligonos']['P1']['total'],842)
        self.assertEqual(self.payload['poligonos']['P2']['total'],4369)
        self.assertTrue(all(r['coordenadas_iguales_historico'] for r in self.reporte))

    def test_inicial_historica_no_se_inventa(self):
        self.assertTrue(all(p['inicial'] is None for p in self.payload['poligonos'].values()))
        self.assertTrue(all(r['comprobaciones']['competencia_inicial']=='no_disponible' for r in self.reporte))

    def copiar(self,t,ids):
        t=Path(t)
        shutil.copy(ROOT/'resultados/modelo_completo/configuracion.json',t/'configuracion.json')
        for p in ids:
            (t/f'P{p}').mkdir()
            for n in ('distribucion.csv','comparacion.csv','monte_carlo.csv'):
                shutil.copy(ROOT/f'resultados/P{p}'/n,t/f'P{p}'/n)
        return t

    def test_carpeta_equivocada_y_metricas_se_rechazan(self):
        with tempfile.TemporaryDirectory() as t:
            t=self.copiar(t,[1])
            shutil.copy(ROOT/'resultados/P30/distribucion.csv',t/'P1/distribucion.csv')
            _,r=construir_datos(ROOT,t,[1])
            self.assertEqual(r[0]['estado'],'falla')
            self.assertEqual(r[0]['comprobaciones']['por_especie'],'falla')
            with self.assertRaises(ValueError):generar_mapa(ROOT,t,t/'rechazado.html',[1])
            self.assertFalse((t/'rechazado.html').exists())

    def test_total_igual_no_basta(self):
        # P5 y P21 tienen ambos 5264 plantas, con distinto inventario y coordenadas.
        with tempfile.TemporaryDirectory() as t:
            t=self.copiar(t,[5])
            shutil.copy(ROOT/'resultados/P21/distribucion.csv',t/'P5/distribucion.csv')
            _,r=construir_datos(ROOT,t,[5])
            c=r[0]['comprobaciones'];self.assertEqual(c['total'],'pasa')
            self.assertEqual(c['existentes_por_especie'],'falla')
            self.assertEqual(c['competencia_final'],'falla')

    def test_especie_cambiada_distancia_y_limites(self):
        for caso in ('especie','distancia','limites'):
            with self.subTest(caso=caso),tempfile.TemporaryDirectory() as t:
                t=self.copiar(t,[1]);f=t/'P1/distribucion.csv';tabla=pd.read_csv(f)
                if caso=='especie':tabla.loc[200,'especie']=self.d.S[0]
                elif caso=='distancia':tabla.loc[200,['x_m','y_m']]=tabla.loc[201,['x_m','y_m']].to_numpy()
                else:tabla.loc[200,'x_m']=-1
                tabla.to_csv(f,index=False);_,r=construir_datos(ROOT,t,[1])
                self.assertEqual(r[0]['estado'],'falla')

    def test_html_reproducible_y_csv_identicos(self):
        with tempfile.TemporaryDirectory() as t:
            a=generar_mapa(ROOT,ROOT/'resultados',Path(t)/'a.html')
            b=generar_mapa(ROOT,ROOT/'resultados',Path(t)/'b.html')
            self.assertEqual(a.read_bytes(),b.read_bytes())
            texto=a.read_text(encoding='utf-8');raw=texto.split('<script id="datos-mapa" type="application/json">',1)[1].split('</script>',1)[0]
            self.assertEqual(json.loads(raw),json.loads(json.dumps(self.payload)))
            self.assertNotIn('http://',texto);self.assertNotIn('https://',texto)

    def test_ids_sin_orden_lexicografico_y_seleccion(self):
        d,r=construir_datos(ROOT,ROOT/'resultados',[30,2,10,1])
        self.assertEqual(list(d['poligonos']),['P1','P2','P10','P30'])
        for v in ([1,1],[0],[31]):
            with self.assertRaises(ValueError):construir_datos(ROOT,ROOT/'resultados',v)

    def test_configuracion_faltante_no_se_infiere(self):
        with tempfile.TemporaryDirectory() as t:
            t=self.copiar(t,[1]);(t/'configuracion.json').unlink()
            _,r=construir_datos(ROOT,t,[1]);self.assertEqual(r[0]['estado'],'falla')

    def test_geojson_por_id_areas_dimensiones_y_huecos(self):
        geoms=cargar_geometrias(ROOT/'data/poligonos_aproximados.geojson',self.d.areas.to_dict())
        self.assertEqual(set(geoms),set(range(1,31)))
        for p,g in geoms.items():
            self.assertAlmostEqual(g.area,self.d.areas.loc[p]*10000,places=6)
            self.assertGreater(g.bounds[2]-g.bounds[0],0)
        g=Polygon([(0,0),(30,0),(30,30),(0,30)],holes=[[(10,10),(20,10),(20,20),(10,20)]])
        pts=candidatos_tresbolillo(g,35,3.4)
        self.assertTrue(TerrenoPoligonal(g).contiene(pts).all())
        self.assertFalse(cKDTree(pts).query_pairs(3.4-1e-8))
        self.assertFalse(TerrenoPoligonal(g).contiene([[15,15]])[0])
        with self.assertRaises(ValueError):candidatos_tresbolillo(g,-1)

    def test_generador_geometrias_fuente_correcta_reproducible(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=[Path(t)/n for n in ('a.geojson','b.geojson')]
            for f in (a,b):
                subprocess.run([sys.executable,str(ROOT/'scripts/crear_geometrias.py'),'--salida',str(f)],check=True,capture_output=True)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            self.assertEqual(json.loads(a.read_text()),json.loads((ROOT/'data/poligonos_aproximados.geojson').read_text()))

    def test_geojson_duplicado_area_invalida_y_crs(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'g.json';feature=dict(type='Feature',properties=dict(id=1,area_ha=.01),geometry=mapping(box(0,0,10,10)))
            f.write_text(json.dumps(dict(type='FeatureCollection',features=[feature,feature])))
            with self.assertRaises(ValueError):cargar_geometrias(f,{1:.01})
            f.write_text(json.dumps(dict(type='FeatureCollection',features=[feature])))
            with self.assertRaises(ValueError):cargar_geometrias(f,{1:1})
            with self.assertRaises(ValueError):cargar_geometrias(f,{1:.01},'georreferenciada')
            with self.assertRaises(ValueError):cargar_geometrias(f,{1:.01},'georreferenciada','EPSG:3857','EPSG:4326')
            g=cargar_geometrias(f,{1:.01},'georreferenciada','EPSG:3857','EPSG:3857')
            self.assertEqual(g[1].area,100)

    def test_pipeline_aproximado_motores_existentes_y_exportacion(self):
        cfg=replace(self.cfg,geometria='aproximada')
        a,r=ejecutar_escenario(1,0,self.d,cfg,self.C)
        b,s=ejecutar_escenario(1,0,self.d,replace(cfg,motor='cpp'),self.C)
        np.testing.assert_array_equal(r['g']['U'],s['g']['U'])
        np.testing.assert_array_equal(r['final'],s['final'])
        self.assertAlmostEqual(a['J_final'],b['J_final'])
        with tempfile.TemporaryDirectory() as t:
            t=Path(t);guardar_detalle_poligono(t,self.d,a,r,self.C,graficas=False)
            d,rep=construir_datos(ROOT,t,[1]);self.assertEqual(rep[0]['estado'],'pasa',rep)
            self.assertIsNotNone(d['poligonos']['P1']['inicial'])
            origen=np.asarray(r['geometria']['origen_m'])
            tabla=pd.DataFrame(dict(poligono=1,x_m=r['F'][:,0]+origen[0],y_m=r['F'][:,1]+origen[1],especie=[self.d.S[i] for i in r['fijas']]))
            f=t/'existentes.csv';tabla.to_csv(f,index=False)
            _,otra=ejecutar_escenario(1,0,self.d,replace(cfg,archivo_existentes=str(f)),self.C)
            np.testing.assert_allclose(otra['F'],r['F'],atol=1e-12,rtol=0)
            np.testing.assert_array_equal(otra['fijas'],r['fijas'])
            tabla.loc[0,'x_m']=-1e6;tabla.to_csv(f,index=False)
            with self.assertRaises(ValueError):ejecutar_escenario(1,0,self.d,replace(cfg,archivo_existentes=str(f)),self.C)
            # Un CSV modificado después de exportar rompe su hash incluso si conserva conteos.
            path=t/'P1/distribucion.csv';path.write_bytes(path.read_bytes()+b'\n')
            _,rep=construir_datos(ROOT,t,[1]);self.assertEqual(rep[0]['comprobaciones']['integridad_exportacion'],'falla')

    def test_economico_exportado_integrado(self):
        with tempfile.TemporaryDirectory() as t:
            ruta,eco,lote,_=ejecutar(self.d,replace(self.cfg,poligonos=(5,)),self.C,salida=t,comparar=False,graficas=False)
            d,r=construir_datos(ROOT,ruta,[5]);self.assertEqual(r[0]['estado'],'pasa',r)
            self.assertTrue(lote.cumple_presupuesto.all())
            self.assertEqual(d['poligonos']['P5']['total'],5264)
            generar_mapa(ROOT,ruta,ruta/'mapa.html',[5])


if __name__=='__main__':unittest.main(verbosity=2)
