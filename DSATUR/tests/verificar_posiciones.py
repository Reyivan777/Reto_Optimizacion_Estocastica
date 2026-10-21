"""Invariantes, deltas completos, regresión e integración de sustituciones."""
import sys
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from reforestacion.config import Config, perfil
from reforestacion.datos import Datos, cargar_competencia
from reforestacion.geometria import construir_grafo
from reforestacion.algoritmos import objetivo
from reforestacion.posiciones import preparar, evaluar, optimizar_posiciones, Rectangulo
from reforestacion.experimento import ejecutar_escenario, guardar_detalle_poligono
from reforestacion.optimizacion_economica import DatosConCuotas, planificar, validar_cuotas
from reforestacion.dos_etapas import ejecutar
from reforestacion.validacion import validar_solucion


class PruebasPosiciones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=Datos(ROOT); cls.C=cargar_competencia(ROOT/'config/competencia.json',cls.d.S)
        cls.cfg=perfil('completo',escenarios=1,optimizar_posiciones=True)

    def sencillo(self, motor='python'):
        cfg=replace(self.cfg,motor=motor)
        F=np.array([[1.,1.]])
        pool=np.array([[4.4,1.],[10.,1.],[10.,10.],[1.,2.],[30.,1.]])
        g=construir_grafo(1,F,pool[:1],cfg)
        return cfg,pool,g,np.array([0,1]),Rectangulo((20.,20.))

    def test_deltas_aristas_aparecen_desaparecen_y_radio(self):
        cfg,pool,g,y,t=self.sencillo()
        for radio in (2.,6.,12.):
            config=replace(cfg,radio=radio)
            for origen,destino in ((0,1),(1,0),(1,2),(2,1)):
                grafo=construir_grafo(1,g['U'][:1],pool[[origen]],config)
                estado=preparar(grafo,pool,t,config);estado['C']=self.C
                delta=evaluar(1,1+destino,y,estado)
                nuevo=construir_grafo(1,g['U'][:1],pool[[destino]],config)
                self.assertAlmostEqual(delta,objetivo(y,nuevo,self.C)-objetivo(y,grafo,self.C),places=12)

    def test_cada_delta_factible_contra_recalculo(self):
        cfg=replace(self.cfg,separacion_min=1.5,paso_malla=1.5,radio=3.2)
        pool=np.array([(x,y) for x in (2.,4.,6.,8.) for y in (2.,4.,6.,8.)])
        g=construir_grafo(1,np.array([[0.,0.]]),pool[[0,3,6,9]],cfg)
        y=np.array([0,1,2,3,4]);estado=preparar(g,pool,Rectangulo((10.,10.)),cfg);estado['C']=self.C
        for a in range(1,len(y)):
            for c in range(len(pool)):
                delta=evaluar(a,1+c,y,estado)
                if delta is None:continue
                U=g['U'].copy();U[a]=pool[c]
                gg=construir_grafo(1,U[:1],U[1:],cfg)
                self.assertAlmostEqual(delta,objetivo(y,gg,self.C)-objetivo(y,g,self.C),places=11)

    def test_un_movimiento_conserva_todo_y_no_muta_entradas(self):
        for motor in ('python','cpp'):
            cfg,pool,g,y,t=self.sencillo(motor)
            U=g['U'].copy(); etiquetas=y.copy();C=self.C.copy();po=pool.copy()
            nuevo,h,s=optimizar_posiciones(y,g,pool,C,t,cfg,propuestas=np.array([[1,1]]))
            self.assertEqual(s['aceptados'],1);self.assertLess(s['J_final'],s['J_inicial'])
            np.testing.assert_array_equal(nuevo['U'][0],U[0])
            np.testing.assert_array_equal(nuevo['U'][1],pool[1])
            for a,b in ((g['U'],U),(y,etiquetas),(C,self.C),(po,pool)):
                np.testing.assert_array_equal(a,b)
            np.testing.assert_array_equal(np.bincount(y),np.bincount(etiquetas))
            self.assertEqual(y[1],etiquetas[1])
            self.assertGreaterEqual(pdist(nuevo['U']).min(),cfg.separacion_min)
            self.assertTrue(t.contiene(nuevo['U']).all())

    def test_ocupada_fuera_distancia_y_empate_no_cambian_solucion(self):
        for motor in ('python','cpp'):
            cfg,pool,g,y,t=self.sencillo(motor)
            # Actual ocupada, distancia insuficiente, fuera del terreno.
            nuevo,h,s=optimizar_posiciones(y,g,pool,self.C,t,cfg,propuestas=np.array([[1,0],[1,3],[1,4]]))
            self.assertIs(nuevo,g);self.assertEqual(s['aceptados'],0);self.assertEqual(s['factibles'],0)
            # Ningún sitio del conjunto es factible: ocupado, cercano o exterior.
            cerrado=pool[[0,3,4]]
            nuevo,h,s=optimizar_posiciones(y,g,cerrado,self.C,t,replace(cfg,intentos_posiciones=30),
                                           rng=np.random.default_rng(42))
            self.assertIs(nuevo,g);self.assertEqual(s['evaluados'],30);self.assertEqual(s['factibles'],0)
            nuevo,h,s=optimizar_posiciones(y,g,pool,np.zeros((10,10)),t,cfg,propuestas=np.array([[1,1]]))
            self.assertIs(nuevo,g);self.assertEqual(s['factibles'],1);self.assertEqual(s['aceptados'],0)
            # Se rechaza incremento al volver desde una posición aislada.
            aislado=construir_grafo(1,g['U'][:1],pool[[1]],cfg)
            nuevo,h,s=optimizar_posiciones(y,aislado,pool,self.C,t,cfg,propuestas=np.array([[1,0]]))
            self.assertIs(nuevo,aislado);self.assertEqual(s['aceptados'],0)

    def test_liberacion_del_sitio_y_motor_con_propuestas_comunes(self):
        cfg,pool,g,y,t=self.sencillo()
        # Cero existentes: permite verificar que el sitio liberado se reutiliza.
        cfg=replace(cfg,separacion_min=1.,paso_malla=1.,radio=5.)
        pool=np.array([[1.,1.],[2.,1.],[3.,1.],[8.,1.]])
        g=construir_grafo(1,np.empty((0,2)),pool[:2],cfg); y=np.array([0,1])
        propuestas=np.array([[0,3],[1,0],[1,2],[0,1],[1,3]])
        a,ha,sa=optimizar_posiciones(y,g,pool,self.C,t,cfg,propuestas=propuestas)
        b,hb,sb=optimizar_posiciones(y,g,pool,self.C,t,replace(cfg,motor='cpp'),propuestas=propuestas)
        np.testing.assert_array_equal(a['U'],b['U']);np.testing.assert_allclose(ha,hb,rtol=0,atol=1e-12)
        self.assertGreaterEqual(sa['factibles'],2)
        self.assertEqual(sa['aceptados'],sb['aceptados'])

    def test_sin_nuevas_sin_candidatas_sin_intentos(self):
        for motor in ('python','cpp'):
            cfg=replace(self.cfg,motor=motor,intentos_posiciones=0)
            for F,V,pool,y in ((np.array([[1.,1.]]),np.empty((0,2)),np.empty((0,2)),np.array([0])),
                               (np.empty((0,2)),np.empty((0,2)),np.empty((0,2)),np.array([],dtype=int))):
                g=construir_grafo(1,F,V,cfg)
                nuevo,h,s=optimizar_posiciones(y,g,pool,self.C,Rectangulo((10.,10.)),cfg)
                self.assertIs(nuevo,g);self.assertEqual(s['evaluados'],0)
            cfg,pool,g,y,t=self.sencillo(motor)
            nuevo,h,s=optimizar_posiciones(y,g,pool,self.C,t,replace(cfg,intentos_posiciones=0))
            self.assertIs(nuevo,g)

    def test_interfaz_terreno_y_errores_controlados(self):
        cfg,pool,g,y,t=self.sencillo()
        class Filtro:
            def contiene(self,puntos):return t.contiene(puntos)&(puntos[:,0]<9.)
        nuevo,h,s=optimizar_posiciones(y,g,pool,self.C,Filtro(),cfg,propuestas=np.array([[1,1]]))
        self.assertIs(nuevo,g)
        for propuestas in (np.array([[0,1]]),np.array([[1,100]]),np.array([[1.,1.]]),np.array([1,1])):
            with self.assertRaises(ValueError):optimizar_posiciones(y,g,pool,self.C,t,cfg,propuestas=propuestas)
        for cambios in ({'intentos_posiciones':-1},{'intentos_posiciones':True},{'optimizar_posiciones':1}):
            with self.assertRaises(ValueError):replace(cfg,**cambios)
        with self.assertRaises(ValueError):preparar(g,np.r_[pool,pool[:1]],t,cfg)
        with self.assertRaises(ValueError):preparar(g,np.array([[np.nan,1.]]),t,cfg)

    def test_integracion_restricciones_economia_y_semillas(self):
        planes=planificar(self.d,self.cfg,(1,13,5))
        vista=DatosConCuotas(self.d,planes)
        for p in (1,13,5):
            referencia=None
            for motor in ('python','cpp'):
                cfg=replace(self.cfg,motor=motor)
                antes,r=ejecutar_escenario(p,0,vista,replace(cfg,optimizar_posiciones=False),self.C)
                despues,s=ejecutar_escenario(p,0,vista,cfg,self.C)
                for key in ('fijas','base','dsatur','final','F','V','q','R'):
                    np.testing.assert_array_equal(r[key],s[key])
                np.testing.assert_array_equal(r['g']['U'],s['g_inicial']['U'])
                self.assertLessEqual(despues['J_final'],antes['J_final'])
                self.assertEqual(antes['costo_um'],despues['costo_um'])
                self.assertEqual(antes['presupuesto_um'],despues['presupuesto_um'])
                self.assertTrue(despues['cumple_presupuesto'])
                validar_solucion(s['final'],s['g'],s['fijas'],s['n'],s['R'],s['limites'],cfg)
                validar_cuotas(planes[p]['R_original'],s['n'],np.bincount(s['final'],minlength=10),self.d.especies.costo_unitario,planes[p]['presupuesto_um'])
                # Reproducibilidad exacta y equivalencia de todas las aceptaciones.
                if referencia is not None:
                    np.testing.assert_array_equal(referencia['g']['U'],s['g']['U'])
                    np.testing.assert_allclose(referencia['historia_posiciones'],s['historia_posiciones'],rtol=0,atol=1e-12)
                _,otra=ejecutar_escenario(p,0,vista,cfg,self.C)
                np.testing.assert_array_equal(s['g']['U'],otra['g']['U'])
                referencia=s

    def test_cada_aceptacion_no_empeora_y_separacion(self):
        f,r=ejecutar_escenario(1,0,self.d,self.cfg,self.C)
        U=r['g_inicial']['U'].copy();previo=f['J_local_especies']
        for paso,a,c,delta in r['historia_posiciones']:
            U[int(a)]=r['pool'][int(c)]
            self.assertTrue(np.all(pdist(U)>=self.cfg.separacion_min-1e-8))
            nuevo=construir_grafo(1,U[:len(r['F'])],U[len(r['F']):],self.cfg)
            actual=objetivo(r['final'],nuevo,self.C)
            self.assertLess(actual,previo)
            self.assertAlmostEqual(actual-previo,delta,places=10);previo=actual
        np.testing.assert_array_equal(U,r['g']['U'])

    def test_desactivada_no_invoca_optimizador_y_regresion(self):
        with patch('reforestacion.posiciones.optimizar_posiciones',side_effect=AssertionError('No debe invocarse')):
            f,r=ejecutar_escenario(1,0,self.d,replace(self.cfg,optimizar_posiciones=False),self.C)
        self.assertAlmostEqual(f['J_final'],874.5251827583863,places=10)
        self.assertIs(r['g'],r['g_inicial'])

    def test_exportacion_usa_grafo_correspondiente_y_economia_comparada(self):
        cfg=replace(self.cfg,motor='cpp',poligonos=(5,))
        with tempfile.TemporaryDirectory() as tmp:
            ruta,eco,lote,pares=ejecutar(self.d,cfg,self.C,salida=tmp,graficas=False)
            self.assertTrue(lote.estado.eq('ok').all());self.assertTrue(pares.geometria_inicial_identica.all())
            tabla=pd.read_csv(ruta/'P5/comparacion.csv')
            self.assertEqual(len(tabla),4)
            self.assertAlmostEqual(tabla.J.iloc[-1],lote.J_final.iloc[0],places=9)
            self.assertAlmostEqual(tabla.J.iloc[-2],lote.J_local_especies.iloc[0],places=9)


if __name__=='__main__':unittest.main(verbosity=2)
