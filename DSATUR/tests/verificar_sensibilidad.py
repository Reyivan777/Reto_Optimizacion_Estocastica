"""Fase 7: validación, métricas comunes, emparejamiento e invariantes."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reforestacion.algoritmos import objetivo
from reforestacion.config import perfil
from reforestacion.datos import Datos, cargar_competencia
from reforestacion.experimento import ejecutar_escenario, LimiteRecursos
from reforestacion.geometria import EscenarioNoConstruido
from reforestacion.optimizacion_economica import planificar, DatosConCuotas
from reforestacion.sensibilidad import matriz_taxonomica, cargar_hipotesis, comparar


class PruebasSensibilidad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=Datos(ROOT)
        cls.C=cargar_competencia(ROOT/'config/competencia.json',cls.d.S)
        cls.m,cls.raw=cargar_hipotesis(ROOT/'config/sensibilidad_competencia.json',cls.d.S,cls.C)
        cls.cfg=perfil('completo',escenarios=1,poligonos=(1,),intentos_local=150,
                       intentos_posiciones=150)
        cls.planes=planificar(cls.d,cls.cfg,[1])
        cls.vista=DatosConCuotas(cls.d,cls.planes)

    def cargar(self,raw):
        with tempfile.TemporaryDirectory() as carpeta:
            p=Path(carpeta)/'c.json';p.write_text(json.dumps(raw),encoding='utf-8')
            return cargar_hipotesis(p,self.d.S,self.C)

    def test_reconstruye_original_y_no_muta(self):
        np.testing.assert_array_equal(matriz_taxonomica(self.d.S,1,1,1),self.C)
        original=self.C.copy()
        self.m['original'][0,0]=9
        np.testing.assert_array_equal(self.C,original)
        self.m['original'][0,0]=3

    def test_pesos_y_catalogo_invalidos(self):
        for w in (-1,float('inf'),float('nan'),True,'1'):
            with self.assertRaises(ValueError):matriz_taxonomica(self.d.S,1,w,1)
        with self.assertRaises(ValueError):matriz_taxonomica(['x','x'],1,1,1)

    def test_config_orden_version_nombres_metadatos(self):
        for cambiar in (
            lambda r:r.update(especies=list(reversed(r['especies']))),
            lambda r:r.update(version=2),
            lambda r:r.update(hipotesis=[]),
            lambda r:r['hipotesis'][0].update(nombre='original'),
            lambda r:r['hipotesis'][0].update(nombre='../otro'),
            lambda r:r['hipotesis'][0].update(naturaleza='medicion'),
            lambda r:r['hipotesis'].append(r['hipotesis'][0]),
            lambda r:r['hipotesis'][0]['pesos'].update(agua=1)):
            r=json.loads(json.dumps(self.raw));cambiar(r)
            with self.assertRaises(ValueError):self.cargar(r)

    def test_matriz_explicita_general_y_ceros(self):
        rng=np.random.default_rng(7);a=rng.uniform(size=(10,10));C=a+a.T
        for a in (C,np.zeros((10,10))):
            r=json.loads(json.dumps(self.raw))
            h=r['hipotesis'][0];h.pop('pesos');h['matriz']=a.tolist()
            m,_=self.cargar(r);np.testing.assert_array_equal(m[h['nombre']],a)

    def test_matriz_invalida_y_especificacion_ambigua(self):
        for a in ([[1]],np.full((10,10),-1).tolist(),np.full((10,10),float('nan')).tolist(),np.triu(np.ones((10,10))).tolist()):
            r=json.loads(json.dumps(self.raw));h=r['hipotesis'][0];h.pop('pesos');h['matriz']=a
            with self.assertRaises(ValueError):self.cargar(r)
        r=json.loads(json.dumps(self.raw));r['hipotesis'][0]['matriz']=self.C.tolist()
        with self.assertRaises(ValueError):self.cargar(r)

    def test_evaluacion_cruzada_contra_suma_independiente(self):
        matrices={'original':self.C,'alternativa':self.m['contraste_moderado']}
        filas,cruces=comparar(1,0,self.vista,self.cfg,matrices,self.planes[1])
        self.assertEqual(len({f['entradas_sha256'] for f in filas}),1)
        detalles={k:ejecutar_escenario(1,0,self.vista,self.cfg,C)[1] for k,C in matrices.items()}
        def suma(r,C):
            return sum(w*C[r['final'][i],r['final'][j]] for (i,j),w in zip(r['g']['pares'],r['g']['pesos']))
        for f in cruces:
            C=matrices[f['matriz_evaluadora']]
            j=suma(detalles[f['matriz_solucion']],C);ref=suma(detalles['original'],C)
            self.assertAlmostEqual(f['J'],j,places=9)
            self.assertAlmostEqual(f['diferencia_vs_original'],j-ref,places=9)
        self.assertTrue(all(f['cumple_presupuesto'] for f in filas))
        for f in filas:
            C=matrices[f['matriz']]
            self.assertAlmostEqual(f['J_final'],sum(f[f'peso_{i}_{j}']*C[i,j]
                for i in range(10) for j in range(i,10)),places=9)

    def test_escala_no_es_mejora_y_denominador_cero(self):
        # Misma C nula: objetivo 0, diferencia 0, porcentaje indefinido.
        filas,c=comparar(1,0,self.d,self.cfg,{'original':np.zeros((10,10)),'otra':np.zeros((10,10))})
        self.assertTrue(all(f['diferencia_pct'] is None and f['diferencia_vs_original']==0 for f in c))
        self.assertEqual(filas[0]['solucion_sha256'],filas[1]['solucion_sha256'])
        _,r=ejecutar_escenario(1,0,self.d,self.cfg,self.C)
        self.assertAlmostEqual(objetivo(r['final'],r['g'],2*self.C),2*objetivo(r['final'],r['g'],self.C))
        # Alternativa principal afín: no cambia el orden de soluciones en grafo fijo.
        masa=r['g']['pesos'].sum()
        for y in (r['base'],r['dsatur'],r['final']):
            self.assertAlmostEqual(objetivo(y,r['g'],self.m['contraste_moderado']),
                .5*objetivo(y,r['g'],self.C)+.5*masa,places=9)

    def test_motores_equivalentes_y_posiciones(self):
        matrices={'original':self.C,'alternativa':self.m['contraste_moderado']}
        for posiciones in (False,True):
            cfg=replace(self.cfg,optimizar_posiciones=posiciones,vecindad_posiciones='mixta')
            py,c=comparar(1,1,self.vista,cfg,matrices,self.planes[1])
            cpp,d=comparar(1,1,self.vista,replace(cfg,motor='cpp'),matrices,self.planes[1])
            for a,b in zip(py,cpp):
                for k in ('entradas_sha256','solucion_sha256','total','costo_um'):
                    self.assertEqual(a[k],b[k])
            np.testing.assert_allclose([f['J'] for f in c],[f['J'] for f in d],atol=1e-8,rtol=0)

    def test_fallos_sin_imputar_y_errores_propagan(self):
        m={'original':self.C,'alternativa':self.C.copy()}
        for error in (EscenarioNoConstruido('geometría'),LimiteRecursos('límite')):
            with patch('reforestacion.sensibilidad.ejecutar_escenario',side_effect=error):
                f,c=comparar(1,0,self.d,self.cfg,m)
                self.assertEqual(len(f),2);self.assertEqual(c,[])
                estado='omitido' if isinstance(error,LimiteRecursos) else 'no_construido'
                self.assertTrue(all(x['estado']==estado and 'J_final' not in x for x in f))
        with patch('reforestacion.sensibilidad.ejecutar_escenario',side_effect=RuntimeError('técnico')):
            with self.assertRaises(RuntimeError):comparar(1,0,self.d,self.cfg,m)
        with self.assertRaises(ValueError):comparar(1,0,self.d,self.cfg,{'otra':self.C})

    def test_referencia_ausente_sin_diferencias_inventadas(self):
        salida=ejecutar_escenario(1,0,self.d,self.cfg,self.C)
        with patch('reforestacion.sensibilidad.ejecutar_escenario',side_effect=[EscenarioNoConstruido('x'),salida]):
            f,c=comparar(1,0,self.d,self.cfg,{'original':self.C,'otra':self.C})
            self.assertEqual(f[0]['estado'],'no_construido')
            self.assertTrue(all(x['J_referencia'] is None and x['diferencia_vs_original'] is None for x in c))

    def test_cli_rechaza_lote_excesivo_y_parametros(self):
        for argumentos in (['--max-corridas','1'],['--motores','cpp,cpp'],['--escenarios','0']):
            r=subprocess.run([sys.executable,str(ROOT/'scripts/analizar_sensibilidad.py'),*argumentos],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)

    def test_cli_exportaciones_fijo_y_economico(self):
        import pandas as pd
        for modo in ('fijo','economico'):
            r=subprocess.run([sys.executable,str(ROOT/'scripts/analizar_sensibilidad.py'),
                '--modo',modo,'--poligonos','1','--escenarios','1','--motores','cpp',
                '--optimizar-posiciones'],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(r.returncode,0,r.stderr)
            out=Path(r.stdout.strip().splitlines()[-1])
            t=pd.read_csv(out/'escenarios.csv');res=pd.read_csv(out/'resumen_pareado.csv')
            self.assertEqual(len(t),7);self.assertTrue(t.estado.eq('ok').all())
            self.assertEqual(len(res),49);self.assertTrue(res.validos.eq(1).all())
            self.assertTrue(res.error_estandar.isna().all())
            self.assertTrue(res.ic_inferior.isna().all())
            self.assertEqual(t.entradas_sha256.nunique(),1)
            m=json.loads((out/'manifiesto.json').read_text(encoding='utf-8'))
            self.assertTrue(m['config']['optimizar_posiciones'])
            self.assertEqual(m['argumentos']['modo'],modo)


if __name__=='__main__':unittest.main(verbosity=2)
