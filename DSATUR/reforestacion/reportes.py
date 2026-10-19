"""Resultados integrales: sin unir coordenadas locales ni sumar escenarios."""
from dataclasses import asdict
from pathlib import Path
import hashlib, json, platform, importlib.metadata
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from .economia import presupuestos, diagnostico_flexibilidad
from .experimento import agregar, seleccionar_poligonos


def estadisticas_globales(globales):
    ok = globales.loc[globales.estado.eq('completo')]
    columnas = ['J_base','J_dsatur','J_final','mejora_pct']
    filas = []
    for col in columnas:
        valores = ok[col]
        filas.append(dict(metrica=col, numero_escenarios_completos=len(ok),
            escenarios_solicitados=len(globales), escenarios_excluidos=len(globales)-len(ok),
            media=valores.mean(), desviacion_estandar=valores.std(ddof=1),
            minimo=valores.min(), maximo=valores.max()))
    return pd.DataFrame(filas)


def resultados_por_poligono(lote, presupuesto, config):
    filas=[]
    for p in seleccionar_poligonos(config.poligonos):
        tabla=lote.loc[lote.poligono.eq(p)];ok=tabla.loc[tabla.estado.eq('ok')]
        fila=dict(poligono=p, escenarios_solicitados=config.escenarios,
            escenarios_completados=len(ok), escenarios_fallidos=int(tabla.estado.eq('fallo').sum()),
            escenarios_omitidos=int(tabla.estado.eq('omitido').sum()),
            escenarios_sin_registro=config.escenarios-len(tabla),
            estado_ejecucion='completo' if len(ok)==config.escenarios else 'incompleto',
            interpretacion='medias entre escenarios completados; cantidades y costos fijos')
        for col in ('J_base','J_dsatur','J_final','mejora_pct'):
            fila[col+'_media']=ok[col].mean() if col in ok else np.nan
        fila['mejora_sobre_J_medio_pct'] = 100*(1-fila['J_final_media']/fila['J_base_media']) if fila['J_base_media']>0 else np.nan
        filas.append(fila)
    return presupuesto.merge(pd.DataFrame(filas),on='poligono',how='left',validate='one_to_one')


