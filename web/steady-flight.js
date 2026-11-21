import {selectedNumerics,numericalSelection} from './numerical-policy.js';

// Match the kernel's operating_points._actual_condition: result metadata owns
// the solved state, while request.condition retains the original inputs.
export function solvedFlightCondition(condition,result){
  if(condition==null)return condition;
  const actual=structuredClone(condition);
  const vectors=['rates','acceleration','angular_acceleration','position_earth','attitude','ground_normal'];
  for(const [variable,value] of Object.entries(result.operating_values??{})){
    if(['speed','alpha','beta'].includes(variable)){actual[variable]=value;continue;}
    const [group,axis]=variable.split('.');
    if(group==='control'||group==='power'){
      (actual[`${group}s`]??={})[axis]=value;
    }else if(vectors.includes(group)){
      const index=(group==='attitude'?['bank','elevation','heading']:['x','y','z']).indexOf(axis);
      if(index>=0){
        actual[group]??=group==='ground_normal'?[0,0,1]:[0,0,0];
        actual[group][index]=value;
      }
    }
  }
  for(const [actuator,value] of Object.entries(result.feedback?.actuators??{})){
    if(/^[FE]\d+$/.test(actuator))
      (actual[actuator[0]==='F'?'controls':'powers']??={})[actuator.slice(1)]=value;
  }
  return actual;
}

export const steadyFlightSettings=`
<section id="steady-flight-settings" class="flight-trim" aria-labelledby="steady-flight-title">
  <h2 id="steady-flight-title">Steady flight</h2>
  <label class="field-label" for="flight-trim-kind">Flight condition</label>
  <select id="flight-trim-kind"><option value="level">Powered level flight</option><option value="glide">Unpowered glide</option></select>
  <details class="advanced"><summary>Trim controls</summary>
    <div class="fields">
      <label>Pitch<select id="flight-trim-pitch"></select></label>
      <label>Yaw<select id="flight-trim-yaw"></select></label>
      <label>Roll<select id="flight-trim-roll"></select></label>
      <label id="flight-trim-power-field">Thrust<select id="flight-trim-power"></select></label>
    </div>
  </details>
  <p id="flight-trim-note">Balance forces and moments at the airspeed above.</p>
  <button id="trim-steady-flight" type="button" class="full-width" disabled>Trim for steady flight</button>
  <p id="flight-trim-status" role="status" hidden></p>
</section>`;

// Build ordinary operating constraints, using the current aircraft and units.
// No saved validation state or aircraft-specific response is substituted.
export function steadyFlightConfiguration(configuration,model,{kind,pitch,yaw,roll='',power}){
  if(!['level','glide'].includes(kind))throw new Error('Select level flight or an unpowered glide.');
  const controls=model.controls.map(String),engines=model.engine_controls.map(e=>String(e.index));
  if(!controls.includes(pitch)||!controls.includes(yaw)||pitch===yaw)
    throw new Error('Choose distinct pitch and yaw controls under Trim controls.');
  if(roll!==''&&(!controls.includes(roll)||[pitch,yaw].includes(roll)))
    throw new Error('Choose a separate roll control, or use sideslip for roll balance.');
  if(kind==='level'&&!engines.includes(power))throw new Error('Level-flight trim needs a thrust control. Select an unpowered glide for an aircraft without an engine.');
  if(!configuration.fields.speed.trim()||!Number.isFinite(Number(configuration.fields.speed))||Number(configuration.fields.speed)<=0)
    throw new Error('Enter a positive airspeed before trimming.');
  const result=structuredClone(configuration),f=result.fields;
  f.mode='mounted';
  if(!['midpoint','aswing-coupled','aswing-airflow'].includes(numericalSelection(result.numerics)))
    result.numerics=selectedNumerics('aswing-airflow');
  for(const kind of ['rates','acceleration','angular_acceleration'])for(const axis of ['x','y','z'])f[`${kind}-${axis}`]='0';
  if(roll!=='')f.beta='0';
  f['attitude-bank']='0';f['attitude-elevation']=f.alpha;
  f['feedback-enabled']=false;f['derivatives-enable']=false;
  f['modal-vacuum']=false;f['modal-quiescent']=false;
  for(const frame of ['time-frame','frequency-frame','modal-frame','modal-ordinary-frame'])f[frame]='free';
  // A generic steady-flight trim starts from the current inputs, not an
  // equilibrium belonging to a different condition or equation selection.
  result.equilibrium={state:null,enabled:false,label:''};
  if(kind==='glide')for(const id of engines)result.powers[id]='0';
  const target=(variable,quantity)=>({variable,quantity,target:0});
  result.constraints=[target('alpha','force.z'),target('attitude.bank','force.y'),
    target(kind==='level'?`power.${power}`:'attitude.elevation','force.x'),
    target(roll===''?'beta':`control.${roll}`,'moment.x'),
    target(`control.${pitch}`,'moment.y'),target(`control.${yaw}`,'moment.z')];
  if(kind==='level')result.constraints.push(target('attitude.elevation','flight_path'));
  return result;
}

