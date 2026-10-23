'use strict';
const D=JSON.parse(document.getElementById('datos-mapa').textContent);
const $=id=>document.getElementById(id), C=['#2166ac','#67a9cf','#1b7837','#a6dba0','#b2182b','#ef8a62','#762a83','#af8dc3','#8c510a','#666666'];
const ids=Object.keys(D.poligonos), canvas=$('mapa'), ctx=canvas.getContext('2d');
let paneles=[], zoom=1, pan=[0,0], pendiente=false, arrastre=null;
const fmt=n=>n.toLocaleString('es-MX',{maximumFractionDigits:3});
ids.forEach(id=>$('poligono').add(new Option(id,id)));
D.especies.forEach((s,i)=>$('especie').add(new Option(s,String(i))));
$('leyenda').innerHTML=D.especies.map((s,i)=>`<span><i class="color" style="background:${C[i]}"></i>${s}</span>`).join('')+'<span><i class="color simbolo"></i>Anillo negro: existente</span>';
function seleccion(){return $('poligono').value==='todos'?ids:[$('poligono').value];}
function puntos(p){return $('etapa').value==='inicial'?p.inicial:p.puntos;}
function visible(z,i,p){return (+$('especie').value<0||z[2]===+$('especie').value)&&($('tipo').value==='todas'||($('tipo').value==='existentes')===(i<p.nf));}
function reiniciar(){zoom=1;pan=[0,0];}
function actualizar(){
 const keys=seleccion(), ps=keys.map(k=>D.poligonos[k]), disponible=ps.every(p=>p.inicial!==null);
 $('etapa').options[1].disabled=!disponible;
 if(!disponible)$('etapa').value='final';
 $('acercar').disabled=$('alejar').disabled=keys.length!==1;
 canvas.style.height=keys.length===1?'640px':`${Math.ceil(keys.length/Math.min(5,keys.length))*180}px`;
 const cuentas=D.especies.map(()=>[0,0]);let visibles=0;
 ps.forEach(p=>puntos(p).forEach((z,i)=>{cuentas[z[2]][i<p.nf?0:1]++;if(visible(z,i,p))visibles++;}));
 $('estado').textContent=`${keys.length} ${keys.length===1?'polígono':'polígonos'} · ${fmt(visibles)} plantas visibles de ${fmt(ps.reduce((n,p)=>n+p.total,0))} · distribución ${$('etapa').value}${disponible?'':' · inicial no disponible para toda esta selección'}`;
 $('titulo').textContent=keys.length===1?`${keys[0]} · ${fmt(ps[0].area_ha)} ha`:'Resumen de los polígonos';
 let detalle=`<div class="metrica">${fmt(ps.reduce((n,p)=>n+p.total,0))} plantas</div>`;
 if(keys.length===1){
  const p=ps[0];detalle+=`<div class="datos">Geometría: <b>${p.geometria.tipo}</b><br>Existentes: ${p.geometria.existentes}<br>Semilla: ${p.semilla} · escenario: ${p.escenario}<br>Separación mínima exigida: ${p.separacion_min} m<br>Coordenadas locales; origen: ${p.geometria.origen_m.join(', ')} m</div><h3>Competencia</h3><table><tr><th>Método</th><th>J</th></tr>${Object.entries(p.competencia).map(([k,v])=>`<tr><td>${k}</td><td>${fmt(v)}</td></tr>`).join('')}</table><p class="datos">Final FF: ${fmt(p.desglose.FF)} · FV: ${fmt(p.desglose.FV)} · VV: ${fmt(p.desglose.VV)}</p>`;
  detalle+='<details><summary>Procedencia SHA-256</summary>'+Object.entries(p.fuentes_sha256).map(([n,h])=>`<p class="datos">${n}<br><code>${h}</code></p>`).join('')+'</details>';
  $('matriz').innerHTML='<table>'+p.matriz_C.map((r,i)=>`<tr><th>${D.especies[i]}</th>${r.map(v=>`<td>${v}</td>`).join('')}</tr>`).join('')+'</table>';
 }else{$('matriz').textContent='Seleccione un polígono para consultar su matriz.';}
 detalle+='<h3>Composición de la selección</h3><p class="datos">Conteos completos de la etapa elegida. Los filtros afectan el lienzo y el CSV visible.</p><table><tr><th>Especie</th><th>Existentes</th><th>Nuevas</th><th>Total</th></tr>'+cuentas.map((r,i)=>`<tr><td><i class="color" style="background:${C[i]}"></i>${D.especies[i]}</td><td>${r[0]}</td><td>${r[1]}</td><td>${r[0]+r[1]}</td></tr>`).join('')+'</table>';
 $('detalle').innerHTML=detalle; programar();
}
function programar(){if(!pendiente){pendiente=true;requestAnimationFrame(()=>{pendiente=false;dibujar();});}}
function dibujar(){
 const b=canvas.getBoundingClientRect(),ratio=window.devicePixelRatio||1;
 canvas.width=Math.round(b.width*ratio);canvas.height=Math.round(b.height*ratio);ctx.setTransform(ratio,0,0,ratio,0,0);
 ctx.fillStyle='#fff';ctx.fillRect(0,0,b.width,b.height);paneles=[];
 const keys=seleccion(), cols=keys.length===1?1:Math.min(b.width<600?3:5,keys.length),rows=Math.ceil(keys.length/cols),w=b.width/cols,h=b.height/rows;
 keys.forEach((id,k)=>{
  const p=D.poligonos[id], left=k%cols*w,top=Math.floor(k/cols)*h,solo=keys.length===1;
  paneles.push({id,left,top,w,h});ctx.save();ctx.beginPath();ctx.rect(left+1,top+1,w-2,h-2);ctx.clip();
  ctx.strokeStyle='#d4e2d9';ctx.strokeRect(left+1,top+1,w-2,h-2);ctx.fillStyle='#183d31';ctx.font='bold 12px system-ui';ctx.fillText(`${id} · ${p.area_ha.toFixed(2)} ha · ${p.total}`,left+9,top+19);
  const [minx,miny,maxx,maxy]=p.limites,s=Math.min((w-24)/(maxx-minx),(h-48)/(maxy-miny))*(solo?zoom:1),cx=(minx+maxx)/2,cy=(miny+maxy)/2;
  const X=x=>left+w/2+(x-cx)*s+(solo?pan[0]:0),Y=y=>top+h/2+12-(y-cy)*s+(solo?pan[1]:0);
  // Polygon and MultiPolygon preserve holes; evenodd also handles nested rings.
  const geom=p.geometria.geometria,polys=geom.type==='Polygon'?[geom.coordinates]:geom.coordinates;
  ctx.beginPath();polys.forEach(poly=>poly.forEach(ring=>{ring.forEach((z,j)=>j?ctx.lineTo(X(z[0]),Y(z[1])):ctx.moveTo(X(z[0]),Y(z[1])));ctx.closePath();}));ctx.fillStyle='#f2f7f1';ctx.fill('evenodd');ctx.strokeStyle='#869c89';ctx.lineWidth=1;ctx.stroke();
  const puntosEtapa=puntos(p),r=solo?Math.min(5,Math.max(1.8,s*.7)):.8;
  // Twenty batched paths per polygon instead of a DOM node per plant.
  for(let especie=0;especie<C.length;especie++)for(const fija of [false,true]){
   ctx.beginPath();puntosEtapa.forEach((z,i)=>{if(z[2]!==especie||(i<p.nf)!==fija||!visible(z,i,p))return;const x=X(z[0]),y=Y(z[1]);if(x<left||x>left+w||y<top+26||y>top+h)return;ctx.moveTo(x+r,y);ctx.arc(x,y,r,0,2*Math.PI);});ctx.fillStyle=C[especie];ctx.fill();if(fija){ctx.strokeStyle='#171f19';ctx.lineWidth=solo?.7:.3;ctx.stroke();}
  }
  ctx.restore();
 });
}
for(const id of ['poligono','especie','tipo','etapa'])$(id).onchange=()=>{if(id==='poligono')reiniciar();actualizar();};
$('restablecer').onclick=()=>{reiniciar();$('poligono').value='todos';$('especie').value='-1';$('tipo').value='todas';$('etapa').value='final';actualizar();};
function cambiarZoom(f){zoom=Math.min(30,Math.max(.3,zoom*f));programar();}
$('acercar').onclick=()=>cambiarZoom(1.3);$('alejar').onclick=()=>cambiarZoom(1/1.3);
canvas.addEventListener('wheel',e=>{if(seleccion().length!==1)return;e.preventDefault();cambiarZoom(e.deltaY<0?1.15:1/1.15);},{passive:false});
canvas.onpointerdown=e=>{arrastre={x:e.clientX,y:e.clientY,pan:[...pan],movido:false};canvas.setPointerCapture(e.pointerId);};
canvas.onpointermove=e=>{if(!arrastre||seleccion().length!==1)return;const dx=e.clientX-arrastre.x,dy=e.clientY-arrastre.y;arrastre.movido=Math.abs(dx)+Math.abs(dy)>4;pan=[arrastre.pan[0]+dx,arrastre.pan[1]+dy];programar();};
canvas.onpointerup=e=>{const a=arrastre;arrastre=null;if(a?.movido)return;const b=canvas.getBoundingClientRect(),x=e.clientX-b.left,y=e.clientY-b.top,p=paneles.find(p=>x>=p.left&&x<=p.left+p.w&&y>=p.top&&y<=p.top+p.h);if(p){$('poligono').value=p.id;reiniciar();actualizar();}};
function descargar(url,nombre){const a=document.createElement('a');a.href=url;a.download=nombre;a.click();}
$('exportar').onclick=()=>{dibujar();canvas.toBlob(blob=>{const url=URL.createObjectURL(blob);descargar(url,`DSATUR_${$('poligono').value}_${$('etapa').value}.png`);setTimeout(()=>URL.revokeObjectURL(url),1000);});};
$('csv').onclick=()=>{const lineas=['poligono,indice,x_m,y_m,existente,especie'];seleccion().forEach(id=>{const p=D.poligonos[id];puntos(p).forEach((z,i)=>{if(visible(z,i,p))lineas.push([id,i,z[0],z[1],i<p.nf,D.especies[z[2]]].join(','));});});const url=URL.createObjectURL(new Blob(['\ufeff'+lineas.join('\n')],{type:'text/csv;charset=utf-8'}));descargar(url,'DSATUR_visible.csv');setTimeout(()=>URL.revokeObjectURL(url),1000);};
window.addEventListener('resize',programar);actualizar();
