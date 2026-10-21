"""Native equivalence, invariants, edge cases and exact economic integration."""
import sys
import unittest
from pathlib import Path
from dataclasses import replace
import numpy as np
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from reforestacion import algoritmos as py, motor_cpp as cpp
from reforestacion.config import perfil, Config
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.geometria import construir_grafo, candidatas
from reforestacion.experimento import ejecutar_escenario
from reforestacion.optimizacion_economica import planificar,DatosConCuotas,validar_cuotas
from reforestacion.motores import obtener_motor

class PruebasCPP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cpp.biblioteca(); cls.d=Datos(ROOT); cls.cfg=perfil('completo',escenarios=1)
        cls.C=cargar_competencia(ROOT/'config/competencia.json',cls.d.S)

    def comparar(self,p,e,datos=None):
        datos=datos or self.d
        a,x=ejecutar_escenario(p,e,datos,self.cfg,self.C)
        b,y=ejecutar_escenario(p,e,datos,replace(self.cfg,motor='cpp'),self.C)
        for k in ('F','V','fijas','base','dsatur','final'):
            np.testing.assert_array_equal(x[k],y[k],err_msg=f'P{p} e{e} {k}')
        np.testing.assert_allclose(x['historia'],y['historia'],rtol=0,atol=1e-8)
        for k in ('J_base','J_dsatur','J_final'):
            self.assertAlmostEqual(a[k],b[k],places=8)
        for k in ('propuestas','evaluados','aceptados','rechazados','especies_iguales'):
            self.assertEqual(x['stats'][k],y['stats'][k])
        return b,y

    def test_pequeno_mediano_grande_entradas_identicas(self):
        for p in (1,13,5):
            for e in (0,1): self.comparar(p,e)

    def test_economia_30_y_compras_asignacion(self):
        planes=planificar(self.d,self.cfg,range(1,31)); vista=DatosConCuotas(self.d,planes)
        for p,plan in planes.items():
            self.assertEqual(plan['estado'],'factible_economicamente')
            a,n,R,q=self.d.poligono(p,self.cfg)
            validar_cuotas(R,n,np.array(plan['R_ajustada']),self.d.especies.costo_unitario.to_numpy(),plan['presupuesto_um'])
        # All changed quotas, including budget boundary P12/P23.
        for p in (5,9,10,12,18,23):
            f,r=self.comparar(p,0,vista)
            np.testing.assert_array_equal(np.bincount(r['final'][len(r['F']):],minlength=10),planes[p]['compras'])
            self.assertTrue(f['cumple_presupuesto'])

    def test_empates_sin_aristas_sin_fijas_y_sin_nuevas(self):
        for nf,n in ((0,0),(0,1),(0,6),(2,2),(2,5)):
            U=np.c_[np.arange(n)*10.,np.zeros(n)]
            g=construir_grafo(1,U[:nf],U[nf:],Config())
            fijas=np.zeros(nf,dtype=int); q=np.zeros(10,dtype=int);q[0]=(n-nf)//2;q[1]=n-nf-q[0]
            y=py.dsatur(fijas,q,g,self.C)
            np.testing.assert_array_equal(y,cpp.dsatur(fijas,q,g,self.C))
            a,h,s=py.busqueda_local(y,g,self.C,np.random.default_rng(7),30)
            b,hh,ss=cpp.busqueda_local(y,g,self.C,np.random.default_rng(7),30)
            np.testing.assert_array_equal(a,b); np.testing.assert_array_equal(h,hh)
            self.assertEqual(s['propuestas'],ss['propuestas'])
        F=np.empty((0,2)); lim=np.array([20.,20.]);cfg=Config()
        for cantidad in (0,1,8):
            a,b=candidatas(F,lim,cantidad,cfg);aa,bb=cpp.candidatas(F,lim,cantidad,cfg)
            np.testing.assert_array_equal(a,aa);np.testing.assert_array_equal(b,bb)

    def test_propuestas_precalculadas_y_deltas(self):
        _,r=ejecutar_escenario(1,0,self.d,self.cfg,self.C)
        g=r['g']; rng=np.random.default_rng(123)
        propuestas=cpp.propuestas_comunes(rng,g['nf'],len(g['U']),300)
        class Secuencia:
            def __init__(self): self.i=0
            def choice(self,*args,**kwargs):
                z=propuestas[self.i];self.i+=1;return z
        a,h,s=py.busqueda_local(r['dsatur'],g,self.C,Secuencia(),len(propuestas))
        b,hh,ss=cpp.busqueda_con_propuestas(r['dsatur'],g,self.C,propuestas)
        np.testing.assert_array_equal(a,b);np.testing.assert_allclose(h,hh,rtol=0,atol=1e-8)
        for a,b in propuestas[:30]:
            z=r['dsatur'].copy(); old=py.objetivo(z,g,self.C);delta=py.delta_intercambio(a,b,z,g,self.C)
            z[a],z[b]=z[b],z[a]
            self.assertAlmostEqual(py.objetivo(z,g,self.C)-old,delta,places=8)

    def test_fallos_controlados_antes_del_abi(self):
        _,r=ejecutar_escenario(1,0,self.d,self.cfg,self.C);g=r['g'];q=r['q'].copy();q[0]+=1
        with self.assertRaises(ValueError): cpp.dsatur(r['fijas'],q,g,self.C)
        with self.assertRaises(ValueError): cpp.busqueda_local(r['dsatur'],g,self.C,np.random.default_rng(),-1)
        with self.assertRaises(ValueError): cpp.busqueda_con_propuestas(r['dsatur'],g,self.C,[[0,1]])
        with self.assertRaises(ValueError): cpp.busqueda_con_propuestas(r['dsatur'],g,self.C,[[len(g['U']),len(g['U'])+1]])
        with self.assertRaises(ValueError): obtener_motor('otro')
        with self.assertRaises(ValueError): cpp.candidatas(r['F'],r['limites'],10**7,self.cfg)

if __name__=='__main__': unittest.main(verbosity=2)
