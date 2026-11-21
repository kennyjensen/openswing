/* CPU projection fallback for browsers without a usable WebGL2 context.
   Uses the actual geometry, depth-sorted faces, and the same orbit/zoom controls. */
import { groundGrid } from './ground-grid.js';
import { beamColor, wireframeColor, engineColor } from './plot-colors.js';
import { surfaceFillColor } from './surface-shading.js';
import { surfaceFaces } from './surface-faces.js';
import { copyViewerFrame } from './viewer-capture.js';
export function createSoftwareViewer(element) {
  const canvas=document.createElement('canvas');
  canvas.setAttribute('aria-label','Aircraft geometry. Drag to orbit; scroll to zoom.');
  canvas.dataset.renderer='canvas2d';
  element.replaceChildren(canvas);
  const ctx=canvas.getContext('2d');
  if(!ctx){canvas.remove();throw new Error('Canvas rendering is unavailable.');}
  const listeners=new AbortController();
  let disposed=false;
  let beams=[], attachments=[], ground=null, center=[0,0,0], extent=1, yaw=.35, pitch=.55, zoom=1, grid=true;
  let width=1,height=1,down=null;
  let framingVertices=[],streamwiseChords=true;
  const faces=b=>surfaceFaces(b,{streamwise:streamwiseChords});
  const rotate=(p)=>{
    const x=p[0]-center[0],y=p[1]-center[1],z=p[2]-center[2];
    const horizontal=Math.cos(yaw)*y+Math.sin(yaw)*x;
    const depth=Math.cos(yaw)*x-Math.sin(yaw)*y;
    return [horizontal,Math.sin(pitch)*depth-Math.cos(pitch)*z,Math.cos(pitch)*depth+Math.sin(pitch)*z];
  };
  function draw(){
    if(disposed)return;
    ctx.clearRect(0,0,width,height);ctx.fillStyle='#131d20';ctx.fillRect(0,0,width,height);
    const vertices=beams.flatMap(b=>b.quads.flat().concat(b.axis.flat())).concat(attachments.flatMap(o=>o.segments.flat()));
    if(!vertices.length)return;
    const rotated=framingVertices.map(rotate);
    const xs=rotated.map(p=>p[0]),ys=rotated.map(p=>p[1]);
    const dx=Math.max(...xs)-Math.min(...xs),dy=Math.max(...ys)-Math.min(...ys);
    const scale=.72*Math.min(width/Math.max(dx,extent*.2),height/Math.max(dy,extent*.2))*zoom;
    const project=p=>{const [x,y,z]=rotate(p);const perspective=1/(1+z/(extent*5));return [width/2+x*scale*perspective,height/2+y*scale*perspective,z];};
    function path(points,stroke,fill=null){
      const ps=points.map(project);ctx.beginPath();ps.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));
      if(fill){ctx.closePath();ctx.fillStyle=fill;ctx.fill();}ctx.strokeStyle=stroke;ctx.lineWidth=.7;ctx.stroke();
    }
    if(grid && ground?.flag){
      const plane=groundGrid(ground,center,extent);
      for(const segment of plane.segments)path(segment,plane.color);
    } else if(grid){
      const floor=center[2]-extent*.08;
      for(let i=-10;i<=10;i++){
        const s=i*extent/10;
        path([[center[0]-extent,center[1]+s,floor],[center[0]+extent,center[1]+s,floor]],'#263b3c');
        path([[center[0]+s,center[1]-extent,floor],[center[0]+s,center[1]+extent,floor]],'#263b3c');
      }
    }
    const polygons=beams.flatMap(b=>{
      const color=beamColor(beams,b.index),fill=surfaceFillColor(color),wire=wireframeColor(color);
      return faces(b).map(q=>({q,fill,wire,depth:q.reduce((sum,p)=>sum+rotate(p)[2],0)/q.length}));
    });
    polygons.sort((a,b)=>b.depth-a.depth).forEach(f=>path(f.q,f.wire,f.fill));
    for(const b of beams){
      const wire=wireframeColor(beamColor(beams,b.index));
      for(const segment of b.axis)path(segment,wire);
    }
    for(const object of attachments)for(const segment of object.segments)path(segment,object.color??(object.kind==='engine'?engineColor:'#e8ba77'));
  }
  function fit(view='perspective'){
    framingVertices=beams.flatMap(b=>faces(b).flat().concat(b.axis.flat())).concat(attachments.filter(o=>!o.overlay).flatMap(o=>o.segments.flat()));
    if(!framingVertices.length)return;
    const lo=[0,1,2].map(i=>Math.min(...framingVertices.map(p=>p[i]))),hi=[0,1,2].map(i=>Math.max(...framingVertices.map(p=>p[i])));
    center=lo.map((x,i)=>(x+hi[i])/2);extent=Math.max(...hi.map((x,i)=>x-lo[i]),1e-6);
    zoom=1;yaw=view==='front'?0:.35;pitch=view==='top'?Math.PI/2:view==='front'?0:.55;
    if(view==='top')yaw=0;draw();
  }
  canvas.style.touchAction='none';
  const options={signal:listeners.signal};
  canvas.addEventListener('pointerdown',e=>{down={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);},options);
  canvas.addEventListener('pointermove',e=>{if(!down)return;yaw+=(e.clientX-down.x)*.006;pitch=Math.max(-1.55,Math.min(1.55,pitch+(e.clientY-down.y)*.006));down={x:e.clientX,y:e.clientY};draw();},options);
  canvas.addEventListener('pointerup',()=>down=null,options);
  canvas.addEventListener('pointercancel',()=>down=null,options);
  canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.1,Math.min(15,zoom*Math.exp(-e.deltaY*.001)));draw();},{...options,passive:false});
  const resize=new ResizeObserver(()=>{
    if(disposed)return;
    const box=element.getBoundingClientRect();
    // Mobile tabs temporarily hide the viewer. Keep its last valid buffer and
    // framing until the observer reports visible dimensions again.
    if(!box.width||!box.height)return;
    width=box.width;height=box.height;const dpr=Math.min(devicePixelRatio,2);
    canvas.width=width*dpr;canvas.height=height*dpr;canvas.style.width=`${width}px`;canvas.style.height=`${height}px`;
    ctx.setTransform(dpr,0,0,dpr,0,0);draw();
  });
  resize.observe(element);
  function setGridVisible(visible){grid=visible;draw();}
  return {kind:'canvas2d',fit,setGridVisible,toggleGrid(){setGridVisible(!grid);},
    capture(target,options){if(disposed)throw new Error('The aircraft view is unavailable.');draw();return copyViewerFrame(canvas,target,options);},
    update(data,objects=[],plane=null,{fit:refit=true,streamwiseChords:projection=true}={}){if(disposed)return;beams=data;attachments=objects;ground=plane;streamwiseChords=projection;if(refit||!framingVertices.length)fit();else draw();},
    dispose(){if(disposed)return;disposed=true;resize.disconnect();listeners.abort();down=null;canvas.remove();beams=[];attachments=[];framingVertices=[];ground=null;},
  };
}