def guardar_configuracion(ruta, datos, config, C, lote):
    versiones={x:importlib.metadata.version(x) for x in ('numpy','pandas','scipy','networkx','matplotlib','nbformat','nbclient')}
    fuentes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (datos.root/'data').glob('*') if f.is_file()}
    contenido=dict(config=asdict(config), matriz_C=C.tolist(), orden_especies=datos.S,
        semillas=dict(base=config.semilla,esquema='SeedSequence([semilla, poligono, escenario]).spawn(3)',
            flujos=['posiciones y etiquetas fijas simuladas','asignacion aleatoria','busqueda local']),
        python=platform.python_version(), versiones=versiones, datos_sha256=fuentes,
        estados=lote.estado.value_counts().to_dict(),
        modelo='cuotas fijas; presupuesto validado individualmente, no reparado',
        tolerancia_delta=1e-10, estadisticas='std muestral ddof=1; no intervalos de confianza')
    Path(ruta).write_text(json.dumps(contenido,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def figuras_globales(globales, por_poligono, presupuesto):
    """Cinco figuras; solo escenarios completos en comparaciones globales."""
    ok=globales.loc[globales.estado.eq('completo')]
    fig,ax=plt.subplots(figsize=(9,5),layout='constrained')
    if len(ok):
        valores=[ok.J_base.mean(),ok.J_final.mean()]
        ax.bar(['Aleatoria','DSATUR + búsqueda local'],valores,color=['#888888','#2166ac'])
        for i,v in enumerate(valores):ax.text(i,v,f'{v:,.1f}',ha='center',va='bottom')
        ax.set_ylim(0,max(valores)*1.14)
    else:ax.text(.5,.5,'No hay escenarios globales completos',ha='center',transform=ax.transAxes)
    ax.set(ylabel='Media de J agregado (índice adimensional)',title=f'Modelo completo: {len(ok)}/{len(globales)} escenarios completos de 30 polígonos')
    yield '01_comparacion_global.png',fig

    fig,ax=plt.subplots(figsize=(10,11),layout='constrained')
    etiquetas=[f'P{int(p)} (n={int(n)})' for p,n in zip(por_poligono.poligono,por_poligono.escenarios_completados)]
    ax.barh(etiquetas,por_poligono.mejora_pct_media,color='#2166ac');ax.invert_yaxis()
    ax.set(xlabel='Media de reducción de J frente a aleatoria (%)',ylabel='Polígono y escenarios completados',title='Procedimiento DSATUR + búsqueda local por polígono')
    yield '02_mejora_por_poligono.png',fig

    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    for col,label,color,marcador in [('J_base','Aleatoria','#888888','s'),('J_final','DSATUR + búsqueda local','#2166ac','o')]:
        # NaN en incompletos evita unir artificialmente escenarios faltantes.
        ax.plot(globales.escenario,globales[col],marker=marcador,color=color,label=label)
    ax.set(xlabel='Escenario conjunto de 30 polígonos',ylabel='J agregado (índice adimensional)',title=f'Monte Carlo global: {len(ok)} escenarios completos; {len(globales)-len(ok)} excluidos')
    ax.legend()
    yield '03_monte_carlo_global.png',fig

    fig,ax=plt.subplots(figsize=(11,12),layout='constrained');y=np.arange(len(presupuesto))
    ax.barh(y-.18,presupuesto.presupuesto_um,height=.35,color='#bbbbbb',label='Presupuesto disponible')
    barras=ax.barh(y+.18,presupuesto.costo_um,height=.35,color='#2166ac',label='Adquisición: cuotas fijas')
    for b,cumple in zip(barras,presupuesto.cumple_presupuesto):
        if not cumple:b.set_color('#b45f06');b.set_hatch('//')
    from matplotlib.patches import Patch
    handles,labels=ax.get_legend_handles_labels();handles.append(Patch(facecolor='#b45f06',hatch='//'));labels.append('Adquisición supera presupuesto')
    ax.legend(handles,labels,loc='lower right')
    ax.set_yticks(y,[f'P{int(p)}' for p in presupuesto.poligono]);ax.invert_yaxis()
    ax.set(xlabel='Unidades monetarias (u.m.)',ylabel='Polígono',title=f'Presupuesto por polígono: {int((~presupuesto.cumple_presupuesto).sum())} incumplimientos individuales')
    yield '04_presupuesto_por_poligono.png',fig

    fig,ax=plt.subplots(figsize=(9,5),layout='constrained')
    if len(ok):ax.hist(ok.mejora_pct,bins=min(6,len(ok)),color='#2166ac',edgecolor='white')
    else:ax.text(.5,.5,'Sin datos completos',ha='center',transform=ax.transAxes)
    ax.set(xlabel='Reducción de J agregado frente a aleatoria (%)',ylabel='Número de escenarios completos',title=f'Distribución de mejoras globales; n={len(ok)} (no supervivencia)')
    yield '05_distribucion_mejoras.png',fig


def guardar_modelo_completo(raiz, datos, config, C, lote):
    if set(seleccionar_poligonos(config.poligonos)) != set(range(1,31)):
        raise ValueError('modelo_completo exige selección de los 30 polígonos.')
    carpeta=Path(raiz)/'modelo_completo';carpeta.mkdir(parents=True,exist_ok=True)
    globales=agregar(lote,list(range(1,31)),config.escenarios)
    presupuesto=presupuestos(datos,config)
    por_poligono=resultados_por_poligono(lote,presupuesto,config)
    globales.to_csv(carpeta/'resumen_global.csv',index=False)
    por_poligono.to_csv(carpeta/'resultados_por_poligono.csv',index=False)
    presupuesto.to_csv(carpeta/'presupuesto_por_poligono.csv',index=False)
    estadisticas_globales(globales).to_csv(carpeta/'estadisticas_monte_carlo.csv',index=False)
    diagnostico_flexibilidad(datos,config).to_csv(carpeta/'diagnostico_flexibilidad_10.csv',index=False)
    # Los registros de cada escenario permanecen en P1–P30/monte_carlo.csv.
    # No duplicar esa misma tabla concatenada en la carpeta global.
    (carpeta/'escenarios_por_poligono.csv').unlink(missing_ok=True)
    datos.resumen(config).to_csv(carpeta/'cuotas_30.csv',index=False)
    guardar_configuracion(carpeta/'configuracion.json',datos,config,C,lote)
    # Regenerar este registro: una nueva corrida no hereda pruebas de otra.
    validacion = dict(origen='validaciones integradas de ejecutar_escenario',
        escenarios_solicitados=len(seleccionar_poligonos(config.poligonos))*config.escenarios,
        escenarios_ok=int(lote.estado.eq('ok').sum()),
        escenarios_globales_completos=int(globales.estado.eq('completo').sum()),
        restricciones='cuotas, fijas, geometria y J_final <= J_dsatur verificadas para estado ok',
        presupuesto_cumplen=int(presupuesto.cumple_presupuesto.sum()),
        pruebas_rapidas='no ejecutadas por el exportador',
        regresion_historica='no comparada automaticamente por el exportador')
    (carpeta/'validacion.json').write_text(json.dumps(validacion,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    graficas=carpeta/'graficas';graficas.mkdir(exist_ok=True)
    for nombre,fig in figuras_globales(globales,por_poligono,presupuesto):
        try:fig.savefig(graficas/nombre,dpi=140,bbox_inches='tight')
        finally:plt.close(fig)
    # Sustituir únicamente los cuatro resúmenes antiguos conocidos de la raíz.
    # Su versión previa sigue disponible en el historial Git.
    for nombre in ('resumen_30_poligonos.csv','resumen_global.csv','cuotas_30.csv','configuracion.json'):
        (Path(raiz)/nombre).unlink(missing_ok=True)
    return globales,por_poligono
