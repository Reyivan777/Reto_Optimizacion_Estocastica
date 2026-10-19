"""Propiedades matemáticas, regresión y errores de entrada."""
from pathlib import Path
from dataclasses import replace
import json,tempfile,subprocess,sys,shutil,unittest
import numpy as np
import pandas as pd
from reforestacion.config import Config,perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.geometria import construir_grafo
from reforestacion.algoritmos import validar_C,objetivo,delta_intercambio,dsatur,busqueda_local
from reforestacion.experimento import ejecutar_escenario,ejecutar_lote,seleccionar_poligonos,agregar
ROOT=Path(__file__).resolve().parents[1]
class Modelo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=Datos(ROOT);cls.cfg=Config();cls.C=cargar_competencia(ROOT/'config/competencia.json',cls.d.S)
        cls.fila,cls.r=ejecutar_escenario(1,0,cls.d,cls.cfg,cls.C)
    def test_regresion_p1(self):
        np.testing.assert_allclose([self.fila[k] for k in ('J_base','J_dsatur','J_final')],
            [1089.006627233044,991.7477053447574,874.5251827583863],rtol=0,atol=1e-8)
        self.assertEqual((self.fila['existentes'],self.fila['nuevas'],self.fila['total']),(165,677,842))
    def test_cuotas_30(self):
        self.assertEqual(tuple(self.d.resumen(self.cfg)[['existentes','meta_final','nuevas']].sum()),(23569,120419,96850))
    def test_objetivo_independiente(self):
        g=self.r['g'];y=self.r['final']
        J=sum(a['weight']*self.C[y[i[1]],y[j[1]]] for i,j,a in g['G'].edges(data=True))
        self.assertAlmostEqual(J,objetivo(y,g,self.C),places=9)
    def test_deltas(self):
        rng=np.random.default_rng(17);M=rng.uniform(0,5,(10,10));M=(M+M.T)/2
        for C in (self.C,M,np.zeros((10,10))):
            g=self.r['g'];y=self.r['final'];J=objetivo(y,g,C)
            pares=list(g['pares'][(g['pares']>=g['nf']).all(axis=1)][:25])
            pares += [rng.choice(np.arange(g['nf'],len(y)),2,replace=False) for _ in range(100)]
            for a,b in pares:
                z=y.copy();z[a],z[b]=z[b],z[a]
                self.assertAlmostEqual(objetivo(z,g,C)-J,delta_intercambio(a,b,y,g,C),places=9)
    def test_conservacion(self):
        r=self.r;g=r['g']
        for nombre in ('base','dsatur','final'):
            y=r[nombre];np.testing.assert_array_equal(y[:g['nf']],r['fijas'])
            np.testing.assert_array_equal(np.bincount(y,minlength=10),r['R'])
        np.testing.assert_array_equal(g['U'][:len(r['F'])],r['F'])
        from scipy.spatial import cKDTree
        self.assertFalse(cKDTree(g['U']).query_pairs(self.cfg.separacion_min-1e-8))
    def test_reproducibilidad(self):
        _,r=ejecutar_escenario(1,0,self.d,self.cfg,self.C)
        for k in ('base','dsatur','final','historia'):np.testing.assert_array_equal(r[k],self.r[k])
        np.testing.assert_array_equal(r['g']['U'],self.r['g']['U'])
    def test_matriz_alternativa(self):
        rng=np.random.default_rng(19);C=rng.uniform(0,4,(10,10));C=(C+C.T)/2
        fila,r=ejecutar_escenario(1,0,self.d,self.cfg,C)
        self.assertEqual(fila['estado'],'ok');self.assertLessEqual(fila['J_final'],fila['J_dsatur']+1e-8)
        np.testing.assert_array_equal(r['g']['U'],self.r['g']['U'])
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'C.json';p.write_text(json.dumps(dict(especies=self.d.S,matriz=C.tolist())))
            np.testing.assert_array_equal(cargar_competencia(p,self.d.S),C)
    def test_matrices_invalidas(self):
        for C in (np.ones((9,9)),np.full((10,10),np.nan),np.full((10,10),np.inf),-np.ones((10,10)),np.triu(np.ones((10,10))),np.ones((10,10))+np.eye(10,k=1)*1e-14):
            with self.assertRaises(ValueError):validar_C(C)
    def test_estadisticas(self):
        st=self.r['stats'];self.assertEqual(st['propuestas'],6000)
        self.assertEqual(st['propuestas'],st['especies_iguales']+st['evaluados'])
        self.assertEqual(st['evaluados'],st['aceptados']+st['rechazados'])
        self.assertLessEqual(st['J_final'],st['J_inicial'])
        self.assertTrue((np.diff(self.r['historia'][:,1])<=1e-8).all())
        self.assertEqual(self.r['historia'][-1,0],6000)
    def test_sin_nuevas_sin_aristas(self):
        g=construir_grafo(1,np.array([[0.,0.],[10.,10.]]),np.empty((0,2)),self.cfg)
        y=np.array([0,1]);self.assertEqual(objetivo(y,g,self.C),0)
        z,h,s=busqueda_local(y,g,self.C,np.random.default_rng(2),6000)
        np.testing.assert_array_equal(z,y);self.assertEqual(s['propuestas'],0)
        np.testing.assert_array_equal(dsatur(y,np.zeros(10,dtype=int),g,self.C),y)
    def test_fallos_y_recursos(self):
        lote=ejecutar_lote(self.d,replace(self.cfg,escenarios=2,max_propuestas_posicion=1),self.C)
        self.assertEqual(lote.estado.tolist(),['fallo','fallo']);self.assertTrue(lote.detalle.str.contains('existentes').all())
        lote=ejecutar_lote(self.d,replace(self.cfg,escenarios=1,max_plantas=1,poligonos='todos'),self.C)
        self.assertEqual(len(lote),30);self.assertTrue(lote.estado.eq('omitido').all());self.assertTrue(agregar(lote).empty)
    def test_seleccion_presupuestos(self):
        self.assertEqual(seleccionar_poligonos(4),[4]);self.assertEqual(seleccionar_poligonos('todos'),list(range(1,31)))
        self.assertEqual(seleccionar_poligonos((1,4,25)),[1,4,25])
        for sel in ([],[1,1],[31],[1.2]):
            with self.assertRaises(ValueError):seleccionar_poligonos(sel)
        self.assertEqual(replace(self.cfg,presupuesto='proporcional').intentos(677),6770)
        self.assertEqual(perfil('completo').max_corridas,360)
    def test_otros_poligonos(self):
        for p in (4,25):
            f,_=ejecutar_escenario(p,0,self.d,self.cfg,self.C)
            self.assertEqual(f['estado'],'ok');self.assertLessEqual(f['J_final'],f['J_dsatur']+1e-8)
    def test_datos_invalidos(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'data').mkdir()
            for name in ('especies.csv','inventario.csv','supervivencia_porcentajes.csv'):shutil.copy(ROOT/'data'/name,root/'data'/name)
            inv=pd.read_csv(root/'data/inventario.csv')
            for invalid in (pd.concat([inv,inv.iloc[:1]]),inv.assign(existentes=-1),inv.assign(area_ha=np.inf),inv.assign(especie='desconocida')):
                invalid.to_csv(root/'data/inventario.csv',index=False)
                with self.assertRaises(ValueError):Datos(root)
        with self.assertRaises(ValueError):self.d.poligono(1,replace(self.cfg,densidad=1))
    def test_copiador_protegido(self):
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)/'copia.ipynb';dest.write_text('manual')
            proc=subprocess.run([sys.executable,str(ROOT/'scripts/crear_notebook.py'),'--destino',str(dest)],capture_output=True)
            self.assertNotEqual(proc.returncode,0);self.assertEqual(dest.read_text(),'manual')
if __name__=='__main__':unittest.main()
