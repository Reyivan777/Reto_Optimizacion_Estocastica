"""Cuatro figuras principales y cinco diagnósticos opcionales."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

COLORES = ['#2166ac','#67a9cf','#1b7837','#a6dba0','#b2182b',
           '#ef8a62','#762a83','#af8dc3','#8c510a','#666666']
MARCAS = ['o','s','^','D','v','P','X','<','>','h']


def mapa(puntos, etiquetas, especies, limites, titulo, nf=0):
    fig,ax = plt.subplots(figsize=(10,6),layout='constrained')
    for s,nombre in enumerate(especies):
        mascara = etiquetas == s
        ax.scatter(*puntos[mascara].T,s=19,c=COLORES[s],marker=MARCAS[s],label=nombre)
    if nf:
        ax.scatter(*puntos[:nf].T,s=55,facecolors='none',edgecolors='black',linewidths=.6,label='Anillo: existente')
    ax.set(xlim=(0,limites[0]),ylim=(0,limites[1]),aspect='equal',xlabel='x local (m)',ylabel='y local (m)',title=titulo)
    ax.legend(bbox_to_anchor=(1.02,1),loc='upper left',fontsize=9)
    return fig


def comparacion(tabla, titulo):
    fig,ax = plt.subplots(figsize=(8,5),layout='constrained')
    tabla = tabla.loc[tabla.metodo.isin(['Aleatoria','DSATUR + local'])].copy()
    tabla['metodo'] = tabla.metodo.replace({'DSATUR + local':'DSATUR + búsqueda local'})
    ax.bar(tabla.metodo,tabla.J,color=['#999999','#2166ac'])
    for i,v in enumerate(tabla.J):
        ax.text(i,v,f'{v:.3f}',ha='center',va='bottom')
    ax.set(ylim=(0,tabla.J.max()*1.13),ylabel='Competencia J (índice adimensional)',title=titulo)
    return fig


def monte_carlo(tabla, titulo):
    ok = tabla.loc[tabla.estado.eq('ok')]
    fig,axs = plt.subplots(1,2,figsize=(12,5),layout='constrained')
    for col,label,color,marker in [('J_base','Aleatoria','#888888','s'),('J_final','DSATUR + búsqueda local','#2166ac','o')]:
        if not ok.empty:
            axs[0].plot(ok.escenario,ok[col],marker=marker,color=color,label=label)
    axs[0].set(xlabel='Escenario espacial completo',ylabel='Competencia J (índice)',title=titulo)
    if not ok.empty:
        axs[0].legend()
        axs[1].hist(ok.mejora_pct,bins=min(6,len(ok)),color='#2166ac',edgecolor='white')
    else:
        axs[0].text(.5,.5,'Ningún escenario completado',ha='center',transform=axs[0].transAxes)
    axs[1].set(xlabel='Reducción frente a aleatoria (%)',ylabel='Número de escenarios',title=f'{len(ok)}/{len(tabla)} completados; estadísticas condicionales')
    return fig


def diagnosticos(detalle, C, especies):
    """Generador: una figura cada vez; nunca crea matrices de distancia densas."""
    g,limites = detalle['g'],detalle['limites']
    fig,ax = plt.subplots();ax.add_patch(plt.Rectangle((0,0),*limites,fill=False))
    ax.set(xlim=(0,limites[0]),ylim=(0,limites[1]),aspect='equal',xlabel='x (m)',ylabel='y (m)',title='Rectángulo de área equivalente')
    yield 'geometria',fig
    fig,ax = plt.subplots();ax.scatter(*detalle['V'].T,s=5,label='Seleccionadas');ax.scatter(*detalle['F'].T,s=8,label='Existentes')
    ax.set(xlabel='x (m)',ylabel='y (m)',aspect='equal',title='Selección geométrica previa a especies');ax.legend()
    yield 'posiciones',fig
    fig,ax = plt.subplots();e=g['pares'][::max(1,len(g['pares'])//450)]
    ax.add_collection(LineCollection(g['U'][e],linewidths=.5));ax.scatter(*g['U'].T,s=3)
    ax.set(xlim=(0,limites[0]),ylim=(0,limites[1]),aspect='equal',xlabel='x (m)',ylabel='y (m)',title='Muestra de aristas de interacción')
    yield 'grafo',fig
    fig,ax = plt.subplots(figsize=(10,8),layout='constrained');im=ax.imshow(C)
    ax.set_xticks(range(len(especies)),especies,rotation=90);ax.set_yticks(range(len(especies)),especies)
    ax.set_title('C provisional: coeficientes adimensionales');fig.colorbar(im,ax=ax,label='Penalización')
    yield 'matriz',fig
    fig,ax = plt.subplots();h=detalle['historia'];ax.step(h[:,0],h[:,1],where='post')
    ax.set(xlabel='Propuestas de intercambio (incluye descartadas)',ylabel='Competencia J (índice)',title='Descensos: mejoras aceptadas; mesetas: sin mejora')
    yield 'busqueda_local',fig

