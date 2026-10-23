"""Estadística, planificación, fallos, agregación y reproducibilidad de fase 5."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reforestacion.monte_carlo import estadisticas,plan_muestra,filas,realizar
from reforestacion.config import perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.experimento import agregar
from reforestacion.geometria import EscenarioNoConstruido
from reforestacion.optimizacion_economica import planificar


class PruebasMonteCarlo(unittest.TestCase):
    def test_media_ic_percentiles_calculo_conocido(self):
        s=estadisticas([1,2,3,4],4)
        self.assertEqual(s['media'],2.5)
        self.assertAlmostEqual(s['desviacion'],np.sqrt(5/3))
        self.assertAlmostEqual(s['error_estandar'],np.sqrt(5/12))
        self.assertAlmostEqual(s['semiancho_ic'],3.182446305284263*np.sqrt(5/12))
        self.assertAlmostEqual(s['ic_inferior'],2.5-s['semiancho_ic'])
        self.assertEqual(s['p50'],2.5)
        self.assertAlmostEqual(s['p05'],1.15)

    def test_cero_uno_constantes_faltantes_no_se_imputan(self):
        for x,n in (([],0),([5],1),([5,np.nan,np.inf],1)):
            s=estadisticas(x,4)
            self.assertEqual(s['validos'],n)
            self.assertEqual(s['excluidos'],4-n)
            self.assertIsNone(s['error_estandar'])
            self.assertIsNone(s['ic_inferior'])
        s=estadisticas([0,0,0],3)
        self.assertEqual(s['semiancho_ic'],0)
        self.assertIsNone(s['semiancho_relativo'])

    def test_tamano_limites_precision_y_piloto(self):
        a=plan_muestra([100,101,99]*10,minimo=10,maximo=10000,relativo=.001,absoluto=.01)
        b=plan_muestra([100,101,99]*10,minimo=10,maximo=10000,relativo=.0005,absoluto=.01)
        self.assertGreater(b['n_estimado'],a['n_estimado'])
        self.assertAlmostEqual(b['n_estimado']/a['n_estimado'],4,delta=.1)
        s=plan_muestra([0,10000],minimo=10,maximo=20)
        self.assertEqual(s['n_confirmacion'],20)
        self.assertTrue(s['limitado'])
        self.assertEqual(plan_muestra([0,0],minimo=10,maximo=20)['n_confirmacion'],10)
        for kw in ({'relativo':0},{'absoluto':float('nan')},{'confianza':1},{'minimo':1},{'maximo':3,'minimo':4}):
            with self.assertRaises(ValueError): plan_muestra([1,2],**kw)
        with self.assertRaises(ValueError): plan_muestra([np.nan,1])
        with self.assertRaises(ValueError): estadisticas([1,2],1)

    def test_agregacion_exige_escenarios_pareados_completos(self):
        tabla=pd.DataFrame([dict(poligono=1,escenario=30,estado='ok',J_final=1,J_base=2),
                            dict(poligono=13,escenario=30,estado='fallo'),
                            dict(poligono=1,escenario=31,estado='ok',J_final=2,J_base=4),
                            dict(poligono=13,escenario=31,estado='ok',J_final=3,J_base=5)])
        a=agregar(tabla,[1,13])
        self.assertEqual(a.estado.tolist(),['incompleto','completo'])
        self.assertTrue(np.isnan(a.J_final.iloc[0]))
        self.assertEqual(a.J_final.iloc[1],5)
        with self.assertRaises(ValueError): agregar(pd.concat([tabla,tabla.iloc[:1]]),[1,13])

    def tarea(self,e=0,motor='cpp'):
        cfg=perfil('completo',motor=motor,escenarios=2,optimizar_posiciones=True,vecindad_posiciones='mixta')
        d=Datos(ROOT); C=cargar_competencia(ROOT/'config/competencia.json',d.S)
        plan=planificar(d,cfg,[1])
        return (1,e,d,cfg,C,plan[1])

    def test_fallos_construccion_sin_reemplazo_y_error_tecnico_visible(self):
        tarea=self.tarea()
        with patch('reforestacion.experimento.ejecutar_escenario',side_effect=EscenarioNoConstruido('capacidad')):
            f=realizar(tarea)
        self.assertEqual(f['estado'],'no_construido')
        self.assertEqual(f['escenario'],0)
        self.assertNotIn('J_final',f)
        with patch('reforestacion.experimento.ejecutar_escenario',side_effect=AssertionError('invariante')):
            with self.assertRaises(AssertionError): realizar(tarea)

    def test_serial_paralelo_ambos_motores_semillas_y_cuotas(self):
        tareas=[self.tarea(e) for e in (0,1)]
        serial=list(filas(iter(tareas)))
        paralelo=list(filas(iter(tareas),workers=2))
        python=[realizar((*x[:3],replace(x[3],motor='python'),*x[4:])) for x in tareas]
        for a,b,c in zip(serial,paralelo,python):
            for clave in ('escenario','estado','entradas_sha256','solucion_sha256','J_final','costo_um'):
                self.assertEqual(a[clave],b[clave])
                self.assertEqual(a[clave],c[clave])
            self.assertTrue(a['cumple_presupuesto'])
        self.assertNotEqual(serial[0]['entradas_sha256'],serial[1]['entradas_sha256'])
        with self.assertRaises(ValueError): list(filas([],0))


if __name__=='__main__': unittest.main(verbosity=2)
