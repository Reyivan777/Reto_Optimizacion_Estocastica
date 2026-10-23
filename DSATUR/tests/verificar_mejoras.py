"""Fase 8: deltas independientes, restricciones, reinicios y CLI."""
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import json
import subprocess
import sys
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from reforestacion.algoritmos import objetivo
from reforestacion.config import perfil
from reforestacion.datos import Datos, cargar_competencia
from reforestacion.experimento import ejecutar_escenario
from reforestacion.mejoras import Mejoras, dsatur_estable, delta_cambio, conjunta, mejorar
from reforestacion.optimizacion_economica import planificar, DatosConCuotas, desviacion_exacta, validar_cuotas


class PruebasMejoras(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Datos(ROOT)
        cls.C = cargar_competencia(ROOT/'config/competencia.json', cls.d.S)
        cls.cfg = perfil('completo', escenarios=1, intentos_local=100, intentos_posiciones=100)
        cls.plan = planificar(cls.d, cls.cfg, [1])[1]
        cls.f, cls.det = ejecutar_escenario(1, 0, DatosConCuotas(cls.d, {1:cls.plan}), cls.cfg, cls.C)

    def test_parametros_invalidos(self):
        for kw in ({'reinicios':True}, {'reinicios':-1}, {'intentos_local':1.5},
                   {'intentos_conjuntos':-1}, {'margen_desviacion':'NaN'},
                   {'margen_desviacion':'-0.01'}, {'margen_desviacion':.1}, {'tolerancia':0}):
            with self.assertRaises(ValueError): Mejoras(**kw)

    def test_deltas_recalculados_matriz_general(self):
        rng = np.random.default_rng(17)
        a = rng.uniform(size=(10,10)); C = a+a.T
        g = self.det['g']; y = self.det['final']
        j = objetivo(y, g, C)
        for i in range(g['nf'], min(g['nf']+8, len(y))):
            for s in range(10):
                z = y.copy(); z[i] = s
                self.assertAlmostEqual(delta_cambio(i,s,y,g,C), objetivo(z,g,C)-j, places=9)

    def test_dsatur_cuotas_fijas_reproducible(self):
        d = self.det
        a = dsatur_estable(d['fijas'],d['q'],d['g'],self.C,np.random.default_rng(8))
        b = dsatur_estable(d['fijas'],d['q'],d['g'],self.C,np.random.default_rng(8))
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(a[:len(d['fijas'])],d['fijas'])
        np.testing.assert_array_equal(np.bincount(a,minlength=10),d['R'])
        with self.assertRaises(ValueError):dsatur_estable(d['fijas'],d['q']+1,d['g'],self.C,np.random.default_rng(8))

    def test_casi_empates_resueltos_por_cuota(self):
        # El vértice nuevo tiene costos 1 y 1+4e-16; cuota restante favorece especie 1.
        g = {'U':np.zeros((4,2)), 'nf':1, 'ady':[[(1,1.)],[(0,1.)],[],[]]}
        C = np.ones((10,10)); C[0,1]=C[1,0]=1+4e-16
        q = np.zeros(10,dtype=int); q[:2]=[1,2]
        y = dsatur_estable(np.array([0]),q,g,C,np.random.default_rng(0))
        self.assertEqual(y[1],1)

    def test_cero_opciones_identico_a_referencia(self):
        f,d = mejorar(1,0,self.d,self.cfg,self.C,self.plan,Mejoras(0,0,0))
        np.testing.assert_array_equal(d['final'],self.det['final'])
        self.assertEqual(f['J_final'],f['J_referencia'])

    def test_reinicios_no_empeoran_y_semillas(self):
        op = Mejoras(2,100,100,'0.02')
        f,d = mejorar(1,0,self.d,self.cfg,self.C,self.plan,op)
        h,z = mejorar(1,0,self.d,self.cfg,self.C,self.plan,op)
        np.testing.assert_array_equal(d['final'],z['final'])
        self.assertLessEqual(f['J_final'],f['J_referencia'])
        js = [r['J_incumbente'] for r in d['traza']]
        self.assertTrue(all(a>=b for a,b in zip(js,js[1:])))
        self.assertLessEqual(f['desviacion_final'],f['desviacion_referencia']+.02+1e-14)

    def test_equivalencia_motores_posiciones(self):
        for on in (False,True):
            cfg = replace(self.cfg,optimizar_posiciones=on,vecindad_posiciones='mixta')
            f,d = mejorar(1,0,self.d,cfg,self.C,self.plan,Mejoras(1,100,100,'0.02'))
            h,z = mejorar(1,0,self.d,replace(cfg,motor='cpp'),self.C,self.plan,Mejoras(1,100,100,'0.02'))
            np.testing.assert_array_equal(d['final'],z['final'])
            np.testing.assert_array_equal(d['g']['U'],z['g']['U'])
            self.assertAlmostEqual(f['J_final'],h['J_final'])

    def sintetico(self):
        R=np.full(10,20);y=np.repeat(np.arange(10),R)
        g={'U':np.zeros((200,2)), 'nf':0, 'pares':np.array([[0,1]]),
           'pesos':np.array([1.]), 'ady':[[] for _ in y]}
        g['ady'][0]=[(1,1.)];g['ady'][1]=[(0,1.)]
        C=np.ones((10,10));C[0,0]=3
        return R,y,g,C

    def test_conjunta_acepta_mejora_y_preserva_bandas(self):
        R,y,g,C=self.sintetico();n=np.zeros(10,dtype=int);costos=np.ones(10)
        z,st=conjunta(y,g,C,R,n,costos,200,Fraction(1,10),np.random.default_rng(4),5000)
        self.assertGreater(st['aceptados'],0)
        self.assertLess(objetivo(z,g,C),objetivo(y,g,C))
        x=np.bincount(z,minlength=10)
        validar_cuotas(R,n,x,costos,200)
        self.assertLessEqual(desviacion_exacta(x,R),Fraction(1,10))

    def test_conjunta_rechaza_desviacion_y_presupuesto(self):
        R,y,g,C=self.sintetico();n=np.zeros(10,dtype=int)
        for costos,B,limite in ((np.ones(10),200,Fraction(0)),(np.r_[1,np.full(9,2)],380,Fraction(1))):
            z,st=conjunta(y,g,C,R,n,costos,B,limite,np.random.default_rng(4),5000)
            np.testing.assert_array_equal(y,z)
            self.assertEqual(st['aceptados'],0)

    def test_sin_nuevas_y_sin_aristas(self):
        R,y,g,C=self.sintetico();g['nf']=len(y)
        z,st=conjunta(y,g,C,R,R,np.ones(10),0,Fraction(0),np.random.default_rng(1),100)
        self.assertEqual(st['propuestas'],0)
        np.testing.assert_array_equal(y,z)
        g['nf']=0;g['pares']=np.empty((0,2),dtype=int);g['pesos']=np.array([]);g['ady']=[[] for _ in y]
        z,st=conjunta(y,g,C,R,np.zeros(10,dtype=int),np.ones(10),200,Fraction(1),np.random.default_rng(1),100)
        self.assertEqual(st['aceptados'],0)

    def test_error_tecnico_se_propaga(self):
        with patch('reforestacion.mejoras.ejecutar_escenario',side_effect=RuntimeError('técnico')):
            with self.assertRaises(RuntimeError):mejorar(1,0,self.d,self.cfg,self.C,self.plan)

    def test_cli_limite_y_exportaciones(self):
        script = str(ROOT/'scripts/optimizar_fase8.py')
        r=subprocess.run([sys.executable,script,'--max-corridas','1'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
        r=subprocess.run([sys.executable,script,'--poligonos','1','--escenarios','1','--motor','cpp',
            '--reinicios','1','--intentos-local','100','--intentos-conjuntos','100','--margen-desviacion','0.02'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(r.returncode,0,r.stderr)
        out=Path(r.stdout.strip().splitlines()[-1])
        m=json.loads((out/'manifiesto.json').read_text(encoding='utf-8'))
        self.assertEqual(m['validos'],1)
        self.assertTrue((out/'INFORME.md').is_file())
        z=np.load(out/'P1_E0.npz');x=np.bincount(z['final'],minlength=10)
        np.testing.assert_array_equal(x,z['x'])


if __name__=='__main__': unittest.main(verbosity=2)
