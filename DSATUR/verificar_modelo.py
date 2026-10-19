"""Comprobaciones opcionales rápidas; no requieren ejecutar los 360 escenarios."""
import sys,tempfile,unittest
from pathlib import Path
from dataclasses import replace
import numpy as np,pandas as pd
from scipy.optimize import linprog
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from reforestacion.config import Config,perfil
from reforestacion.datos import Datos,cargar_competencia
from reforestacion.economia import presupuesto_poligono,presupuestos,diagnostico_flexibilidad
from reforestacion.algoritmos import objetivo,delta_intercambio
from reforestacion.experimento import ejecutar_escenario,ejecutar_lote,agregar,guardar_monte_carlo_por_poligono
from reforestacion.reportes import guardar_modelo_completo,estadisticas_globales
from reforestacion import visualizacion as vis
class Pruebas(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.d=Datos(ROOT);cls.cfg=perfil('completo',escenarios=1);cls.C=cargar_competencia(ROOT/'config/competencia.json',cls.d.S)
  cls.f,cls.r=ejecutar_escenario(1,0,cls.d,cls.cfg,cls.C)
 def test_regresion_historica(self):
  old=dict(J_base=1089.006627233044,J_dsatur=991.7477053447574,J_final=874.5251827583863,costo_um=15903.5)
  for k in ('J_base','J_dsatur','J_final','costo_um'):self.assertAlmostEqual(self.f[k],old[k],places=8)
 def test_presupuesto_individual_no_agregado(self):
  b=presupuestos(self.d,self.cfg)
  self.assertEqual(b.loc[~b.cumple_presupuesto,'poligono'].tolist(),[5,9,10,12,18,23])
  self.assertEqual(b.costo_um.sum(),2279608.);self.assertAlmostEqual(b.presupuesto_um.sum(),2287625.)
  self.assertFalse(b.cumple_presupuesto.all());self.assertGreater(b.saldo_um.sum(),0)
  for row in b.itertuples():
   a,n,R,q=self.d.poligono(row.poligono,self.cfg)
   self.assertAlmostEqual(row.presupuesto_um,12500*a);self.assertAlmostEqual(row.costo_um,q@self.d.especies.costo_unitario.to_numpy())
   self.assertAlmostEqual(row.presupuesto_utilizado_pct,100*row.costo_um/row.presupuesto_um)
 def test_flexibilidad_solo_diagnostico_y_minimo(self):
  antes=[self.d.poligono(p,self.cfg)[2].copy() for p in range(1,31)]
  diag=diagnostico_flexibilidad(self.d,self.cfg)
  self.assertFalse(diag.aplicado_al_modelo.any())
  c=self.d.especies.costo_unitario.to_numpy()
  for p,R in enumerate(antes,1):
   a,n,rr,q=self.d.poligono(p,self.cfg);np.testing.assert_array_equal(rr,R)
   lo=np.maximum(n,(90*R+99)//100);hi=110*R//100
   sol=linprog(c,A_eq=np.ones((1,10)),b_eq=[R.sum()],bounds=list(zip(lo,hi)),method='highs')
   self.assertTrue(sol.success)
   self.assertAlmostEqual(sol.fun-c@n,diag.loc[diag.poligono.eq(p),'costo_minimo_banda_10_um'].iloc[0],places=7)
 def test_restricciones_deltas_reproducibilidad(self):
  from reforestacion.validacion import validar_solucion
  r=self.r;g=r['g']
  for key in ('base','dsatur','final'):validar_solucion(r[key],g,r['fijas'],r['n'],r['R'],r['limites'],self.cfg)
  self.assertLessEqual(self.f['J_final'],self.f['J_dsatur'])
  _,otra=ejecutar_escenario(1,0,self.d,self.cfg,self.C)
  for key in ('base','dsatur','final','historia'):np.testing.assert_array_equal(r[key],otra[key])
  np.testing.assert_array_equal(g['U'][:len(r['F'])],r['F'])
  rng=np.random.default_rng(5)
  for _ in range(100):
   a,b=rng.choice(np.arange(g['nf'],len(g['U'])),2,replace=False)
   z=r['final'].copy();z[a],z[b]=z[b],z[a]
   self.assertAlmostEqual(objetivo(z,g,self.C)-objetivo(r['final'],g,self.C),delta_intercambio(a,b,r['final'],g,self.C),places=8)
 def test_no_agregar_faltantes_fallos_omitidos(self):
  for caso in ('faltante','fallo','omitido'):
   df=pd.DataFrame([dict(self.f,poligono=i) for i in range(1,31)])
   if caso=='faltante':df=df.iloc[:-1]
   else:df.loc[29,'estado']=caso
   a=agregar(df,escenarios_esperados=2)
   self.assertEqual(a.estado.tolist(),['incompleto','incompleto']);self.assertTrue(a.J_final.isna().all())
   self.assertEqual(estadisticas_globales(a).numero_escenarios_completos.tolist(),[0]*4)
  # Una fila fallida sin economía induce dtype object: no invertir bool de Python.
  df=pd.DataFrame([dict(self.f,poligono=i) for i in range(1,31)]+[dict(poligono=1,escenario=1,estado='fallo',detalle='controlado')])
  g=agregar(df,escenarios_esperados=2)
  self.assertEqual(g.poligonos_fuera_presupuesto.iloc[0],0)
  with self.assertRaises(ValueError):agregar(pd.DataFrame([self.f,self.f]),[1])
 def test_porcentaje_global_ratio_sumas(self):
  df=pd.DataFrame([dict(self.f,poligono=i,J_base=100+i,J_dsatur=95+i,J_final=90+i) for i in range(1,31)])
  a=agregar(df);self.assertEqual(a.estado.iloc[0],'completo')
  self.assertAlmostEqual(a.mejora_pct.iloc[0],100*(df.J_base.sum()-df.J_final.sum())/df.J_base.sum())
 def test_graficas_dos_metodos(self):
  import matplotlib.pyplot as plt
  tabla=pd.DataFrame(dict(metodo=['Aleatoria','DSATUR','DSATUR + local'],J=[10,9,8]))
  fig=vis.comparacion(tabla,'prueba');self.assertEqual(len(fig.axes[0].patches),2);plt.close(fig)
  fig=vis.monte_carlo(pd.DataFrame([self.f]),'prueba');self.assertEqual(len(fig.axes[0].lines),2);plt.close(fig)
 def test_fallo_exportacion_real_sin_obsoletos(self):
  cfg=replace(self.cfg,poligonos=(1,),max_propuestas_posicion=1)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'P1';p.mkdir();(p/'distribucion.csv').write_text('obsoleto')
   lote=ejecutar_lote(self.d,cfg,self.C,salida_detalles=t,graficas=False)
   self.assertEqual(lote.estado.tolist(),['fallo']);self.assertFalse((p/'distribucion.csv').exists())
   guardar_monte_carlo_por_poligono(t,lote)
   self.assertTrue((p/'estadisticas_mc.csv').is_file())
 def test_modelo_completo_rechaza_subconjuntos(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):guardar_modelo_completo(t,self.d,self.cfg,self.C,pd.DataFrame([self.f]))
   cfg=replace(self.cfg,poligonos='todos',max_plantas=1)
   fallos=ejecutar_lote(self.d,cfg,self.C)
   g,_=guardar_modelo_completo(t,self.d,cfg,self.C,fallos)
   self.assertTrue(g.estado.eq('incompleto').all());self.assertTrue(g.J_final.isna().all())
   stats=pd.read_csv(Path(t)/'modelo_completo/estadisticas_monte_carlo.csv')
   self.assertTrue(stats.numero_escenarios_completos.eq(0).all())
   self.assertEqual(len(list((Path(t)/'modelo_completo/graficas').glob('*.png'))),5)
if __name__=='__main__':unittest.main(verbosity=2)
