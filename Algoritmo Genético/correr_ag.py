"""
Ejecuta el AG sobre los MISMOS escenarios espaciales del notebook del matemático
(P1, 12 escenarios, semillas SeedSequence([semilla, p, escenario])) y compara con
base aleatoria, DSATUR y DSATUR + búsqueda local (6000 propuestas, como en el notebook).
Referencia adicional: búsqueda local con presupuesto de evaluaciones comparable al del AG.

Uso:  python correr_ag.py [poligono] [n_escenarios]
Las rutas de los CSV se definen en RUTA_ESPECIES y RUTA_INVENTARIO (más abajo).
"""
import sys, json
from pathlib import Path
from time import perf_counter
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ag_reforestacion import *

#---------------- RUTAS DIRECTAS DE LOS ARCHIVOS (EDITAR) ----------------
RUTA_ESPECIES = Path(__file__).parent / "especies.csv"
RUTA_INVENTARIO = Path(__file__).parent / "inventario.csv"
#--------------------------------------------------------------------------
POLIGONO = int(sys.argv[1]) if len(sys.argv) > 1 else 1
cfg = Config()
if len(sys.argv) > 2:
    cfg = replace(cfg, escenarios=int(sys.argv[2]))
cfg_ag = ConfigAG()
INTENTOS_LOCAL_LARGO = 200000      # referencia de presupuesto comparable (no está en el notebook)

OUT = Path("resultados_ag"); OUT.mkdir(exist_ok=True)
esp, inv, areas, S = cargar_datos(RUTA_ESPECIES, RUTA_INVENTARIO)
C = matriz_competencia(esp); validar_C(C)
costo_unit = esp.costo_unitario.to_numpy()


def ejecutar_escenario_ag(p, e):
    t_ini = perf_counter()
    area, n, R, q = datos_poligono(p, esp, inv, areas, S, cfg)
    lim = dimensiones(area, cfg)
    rp, rb, rl = flujos(p, e, cfg)
    F, fijas = simular_existentes(n, lim, cfg, rp)
    pool, V = candidatas(F, lim, int(q.sum()), cfg)
    g = construir_grafo(p, F, V, cfg)

    base = base_aleatoria(fijas, q, rb)
    ds = dsatur(fijas, q, g, C)
    loc, _ = busqueda_local(ds, g, C, rl, cfg.intentos_local)
    t = perf_counter()
    loc_largo, _ = busqueda_local(ds, g, C, np.random.default_rng(np.random.SeedSequence([cfg.semilla, p, e, 99])),
                                  INTENTOS_LOCAL_LARGO)
    t_largo = perf_counter() - t

    # AG: flujo aleatorio propio, independiente de los tres del notebook
    rng_ag = np.random.default_rng(np.random.SeedSequence([cfg.semilla, p, e, 7]))
    ag = AlgoritmoGenetico(fijas, q, g, C, rng_ag, cfg_ag)
    t = perf_counter()
    y_ag = ag.ejecutar()
    t_ag = perf_counter() - t

    for y in [base, ds, loc, loc_largo, y_ag]:
        validar_solucion(y, g, fijas, n, R, lim, cfg)
    J = {k: objetivo(y, g, C) for k, y in
         [("base", base), ("dsatur", ds), ("local", loc), ("local_largo", loc_largo), ("ag", y_ag)]}
    ff = objetivo(y_ag, g, C, True)["FF"]
    fila = {"poligono": p, "escenario": e, "existentes": int(n.sum()), "nuevas": int(q.sum()),
            "total": int(R.sum()), "J_base": J["base"], "J_dsatur": J["dsatur"],
            "J_final_local": J["local"], "J_local_largo": J["local_largo"], "J_ag": J["ag"],
            "J_fijo": ff,
            "mejora_ag_vs_base_pct": 100 * (J["base"] - J["ag"]) / J["base"],
            "mejora_ag_vs_local_pct": 100 * (J["local"] - J["ag"]) / J["local"],
            "generaciones_ag": len(ag.historia) - 1, "evaluaciones_ag": ag.evaluaciones,
            "costo_um": float(q @ costo_unit), "seg_ag": t_ag, "seg_local_largo": t_largo,
            "seg_total": perf_counter() - t_ini}
    return fila, ag


if __name__ == "__main__":
    filas, historias = [], []
    for e in range(cfg.escenarios):
        try:
            fila, ag = ejecutar_escenario_ag(POLIGONO, e)
            fila.update(estado="ok", detalle="")
            historias.append(ag.historia[:, 0])
        except (EscenarioNoConstruido, ValueError) as err:
            fila = {"poligono": POLIGONO, "escenario": e, "estado": "fallo", "detalle": str(err)}
        filas.append(fila)
        print(f"escenario {e}: {fila.get('estado')}  J_ag={fila.get('J_ag', float('nan')):.2f}", flush=True)
    mc = pd.DataFrame(filas)
    mc.to_csv(OUT / f"comparacion_ag_p{POLIGONO}.csv", index=False)
    ok = mc[mc.estado.eq("ok")]
    print(f"\nEscenarios completados: {len(ok)}/{len(mc)}")
    cols = ["J_base", "J_dsatur", "J_final_local", "J_local_largo", "J_ag",
            "mejora_ag_vs_base_pct", "mejora_ag_vs_local_pct", "costo_um", "seg_ag"]
    est = ok[cols].agg(["count", "mean", "std", "min", "max"]).T
    est["error_estandar_media"] = est["std"] / np.sqrt(est["count"])
    est.round(4).to_csv(OUT / f"estadisticas_ag_p{POLIGONO}.csv")
    print(est.round(3).to_string())
    print("\nEscenarios en que el AG supera a DSATUR + local (6000):", int((ok.J_ag < ok.J_final_local).sum()), "/", len(ok))
    print("Escenarios en que el AG supera a la local de presupuesto comparable:", int((ok.J_ag < ok.J_local_largo).sum()), "/", len(ok))

    fig, axs = plt.subplots(1, 2, figsize=(12, 4.5))
    for h in historias:
        axs[0].plot(h, alpha=.5, lw=.9)
    axs[0].set(xlabel="Generación", ylabel="Mejor J (índice de competencia)", title="Convergencia del AG por escenario")
    x = np.arange(len(ok))
    for col, lab, m in [("J_base", "Base", "s"), ("J_dsatur", "DSATUR", "^"), ("J_final_local", "DSATUR + local", "o"),
                        ("J_ag", "AG", "D")]:
        axs[1].plot(ok.escenario, ok[col], marker=m, label=lab)
    axs[1].set(xlabel="Escenario espacial", ylabel="J total", title="Comparación pareada"); axs[1].legend()
    fig.tight_layout(); fig.savefig(OUT / f"comparacion_ag_p{POLIGONO}.png", dpi=140)
    (OUT / "configuracion_ag.json").write_text(json.dumps(
        {"config_modelo": asdict(cfg), "config_ag": asdict(cfg_ag),
         "intentos_local_largo": INTENTOS_LOCAL_LARGO, "matriz_C": C.tolist()}, indent=2), encoding="utf-8")