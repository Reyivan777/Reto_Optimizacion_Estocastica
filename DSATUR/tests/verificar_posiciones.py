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
from reforestacion.posiciones import preparar, evaluar, aplicar, optimizar_posiciones, Rectangulo
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

    def test_intercambio_sin_sitios_libres_conserva_identidades_y_entradas(self):
        for motor in ('python','cpp'):
            cfg=replace(self.cfg,motor=motor,vecindad_posiciones='mixta')
            F=np.array([[1.,1.]])
            pool=np.array([[4.4,1.],[10.,1.]])
            g=construir_grafo(1,F,pool,cfg); y=np.array([0,0,4])
            U=g['U'].copy(); etiquetas=y.copy()
            nuevo,h,s=optimizar_posiciones(y,g,pool,self.C,Rectangulo((20.,20.)),cfg,
                                           propuestas=np.array([[1,1],[1,1],[2,0]]))
            np.testing.assert_array_equal(nuevo['U'],U[[0,2,1]])
            np.testing.assert_array_equal(y,etiquetas)
            np.testing.assert_array_equal(g['U'],U)
            np.testing.assert_array_equal(pool,U[1:])
            self.assertEqual(s['aceptados_intercambio'],1)
            self.assertEqual(s['aceptados_sustitucion'],0)
            self.assertEqual(s['factibles_intercambio'],1)  # después: destinos propios
            self.assertEqual(s['J_final'],objetivo(y,nuevo,self.C))
            self.assertLess(s['J_final'],s['J_inicial'])
            # La referencia histórica sigue rechazando el sitio ocupado.
            viejo,_,ss=optimizar_posiciones(y,g,pool,self.C,Rectangulo((20.,20.)),
                replace(cfg,vecindad_posiciones='sustituciones'),propuestas=np.array([[1,1]]))
            self.assertIs(viejo,g);self.assertEqual(ss['aceptados'],0)

    def test_deltas_intercambio_exhaustivos_matriz_simetrica_general(self):
        rng=np.random.default_rng(59); C=rng.uniform(0,4,(10,10));C=(C+C.T)/2
        pool=np.array([(x,y) for x in (2.,4.,6.) for y in (2.,4.,6.)])
        etiquetas=np.arange(10)
        for radio in (1.,3.,20.):
            cfg=replace(self.cfg,separacion_min=1.,radio=radio,vecindad_posiciones='mixta')
            g=construir_grafo(1,np.array([[0.,0.]]),pool,cfg)
            estado=preparar(g,pool,Rectangulo((8.,8.)),cfg);estado['C']=C
            for a in range(1,len(etiquetas)):
                for b in range(1,len(etiquetas)):
                    if a==b:continue
                    delta=evaluar(a,b,etiquetas,estado,intercambios=True)
                    U=g['U'].copy();U[[a,b]]=U[[b,a]]
                    gg=construir_grafo(1,U[:1],U[1:],cfg)
                    self.assertAlmostEqual(delta,objetivo(etiquetas,gg,C)-objetivo(etiquetas,g,C),places=11)
            # Nunca admite el sitio de una existente ni un destino propio.
            self.assertIsNone(evaluar(1,0,etiquetas,estado,intercambios=True))
            self.assertIsNone(evaluar(1,1,etiquetas,estado,intercambios=True))

    def test_mixta_cada_paso_y_ocupacion_dinamica(self):
        from scipy.spatial import cKDTree
        cfg=replace(self.cfg,vecindad_posiciones='mixta')
        f,r=ejecutar_escenario(1,0,self.d,cfg,self.C)
        estado=preparar(r['g_inicial'],r['pool'],Rectangulo(tuple(r['limites'])),cfg)
        estado['C']=self.C
        previo=f['J_local_especies'];tipos={'sustitucion':0,'intercambio':0}
        for paso,a,c,delta in r['historia_posiciones']:
            a,c=int(a),int(c);destino=estado['nf']+c
            tipo='intercambio' if estado['ocupantes'][destino]>=0 else 'sustitucion'
            tipos[tipo]+=1
            self.assertAlmostEqual(evaluar(a,destino,r['final'],estado,True),delta,places=12)
            aplicar(a,destino,estado)
            U=estado['xy'][estado['sitios']]
            self.assertEqual(len(np.unique(U,axis=0)),len(U))
            self.assertFalse(cKDTree(U).query_pairs(cfg.separacion_min-1e-8))
            np.testing.assert_array_equal(U[:estado['nf']],r['F'])
            gg=construir_grafo(1,U[:estado['nf']],U[estado['nf']:],cfg)
            actual=objetivo(r['final'],gg,self.C)
            self.assertLess(actual,previo);self.assertAlmostEqual(actual-previo,delta,places=10)
            previo=actual
        np.testing.assert_array_equal(estado['xy'][estado['sitios']],r['g']['U'])
        for tipo in tipos:
            self.assertGreater(tipos[tipo],0)
            self.assertEqual(tipos[tipo],r['stats_posiciones']['aceptados_'+tipo])

    def test_mixta_integracion_economia_semillas_motores_y_exportacion(self):
        cfg=replace(self.cfg,vecindad_posiciones='mixta',poligonos=(5,))
        planes=planificar(self.d,cfg,(1,13,5));vista=DatosConCuotas(self.d,planes)
        for p in (1,13,5):
            antes,ref=ejecutar_escenario(p,0,vista,replace(cfg,optimizar_posiciones=False),self.C)
            fila,a=ejecutar_escenario(p,0,vista,cfg,self.C)
            _,b=ejecutar_escenario(p,0,vista,replace(cfg,motor='cpp'),self.C)
            _,otra=ejecutar_escenario(p,0,vista,cfg,self.C)
            for key in ('F','V','fijas','q','R','base','dsatur','final'):
                np.testing.assert_array_equal(ref[key],a[key])
            for r in (a,b,otra):
                np.testing.assert_array_equal(a['g']['U'],r['g']['U'])
                np.testing.assert_allclose(a['historia_posiciones'],r['historia_posiciones'],rtol=0,atol=1e-12)
                validar_solucion(r['final'],r['g'],r['fijas'],r['n'],r['R'],r['limites'],cfg)
                validar_cuotas(planes[p]['R_original'],r['n'],np.bincount(r['final'],minlength=10),
                               self.d.especies.costo_unitario,planes[p]['presupuesto_um'])
            self.assertLessEqual(fila['J_final'],antes['J_final'])
            self.assertEqual(fila['costo_um'],antes['costo_um'])
            self.assertEqual(fila['presupuesto_um'],antes['presupuesto_um'])
            s=a['stats_posiciones']
            self.assertEqual(s['aceptados'],s['aceptados_sustitucion']+s['aceptados_intercambio'])
            self.assertEqual(s['factibles'],s['factibles_sustitucion']+s['factibles_intercambio'])
        with tempfile.TemporaryDirectory() as tmp:
            ruta,_,lote,pares=ejecutar(self.d,cfg,self.C,salida=tmp,graficas=False)
            self.assertTrue(lote.estado.eq('ok').all());self.assertTrue(pares.geometria_inicial_identica.all())
            tabla=pd.read_csv(ruta/'P5/comparacion.csv')
            self.assertAlmostEqual(tabla.J.iloc[-1],lote.J_final.iloc[0],places=9)
            xy=pd.read_csv(ruta/'P5/distribucion.csv')[['x_m','y_m']].to_numpy()
            np.testing.assert_allclose(xy,a['g']['U'],rtol=0,atol=1e-12)

    def test_mixta_empates_incrementos_vacios_y_filtro_terreno(self):
        for motor in ('python','cpp'):
            cfg=replace(self.cfg,motor=motor,vecindad_posiciones='mixta')
            F=np.array([[1.,1.]])
            pool=np.array([[4.4,1.],[10.,1.],[1.,2.],[30.,1.]])
            g=construir_grafo(1,F,pool[:2],cfg);y=np.array([0,4,0])
            # Invertir el intercambio mejorante empeora; propio, cercano y exterior.
            propuestas=np.array([[1,1],[1,0],[1,2],[1,3]])
            nuevo,h,s=optimizar_posiciones(y,g,pool,self.C,Rectangulo((20.,20.)),cfg,propuestas=propuestas)
            self.assertIs(nuevo,g);self.assertEqual(s['aceptados'],0)
            # Matriz nula: solo empates aunque haya intercambios factibles.
            nuevo,h,s=optimizar_posiciones(y,g,pool,np.zeros((10,10)),Rectangulo((20.,20.)),cfg,propuestas=propuestas)
            self.assertIs(nuevo,g);self.assertGreater(s['factibles_intercambio'],0)
            vacio=construir_grafo(1,np.empty((0,2)),np.empty((0,2)),cfg)
            nuevo,h,s=optimizar_posiciones(np.array([],dtype=int),vacio,np.empty((0,2)),self.C,
                                           Rectangulo((20.,20.)),cfg)
            self.assertIs(nuevo,vacio);self.assertEqual(s['evaluados'],0)
        with self.assertRaises(ValueError):replace(self.cfg,vecindad_posiciones='otra')


if __name__=='__main__':unittest.main(verbosity=2)
