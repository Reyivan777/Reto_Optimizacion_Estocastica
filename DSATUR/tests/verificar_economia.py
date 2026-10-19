"""Pruebas económicas y de integración (sin lanzar 360 escenarios)."""
import itertools
import tempfile
import unittest
import sys
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dataclasses import replace
import numpy as np
from scipy.optimize import OptimizeResult
from reforestacion.config import perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.economia import diagnostico_flexibilidad
from reforestacion.optimizacion_economica import (optimizar_cuotas,planificar,
    validar_cuotas,DatosConCuotas,desviacion_exacta)
from reforestacion.experimento import ejecutar_escenario
from reforestacion.dos_etapas import ejecutar

class PruebasEconomicas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=Datos(ROOT);cls.cfg=perfil('completo',escenarios=1,poligonos=(5,))
        cls.C=cargar_competencia(ROOT/'config/competencia.json',cls.d.S)
        cls.planes=planificar(cls.d,cls.cfg,range(1,31))

    def test_30_economicos_y_diagnostico(self):
        diag=diagnostico_flexibilidad(self.d,self.cfg).set_index('poligono')
        for p,plan in self.planes.items():
            _,n,R,_=self.d.poligono(p,self.cfg)
            self.assertEqual(plan['estado'],'factible_economicamente')
            self.assertTrue(plan['certificado_desviacion'])
            self.assertTrue(plan['certificado_desempate'])
            validar_cuotas(R,n,plan['R_ajustada'],self.d.especies.costo_unitario,plan['presupuesto_um'])
            self.assertAlmostEqual(plan['costo_minimo_um'],diag.loc[p,'costo_minimo_banda_10_um'])
            if p not in (5,9,10,12,18,23):self.assertEqual(plan['R_ajustada'],R.tolist())

    def test_enumeracion_lexicografica(self):
        R=np.array([10,20,0]);n=np.array([0,2,0]);c=np.array([3.,1.,9.]);B=46
        opciones=[]
        for x in itertools.product(range(9,12),range(18,23),[0]):
            if sum(x)==30 and c@(np.array(x)-n)<=B:
                opciones.append((desviacion_exacta(x,R),float(c@(np.array(x)-n))))
        s=optimizar_cuotas(R,n,c,B)
        self.assertEqual((desviacion_exacta(s['R_ajustada'],R),s['costo_ajustado_um']),min(opciones))

    def test_inviables_ceros_y_bordes(self):
        s=optimizar_cuotas([10,10],[0,0],[3,1],35)
        self.assertEqual(s['estado'],'inviable_economicamente');self.assertEqual(s['costo_minimo_um'],38)
        s=optimizar_cuotas([0,10],[1,0],[1,1],100)
        self.assertEqual(s['estado'],'inviable_economicamente')
        s=optimizar_cuotas([0,10],[0,10],[1,1],0)
        self.assertEqual(s['compras'],[0,0])
        s=optimizar_cuotas([0,0],[0,0],[1,2],0)
        self.assertEqual(s['R_ajustada'],[0,0])
        with self.assertRaises(ValueError): validar_cuotas(np.array([10]),np.array([0]),[10],[.1],.999999)
        with self.assertRaises(ValueError): optimizar_cuotas([1.5],[0],[1],1)

    def test_limite_solver_no_es_inviabilidad(self):
        with patch('reforestacion.optimizacion_economica.milp',return_value=OptimizeResult(status=1,x=None,message='límite')):
            s=optimizar_cuotas([10],[0],[1],10)
        self.assertEqual(s['estado'],'omitido_limite_computacional')
        self.assertFalse(s['certificado_desviacion'])

    def test_integracion_cuotas_compras_fijas_geometria(self):
        fijo,df=ejecutar_escenario(5,0,self.d,self.cfg,self.C)
        vista=DatosConCuotas(self.d,self.planes)
        eco,de=ejecutar_escenario(5,0,vista,self.cfg,self.C)
        np.testing.assert_array_equal(df['g']['U'],de['g']['U'])
        np.testing.assert_array_equal(df['fijas'],de['fijas'])
        np.testing.assert_array_equal(np.bincount(de['final'],minlength=10)-de['n'],self.planes[5]['compras'])
        self.assertLessEqual(eco['J_final'],eco['J_dsatur'])
        self.assertTrue(eco['cumple_presupuesto']);self.assertFalse(fijo['cumple_presupuesto'])

    def test_estados_y_salidas_sin_sobrescribir(self):
        with tempfile.TemporaryDirectory() as t:
            cfg=replace(self.cfg,max_plantas=1)
            r,_,l,_=ejecutar(self.d,cfg,self.C,salida=t,graficas=False)
            self.assertEqual(l.estado_factibilidad.iloc[0],'omitido_limite_computacional')
            r2,_,_,_=ejecutar(self.d,cfg,self.C,salida=t,etapa='economica',graficas=False)
            self.assertNotEqual(r,r2);self.assertTrue((r/'cuotas.csv').is_file())
            cfg=replace(self.cfg,max_propuestas_posicion=1)
            _,_,l,_=ejecutar(self.d,cfg,self.C,salida=t,graficas=False,comparar=False)
            self.assertEqual(l.estado_factibilidad.iloc[0],'economica_factible_espacial_no_construida')
            cfg=replace(self.cfg,presupuesto_por_ha=1.)
            _,_,l,_=ejecutar(self.d,cfg,self.C,salida=t,graficas=False)
            self.assertEqual(l.estado_factibilidad.iloc[0],'inviable_economicamente')
            with patch('reforestacion.dos_etapas.ejecutar_escenario',side_effect=RuntimeError('controlado')):
                _,_,l,_=ejecutar(self.d,self.cfg,self.C,salida=t,graficas=False)
            self.assertEqual(l.estado_factibilidad.iloc[0],'error_ejecucion')

if __name__=='__main__': unittest.main(verbosity=2)
