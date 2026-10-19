"""
Resultados detallados del AG para el reporte (P1, escenario 0 del notebook del matemático).

Genera, en la carpeta resultados_ag/:
  - cuotas_p1.csv                    existentes, meta final, plantas nuevas y costo por especie
  - distribucion_ag_p1_esc0.csv      cada planta: coordenadas, si es preexistente y su especie
  - metodos_p1_esc0.csv              J (FF, FV, VV) y pares vecinos por tipo de relación, por método
  - probabilidades_p1.csv            densidad por ha y probabilidad de ocurrencia por especie (P1)
  - densidad_30_poligonos.csv        densidad de plantas existentes por ha en los 30 polígonos
  - fig_grafo_especies.png           grafo de competencia entre especies
  - fig_mapa_base_vs_ag.png          distribución aleatoria vs. distribución del AG
  - fig_mapa_ag.png                  distribución final del AG (nuevas y preexistentes)
  - fig_convergencia_esc0.png        convergencia del AG frente a los demás métodos
  - fig_densidad_probabilidad.png    distribución empírica de plantas por ha y por especie
  - fig_comparacion_metodos.png      J medio por método (12 escenarios; requiere comparacion_ag_p1.csv)

Uso:  python resultados_detalle.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from ag_reforestacion import *

# ---------------- RUTAS DIRECTAS DE LOS ARCHIVOS (EDITAR SI HACE FALTA) ----------------
BASE = Path(__file__).resolve().parent
RUTA_ESPECIES = BASE / "especies.csv"
RUTA_INVENTARIO = BASE / "inventario.csv"
RUTA_COMPARACION = BASE / "resultados_ag" / "comparacion_ag_p1.csv"   # salida de correr_ag.py
OUT = BASE / "resultados_ag"
# ------------------------------------------------------------------------------------------
POLIGONO, ESCENARIO = 1, 0
OUT.mkdir(exist_ok=True)

cfg, cfg_ag = Config(), ConfigAG()
esp, inv, areas, S = cargar_datos(RUTA_ESPECIES, RUTA_INVENTARIO)
K = len(S)
C = matriz_competencia(esp)
validar_C(C)
COLORES = ['#2166ac', '#67a9cf', '#1b7837', '#a6dba0', '#b2182b',
           '#ef8a62', '#762a83', '#af8dc3', '#8c510a', '#666666']
MARCAS = ['o', 's', '^', 'D', 'v', 'P', 'X', '<', '>', 'h']
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})

# ---------------------------------------------------------------------------------------
# 1) Escenario 0 de P1 (mismas semillas que el notebook) y los cuatro métodos
# ---------------------------------------------------------------------------------------
area, n, R, q = datos_poligono(POLIGONO, esp, inv, areas, S, cfg)
lim = dimensiones(area, cfg)
rp, rb, rl = flujos(POLIGONO, ESCENARIO, cfg)
F, fijas = simular_existentes(n, lim, cfg, rp)
pool, V = candidatas(F, lim, int(q.sum()), cfg)
g = construir_grafo(POLIGONO, F, V, cfg)

y_base = base_aleatoria(fijas, q, rb)
y_dsatur = dsatur(fijas, q, g, C)
y_local, _ = busqueda_local(y_dsatur, g, C, rl, cfg.intentos_local)
rng_ag = np.random.default_rng(np.random.SeedSequence([cfg.semilla, POLIGONO, ESCENARIO, 7]))
ag = AlgoritmoGenetico(fijas, q, g, C, rng_ag, cfg_ag)
y_ag = ag.ejecutar()
metodos = {"Aleatoria": y_base, "DSATUR": y_dsatur, "DSATUR + local": y_local, "Algoritmo genético": y_ag}
for y in metodos.values():
    validar_solucion(y, g, fijas, n, R, lim, cfg)

# ---------------------------------------------------------------------------------------
# 2) Cuotas y costo
# ---------------------------------------------------------------------------------------
cuotas = esp[["especie", "genero", "costo_unitario"]].copy()
cuotas["existentes"] = n
cuotas["meta_final"] = R
cuotas["nuevas"] = q
cuotas["costo_nuevas_um"] = q * esp.costo_unitario.to_numpy()
cuotas["final_ag_verificado"] = np.bincount(y_ag, minlength=K)
cuotas.to_csv(OUT / "cuotas_p1.csv", index=False)
print(cuotas.to_string(index=False))
print("Costo total de adquisición (u.m.):", cuotas.costo_nuevas_um.sum())

# ---------------------------------------------------------------------------------------
# 3) Detalle de la solución del AG: qué especie va en cada posición
# ---------------------------------------------------------------------------------------
U = g["U"]
pd.DataFrame({"poligono": POLIGONO, "indice_local": np.arange(len(y_ag)),
              "x_simulada_m": U[:, 0], "y_simulada_m": U[:, 1],
              "preexistente": np.arange(len(y_ag)) < len(F),
              "especie": [S[s] for s in y_ag]}).to_csv(OUT / "distribucion_ag_p1_esc0.csv", index=False)

# ---------------------------------------------------------------------------------------
# 4) Comparación de métodos en el escenario 0: J y tipos de pares vecinos
# ---------------------------------------------------------------------------------------
genero = esp.genero.to_numpy()
i_, j_ = g["pares"].T


def pares_por_relacion(y):
    a, b = y[i_], y[j_]
    misma = a == b
    mismo_gen = (genero[a] == genero[b]) & ~misma
    return int(misma.sum()), int(mismo_gen.sum()), int((~misma & ~mismo_gen).sum())


filas = []
for nombre, y in metodos.items():
    d = objetivo(y, g, C, True)
    m, mg, dg = pares_por_relacion(y)
    filas.append({"metodo": nombre, **d, "pares_totales": len(i_), "pares_misma_especie": m,
                  "pares_mismo_genero_distinta_especie": mg, "pares_distinto_genero": dg})
metodos_df = pd.DataFrame(filas)
metodos_df.to_csv(OUT / "metodos_p1_esc0.csv", index=False)
print(metodos_df.round(2).to_string(index=False))

# ---------------------------------------------------------------------------------------
# 5) Probabilidades: densidad por ha y ocurrencia por especie (inventario conocido)
# ---------------------------------------------------------------------------------------
prob = pd.DataFrame({"especie": S, "existentes": n, "existentes_por_ha": n / area,
                     "P_especie_planta_existente": n / n.sum(),
                     "proporcion_meta_fuente": esp.objetivo_por_ha / esp.objetivo_por_ha.sum()})
prob.to_csv(OUT / "probabilidades_p1.csv", index=False)
print(prob.round(4).to_string(index=False))

tot = inv.groupby("poligono").agg(area_ha=("area_ha", "first"), existentes=("existentes", "sum"))
tot["existentes_por_ha"] = tot.existentes / tot.area_ha
tot.to_csv(OUT / "densidad_30_poligonos.csv")
print(tot.existentes_por_ha.describe().round(2).to_string())
por_esp = inv.groupby("especie").existentes.sum().reindex(S)
p_global = por_esp / por_esp.sum()

# ---------------------------------------------------------------------------------------
# 6) Figuras
# ---------------------------------------------------------------------------------------
# 6.1 Grafo de competencia entre especies
fig, ax = plt.subplots(figsize=(8.5, 6.5))
H = nx.Graph()
H.add_nodes_from(range(K))
for s in range(K):
    for t in range(s + 1, K):
        H.add_edge(s, t, weight=C[s, t])
pos = nx.circular_layout(H)
e2 = [(u, v) for u, v, d in H.edges(data=True) if d["weight"] == 2]
e1 = [(u, v) for u, v, d in H.edges(data=True) if d["weight"] == 1]
nx.draw_networkx_edges(H, pos, edgelist=e1, ax=ax, width=0.5, alpha=0.25, edge_color="#888888")
nx.draw_networkx_edges(H, pos, edgelist=e2, ax=ax, width=3.0, alpha=0.9, edge_color="#b2182b")
nx.draw_networkx_nodes(H, pos, ax=ax, node_color=COLORES, node_size=900, edgecolors="black", linewidths=1.5)
nx.draw_networkx_labels(H, pos, ax=ax, labels={i: str(i + 1) for i in range(K)}, font_color="white", font_weight="bold")
ax.text(1.12, 0.98, "\n".join(f"{i + 1}. {s}" for i, s in enumerate(S)), transform=ax.transAxes, va="top", fontsize=9)
ax.plot([], [], color="#b2182b", lw=3, label="C = 2: mismo género, distinta especie")
ax.plot([], [], color="#888888", lw=0.8, label="C = 1: géneros distintos")
ax.plot([], [], " ", label="C = 3 (misma especie): autocompetencia, no se dibuja")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.12), frameon=False, fontsize=9)
ax.set_title("Grafo de competencia entre especies (supuesto de prueba)")
ax.axis("off")
fig.savefig(OUT / "fig_grafo_especies.png", dpi=150, bbox_inches="tight")
plt.close(fig)


# 6.2 Mapas de la distribución
def mapa(ax, puntos, etiquetas, titulo, fijos=None):
    for s in range(K):
        m = etiquetas == s
        ax.scatter(*puntos[m].T, s=18, c=COLORES[s], marker=MARCAS[s], label=S[s], alpha=.9)
    if fijos is not None:
        ax.scatter(*puntos[fijos].T, s=55, facecolors="none", edgecolors="black", linewidths=.7,
                   label="Anillo: preexistente")
    ax.set(xlim=(0, lim[0]), ylim=(0, lim[1]), aspect="equal", xlabel="x local (m)", ylabel="y local (m)", title=titulo)


fijos_idx = np.arange(len(F))
fig, axs = plt.subplots(1, 2, figsize=(15, 7))
mapa(axs[0], U, y_base, f"Aleatoria (J = {objetivo(y_base, g, C):.1f})", fijos_idx)
mapa(axs[1], U, y_ag, f"Algoritmo genético (J = {objetivo(y_ag, g, C):.1f})", fijos_idx)
axs[1].legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
fig.suptitle("P1, escenario 0: posiciones y especies (coordenadas simuladas)")
fig.tight_layout()
fig.savefig(OUT / "fig_mapa_base_vs_ag.png", dpi=140, bbox_inches="tight")
plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 7))
mapa(ax, U, y_ag, "P1, escenario 0: distribución final del algoritmo genético", fijos_idx)
ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "fig_mapa_ag.png", dpi=140, bbox_inches="tight")
plt.close(fig)

# 6.3 Convergencia
fig, ax = plt.subplots(figsize=(8, 4.8))
ax.plot(ag.historia[:, 0], label="AG: mejor individuo", color="#2166ac")
ax.plot(ag.historia[:, 1], label="AG: media de la población", color="#2166ac", alpha=.4)
for nombre, y, c, ls in [("Aleatoria", y_base, "#888888", "--"), ("DSATUR", y_dsatur, "#67a9cf", "--"),
                         ("DSATUR + local", y_local, "#b2182b", "--")]:
    ax.axhline(objetivo(y, g, C), color=c, ls=ls, label=nombre)
ax.set(xlabel="Generación", ylabel="Competencia total J (índice)", title="Convergencia del AG, P1, escenario 0")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "fig_convergencia_esc0.png", dpi=140)
plt.close(fig)

# 6.4 Distribuciones empíricas (sin ajuste paramétrico)
fig, axs = plt.subplots(1, 2, figsize=(12, 4.5))
axs[0].hist(tot.existentes_por_ha, bins=10, color="#2166ac", edgecolor="white")
axs[0].axvline(tot.loc[POLIGONO, "existentes_por_ha"], color="#b2182b", ls="--", label=f"P{POLIGONO}")
axs[0].set(xlabel="Plantas existentes por ha", ylabel="Número de polígonos",
           title="Densidad de existentes en los 30 polígonos")
axs[0].legend()
x = np.arange(K)
axs[1].bar(x - 0.2, prob.P_especie_planta_existente, 0.4, label=f"P{POLIGONO}: existentes", color="#2166ac")
axs[1].bar(x + 0.2, prob.proporcion_meta_fuente, 0.4, label="Meta de la fuente", color="#bdbdbd")
axs[1].set_xticks(x)
axs[1].set_xticklabels([str(i + 1) for i in range(K)])
axs[1].set(xlabel="Especie (número del grafo)", ylabel="Proporción", title="Probabilidad de ocurrencia por especie")
axs[1].legend()
fig.tight_layout()
fig.savefig(OUT / "fig_densidad_probabilidad.png", dpi=140)
plt.close(fig)

# 6.5 Comparación de métodos en los 12 escenarios (si ya existe la salida de correr_ag.py)
if RUTA_COMPARACION.exists():
    mc = pd.read_csv(RUTA_COMPARACION)
    mc = mc[mc.estado.eq("ok")]
    cols = [("J_base", "Aleatoria"), ("J_dsatur", "DSATUR"), ("J_final_local", "DSATUR + local\n(6000)"),
            ("J_ag", "Algoritmo\ngenético"), ("J_local_largo", "Local\n(200 000)")]
    medias = [mc[c].mean() for c, _ in cols]
    ees = [mc[c].std() / np.sqrt(len(mc)) for c, _ in cols]
    fig, ax = plt.subplots(figsize=(8.5, 5))
    barras = ax.bar([l for _, l in cols], medias, yerr=ees, capsize=4,
                    color=["#999999", "#67a9cf", "#2166ac", "#b2182b", "#1b7837"])
    for b, v in zip(barras, medias):
        ax.text(b.get_x() + b.get_width() / 2, v + 8, f"{v:.1f}", ha="center")
    ax.set(ylim=(0, max(medias) * 1.12), ylabel="Competencia total J (media de escenarios)",
           title=f"P1: {len(mc)} escenarios, mismos sitios y cuotas")
    fig.tight_layout()
    fig.savefig(OUT / "fig_comparacion_metodos.png", dpi=140)
    plt.close(fig)
else:
    print("Aviso: no se encontró", RUTA_COMPARACION, "- se omite fig_comparacion_metodos.png (ejecute antes correr_ag.py).")
print("Listo. Archivos guardados en", OUT)