export function createSteadyFlight({getState,capture,load,run,accept,showError}){
  const $=id=>document.getElementById(id);
  let working=false,source=null;
  function refresh(){
    const state=getState(),disabled=working||state.busy||state.dirty||!state.model;
    for(const el of $('steady-flight-settings').querySelectorAll('select,button'))el.disabled=disabled;
    $('trim-steady-flight').textContent=working?'Trimming…':'Trim for steady flight';
    $('flight-trim-power-field').hidden=$('flight-trim-kind').value==='glide';
    $('flight-trim-note').textContent=$('flight-trim-kind').value==='glide'
      ?'Solve the glide angle at the airspeed above, with thrust off.'
      :'Balance forces and moments at the airspeed above.';
  }
  function setModel(model,asw){
    if(asw===source){refresh();return;}
    source=asw;
    const controls=model.controls.map(String),engines=model.engine_controls.map(e=>String(e.index));
    const pitch=controls.includes('2')?'2':controls[0]??'';
    const yaw=controls.includes('3')?'3':controls.find(id=>id!==pitch)??'';
    for(const [name,ids,selected] of [['pitch',controls,pitch],['yaw',controls,yaw],
      ['roll',controls,controls.includes('1')&&![pitch,yaw].includes('1')?'1':''],['power',engines,engines[0]??'']]){
      const select=$(`flight-trim-${name}`);select.replaceChildren();
      if(name==='roll'||!ids.length){const option=document.createElement('option');option.value='';option.textContent=name==='roll'?'Use sideslip':'Unavailable';select.append(option);}
      for(const id of ids){const option=document.createElement('option');option.value=id;option.textContent=`${name==='power'?'Engine':'Flap'} ${id}`;select.append(option);}
      select.value=selected;
    }
    $('flight-trim-kind').value=engines.length?'level':'glide';refresh();
  }
  function clear(){ $('flight-trim-status').hidden=true;refresh(); }
  $('flight-trim-kind').onchange=refresh;
  $('trim-steady-flight').onclick=async()=>{
    if(working||getState().busy||getState().dirty||!getState().model)return;
    const message=$('flight-trim-status');
    try{
      const options=Object.fromEntries(['kind','pitch','yaw','roll','power'].map(key=>[key,$(`flight-trim-${key}`).value]));
      const configuration=steadyFlightConfiguration(capture(),getState().model,options);
      working=true;refresh();
      await load(configuration);
      message.hidden=false;message.textContent='Solving steady-flight balance…';
      const result=await run();
      if(!result?.equilibrium_state){
        // Run analysis already reports the precise validation/solver error.
        // Keep it visible instead of replacing it with a generic trim error.
        message.hidden=false;message.textContent='Trim did not finish. Review the solver message and flight settings.';
        return;
      }
      accept(result);
      message.hidden=false;message.textContent='Trim complete. Flight inputs updated; the trimmed state is ready for Bode, modes or time response.';
    }catch(error){message.hidden=false;message.textContent=error.message;showError(error);}
    finally{working=false;refresh();}
  };
  refresh();return {refresh,setModel,clear};
}
