/** Pointer and keyboard editing of the existing property stations. */
export function createDistributionPointEditor(svg,{points,projection,enabled,mirrored,change,complete=()=>{}}) {
  let drag=null;
  let keyboard=false;
  const rounded=value=>Number(value.toPrecision(12));
  function indexOf(target){
    const handle=target.closest('[data-distribution-point]');
    if(!handle||!svg.contains(handle))return -1;
    const index=Number(handle.getAttribute('data-distribution-point'));
    return Number.isInteger(index)&&index>=0&&index<points().length?index:-1;
  }
  function coordinates(event){
    const matrix=svg.getScreenCTM();if(!matrix)return null;
    const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;
    const local=point.matrixTransform(matrix.inverse());
    return [projection.station(local.x),projection.value(local.y)];
  }
  function move(index,station,value){
    if(!enabled()||!Number.isFinite(station)||!Number.isFinite(value))return;
    const rows=points(),row=rows[index];if(!row)return;
    // Keep station order, doubled-station jumps, and the mirrored center.
    const left=index?Number(rows[index-1][0]):projection.xmin;
    const right=index+1<rows.length?Number(rows[index+1][0]):projection.xmax;
    if(!Number.isFinite(left)||!Number.isFinite(right)||left>right)return;
    const fixed=(mirrored()&&index===0&&Number(row[0])===0)
      ||(index>0&&left===Number(row[0]))||(index+1<rows.length&&right===Number(row[0]));
    const gap=Math.max((projection.xmax-projection.xmin)*1e-9,Number.EPSILON*Math.max(1,Math.abs(left),Math.abs(right))*8);
    const low=index?left+gap:left,high=index+1<rows.length?right-gap:right;
    const next=[fixed||low>high?Number(row[0]):Math.max(low,Math.min(high,rounded(station))),
      rounded(Math.max(projection.ymin,Math.min(projection.ymax,value)))];
    if(next[0]!==Number(row[0])||next[1]!==Number(row[1]))change(index,next);
  }
  function finish({revert=false,save=false}={}){
    if(!drag)return;
    const previous=drag;drag=null;
    svg.classList.remove('distribution-dragging');
    if(revert&&enabled())change(previous.index,previous.original);
    if(svg.hasPointerCapture(previous.pointer))svg.releasePointerCapture(previous.pointer);
    if(save&&points()[previous.index]?.some((v,i)=>Number(v)!==previous.original[i]))complete();
  }
  svg.onpointerdown=event=>{
    if(!enabled()||drag||event.button!==0||event.isPrimary===false)return;
    const index=indexOf(event.target);if(index<0)return;
    const origin=coordinates(event),row=points()[index].map(Number);
    if(!origin||!row.every(Number.isFinite))return;
    drag={index,pointer:event.pointerId,original:row,offset:[row[0]-origin[0],row[1]-origin[1]]};
    svg.setPointerCapture(event.pointerId);
    event.target.focus?.({preventScroll:true});
    svg.classList.add('distribution-dragging');event.preventDefault();
  };
  svg.onpointermove=event=>{
    if(!drag||event.pointerId!==drag.pointer)return;
    if(!enabled()){finish();return;}
    const point=coordinates(event);if(!point)return;
    move(drag.index,point[0]+drag.offset[0],point[1]+drag.offset[1]);event.preventDefault();
  };
  svg.onpointerup=event=>{
    if(!drag||event.pointerId!==drag.pointer)return;
    svg.onpointermove(event);finish({save:true});
  };
  svg.onpointercancel=event=>{if(drag&&event.pointerId===drag.pointer)finish({revert:true});};
  svg.onlostpointercapture=event=>{if(drag&&event.pointerId===drag.pointer)finish({revert:true});};
  svg.onkeydown=event=>{
    if(event.key==='Escape'&&drag){finish({revert:true});event.preventDefault();return;}
    if(!enabled()||drag)return;
    const index=indexOf(event.target);if(index<0)return;
    const directions={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,1],ArrowDown:[0,-1]};
    const direction=directions[event.key];if(!direction)return;
    const [station,value]=points()[index].map(Number),step=event.shiftKey?10:1;
    move(index,station+direction[0]*(projection.xmax-projection.xmin)*.005*step,
      value+direction[1]*(projection.ymax-projection.ymin)*.005*step);
    keyboard=true;
    event.preventDefault();
  };
  const finishKeyboard=()=>{if(keyboard){keyboard=false;complete();}};
  svg.onkeyup=event=>{if(event.key.startsWith('Arrow'))finishKeyboard();};
  svg.onfocusout=finishKeyboard;
  return {stop:()=>finish(),destroy(){
    finish();keyboard=false;
    for(const name of ['pointerdown','pointermove','pointerup','pointercancel','lostpointercapture','keydown','keyup','focusout'])svg['on'+name]=null;
  }};
}
