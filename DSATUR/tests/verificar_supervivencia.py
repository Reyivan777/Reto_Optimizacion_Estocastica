"""Fase 6: contratos, esperanzas, mortalidad, reposición, dinero y semillas."""
from dataclasses import replace
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))
from reforestacion.datos import Datos
from reforestacion.supervivencia import Hipotesis, auditar_historico, proyectar, simular
from explorar_supervivencia import cargar_hipotesis


class PruebasSupervivencia(unittest.TestCase):
    def setUp(self):
        self.h = Hipotesis('prueba', 'Probabilidades hipotéticas para verificar fórmulas.')

    def test_auditoria_real_y_alineacion_por_especie(self):
        d = Datos(ROOT)
        a = auditar_historico(d.supervivencia.iloc[::-1], d.S)
        self.assertEqual(a['filas'], 10)
        self.assertEqual(a['minimo_pct'], 72.63)
        self.assertEqual(a['especies_con_aumento'], 0)
        self.assertFalse(a['denominadores_disponibles'])
        self.assertFalse(a['calibracion_estadistica'])

    def test_auditoria_rechaza_faltantes_duplicados_rangos_y_esquema(self):
        d = Datos(ROOT); t = d.supervivencia
        malas = [t.iloc[:-1], pd.concat([t.iloc[:-1], t.iloc[:1]]),
                 t.assign(especie=['x']+t.especie.tolist()[1:]), t.drop(columns='2022')]
        for valor in (np.nan, np.inf, -1, 101, 'texto'):
            x = t.astype(object).copy(); x.loc[0, '2023'] = valor; malas.append(x)
        for x in malas:
            with self.assertRaises(ValueError): auditar_historico(x, d.S)
        # No se descarta un aumento: puede indicar distinta cohorte/denominador.
        x = t.copy(); x.loc[0, '2023'] = 99
        self.assertEqual(auditar_historico(x, d.S)['especies_con_aumento'], 1)

    def test_esperanza_conocida_y_conservacion_por_especie(self):
        h = replace(self.h, supervivencia_existentes=.5, fraccion_reposicion=.5)
        t, a = proyectar([2], [4], [.75], [10], 100, h)
        self.assertEqual(a['vivos_iniciales_esperados'], 4)
        self.assertEqual(a['muertes_esperadas'], 2)
        self.assertEqual(a['reposiciones_esperadas'], 1)
        self.assertEqual(a['vivos_finales_esperados'], 4.75)
        self.assertEqual(a['costo_total_esperado_um'], 50)
        self.assertEqual(a['deficit_esperado'], 1.25)
        self.assertEqual(t.meta.iloc[0], 6)

    def test_extremos_mortalidad_total_y_reposicion_no_iterativa(self):
        h = replace(self.h, supervivencia_existentes=0, fraccion_reposicion=1)
        a = simular([2], [4], [0], [10], 50, h, 1, 0)
        self.assertEqual(a['muertes'], 6)
        self.assertEqual(a['reposiciones'], 6)
        self.assertEqual(a['compras_totales'], 10)
        self.assertEqual(a['vivos_finales'], 0)
        self.assertEqual(a['exceso_um'], 50)
        self.assertFalse(a['cumple_presupuesto'])
        b = simular([2], [4], [1], [10], 50, self.h, 1, 0)
        self.assertEqual(b['vivos_finales'], 6)
        self.assertEqual(b['muertes'], 0)

    def test_stocks_vacios_y_cero_presupuesto(self):
        a = simular([0,0], [0,0], [.2,.8], [0,10], 0, self.h, 1, 0)
        self.assertEqual(a['costo_total_um'], 0)
        self.assertEqual(a['vivos_finales'], 0)
        self.assertTrue(a['cumple_presupuesto'])
        t, b = proyectar([0], [0], [.5], [1], 0, self.h)
        self.assertEqual(b['deficit_esperado'], 0)

    def test_validacion_hipotesis_y_probabilidades_sin_recorte(self):
        for campo, valor in [('nombre',''), ('justificacion',''), ('fraccion_reposicion',1.1),
            ('supervivencia_existentes',-1), ('factor_precio_inicial',np.inf),
            ('factor_presupuesto',True), ('factor_supervivencia_nuevas',np.nan)]:
            with self.assertRaises(ValueError): replace(self.h, **{campo:valor})
        for cambio in ({'factor_supervivencia_nuevas':2}, {'factor_supervivencia_reposicion':2}):
            with self.assertRaises(ValueError): proyectar([1],[1],[.8],[1],10,replace(self.h,**cambio))

    def test_vectores_conteos_presupuestos_e_indices_invalidos(self):
        casos = [([],[],[],[],1), ([1],[1,2],[.5],[1],1),
                 ([.5],[1],[.5],[1],1), ([1],[1],[-.5],[1],1),
                 ([1],[1],[.5],[-1],1), ([1],[np.nan],[.5],[1],1),
                 ([1],[1],[.5],[1],-1), ([1],[1],[.5],[1],np.inf)]
        for args in casos:
            with self.assertRaises(ValueError): proyectar(*args,self.h)
        for indices in ((1,-1,2),(True,0,2),(1,0,-1)):
            with self.assertRaises(ValueError): simular([1],[1],[.5],[1],10,self.h,*indices)

    def test_comparacion_monetaria_decimal_sin_tolerancia(self):
        a = simular([0],[3],[1],[.1],.3,self.h,1,0)
        self.assertTrue(a['cumple_presupuesto'])
        b = simular([0],[3],[1],[.1],.2999999999,self.h,1,0)
        self.assertFalse(b['cumple_presupuesto'])
        self.assertGreater(b['exceso_um'], 0)

    def test_semillas_orden_no_mutacion_y_estres_solo_economico(self):
        n,q,p,c = map(np.array, ([3,5],[100,200],[.2,.8],[2,3]))
        antes = [x.copy() for x in (n,q,p,c)]
        a = simular(n,q,p,c,1000,self.h,13,7)
        simular(n,q,p,c,1000,self.h,1,10)
        self.assertEqual(a, simular(n,q,p,c,1000,self.h,13,7))
        b = simular(n,q,p,c,1000,replace(self.h,factor_precio_inicial=2,factor_presupuesto=.5),13,7)
        self.assertEqual(a['vivos_finales'], b['vivos_finales'])
        self.assertEqual(a['muertes'], b['muertes'])
        self.assertEqual(b['costo_inicial_um'], 2*a['costo_inicial_um'])
        for x,y in zip((n,q,p,c),antes): np.testing.assert_array_equal(x,y)
        valores = [simular(n,q,p,c,1000,self.h,13,i)['vivos_finales'] for i in range(10)]
        self.assertGreater(len(set(valores)),1)

    def test_media_y_varianza_con_reposicion_contra_distribucion_analitica(self):
        # Cada sitio nuevo acaba vivo con p + (1-p)*rho*pr = .625.
        h = replace(self.h, fraccion_reposicion=.5)
        valores = [simular([0],[40],[.5],[2],1000,h,1,i)['vivos_finales'] for i in range(4000)]
        self.assertLess(abs(np.mean(valores)-25), 6*np.sqrt(40*.625*.375/4000))
        self.assertAlmostEqual(np.var(valores),40*.625*.375,delta=.8)
        for i in range(50):
            a = simular([4],[40],[.5],[2],1000,h,1,i)
            self.assertEqual(a['vivos_finales']+a['deficit'],44)
            self.assertLessEqual(a['reposiciones'],a['muertes'])
            self.assertLessEqual(a['vivos_reposicion'],a['reposiciones'])

    def test_configuracion_explicita_y_nombres_unicos(self):
        path = ROOT/'config/escenarios_supervivencia.json'
        raw, hs = cargar_hipotesis(path)
        self.assertEqual(len(hs),6)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'h.json'
            raw['hipotesis'].append(raw['hipotesis'][0])
            p.write_text(json.dumps(raw),encoding='utf-8')
            with self.assertRaises(ValueError): cargar_hipotesis(p)

    def test_cli_modos_exportacion_y_suma_por_indice(self):
        for modo in ('fijo','economico'):
            r = subprocess.run([sys.executable, str(ROOT/'scripts/explorar_supervivencia.py'),
                '--poligonos','1,5','--escenarios','3','--modo',modo],cwd=ROOT,
                text=True,capture_output=True,check=True)
            out = Path(r.stdout.strip().splitlines()[-1])
            t = pd.read_csv(out/'simulaciones.csv')
            a = pd.read_csv(out/'agregado_subconjunto.csv')
            self.assertEqual(len(t),36)
            np.testing.assert_array_equal(a.vivos_finales,
                t.groupby(['hipotesis','escenario'],sort=False).vivos_finales.sum())
            self.assertFalse(t.duplicated(['hipotesis','poligono','escenario']).any())
            self.assertTrue((out/'manifiesto.json').is_file())


if __name__ == '__main__': unittest.main(verbosity=2)
