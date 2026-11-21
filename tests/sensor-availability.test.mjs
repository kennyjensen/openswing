import test from 'node:test';
import assert from 'node:assert/strict';
import {sensorFields,sensorFieldAvailable,sensorAvailabilityDescription,createSensorResults} from '../web/sensor-results.js';
import {createCustomConstraints} from '../web/custom-constraints.js';
import {defaultSensorRomOutputs} from '../web/rom-results.js';

const frameFields=['alpha','beta','bank','air_velocity_sensor','acceleration_sensor','angular_acceleration_sensor','rates_sensor'];
const independentFields=['speed','heading','elevation','position_earth','velocity_earth','anchor_position_body','anchor_velocity_body','displacement_body','position_body','force_local','moment_local','strain','curvature_change','circulation','shell_strain','shell_shear_stress'];
const collinear={index:2,beam:1,t:1,axes_available:false,v_axis_available:true,
  axes_unavailable_reason:'Sensor V and A directions are collinear',axes_body:null,axes_earth:null,
  speed:10,alpha:null,beta:null,bank:null,elevation:0,heading:180,
  air_velocity_sensor:null,acceleration_sensor:null,angular_acceleration_sensor:null,rates_sensor:null,
  position_earth:[1,2,3],velocity_earth:[-10,0,0],flow_singular:false,attitude_singular:false,flow_mode:'total'};

test('collinear directions preserve speed, V-direction attitude, GPS and structural selections',()=>{
  const inspected={index:2,axes_available:false,v_axis_available:true};
  for(const row of [inspected,collinear]){
    for(const field of frameFields)assert.equal(sensorFieldAvailable(row,field),false,field);
    for(const field of independentFields)assert.equal(sensorFieldAvailable(row,field),true,field);
  }
});

test('missing V direction excludes its angles without excluding scalar speed or body outputs',()=>{
  const row={axes_available:false,v_axis_available:false};
  for(const field of ['heading','elevation',...frameFields])assert.equal(sensorFieldAvailable(row,field),false,field);
  for(const field of ['speed','position_body','position_earth','velocity_earth','force_local'])assert.equal(sensorFieldAvailable(row,field),true,field);
});

test('explicit unavailable measurements are excluded while zero values and legacy metadata remain available',()=>{
  for(const [field] of sensorFields)assert.equal(sensorFieldAvailable({index:1},field),true,field);
  for(const field of ['speed','heading','shell_shear_stress']){
    assert.equal(sensorFieldAvailable({[field]:0},field),true);
    assert.equal(sensorFieldAvailable({[field]:null},field),false);
  }
  assert.equal(sensorFieldAvailable({axes_available:true,acceleration_sensor:[0,0,0]},'acceleration_sensor'),true);
  assert.equal(sensorFieldAvailable({axes_available:true,acceleration_sensor:null},'acceleration_sensor'),false);
});

test('frame unavailability is described without falsely claiming zero airflow',()=>{
  for(const complex of [false,true]){
    const message=sensorAvailabilityDescription(collinear,complex);
    assert.match(message,/Sensor frame unavailable: Sensor V and A directions are collinear/);
    assert.doesNotMatch(message,/zero airflow|zero airspeed|vertical/);
    assert.doesNotMatch(sensorAvailabilityDescription({...collinear,flow_singular:undefined},complex),/zero airflow|zero airspeed/);
    assert.doesNotMatch(sensorAvailabilityDescription({...collinear,flow_singular:null},complex),/zero airflow|zero airspeed/);
  }
});

test('flow flag distinguishes zero airflow and preserves old result warnings',()=>{
  assert.match(sensorAvailabilityDescription({...collinear,speed:0,flow_singular:true}),/Flow angles are undefined at zero airspeed/);
  assert.match(sensorAvailabilityDescription({...collinear,speed:0,flow_singular:true},true),/Airspeed and flow-angle perturbations are undefined at zero airflow/);
  assert.equal(sensorAvailabilityDescription({speed:10,alpha:0,attitude_singular:false}),'');
  assert.match(sensorAvailabilityDescription({speed:0,alpha:null}),/zero airspeed/);
  assert.doesNotMatch(sensorAvailabilityDescription({speed:0,alpha:null,flow_singular:false}),/zero/);
});

test('undefined V and vertical attitude warnings remain distinct',()=>{
  assert.match(sensorAvailabilityDescription({...collinear,v_axis_available:false,attitude_singular:true}),/V direction is unavailable/);
  assert.doesNotMatch(sensorAvailabilityDescription({...collinear,v_axis_available:false,attitude_singular:true}),/vertical/);
  assert.match(sensorAvailabilityDescription({attitude_singular:true}),/Bank and heading are undefined at this vertical/);
  assert.match(sensorAvailabilityDescription({attitude_singular:true},true),/Euler-angle perturbations are undefined/);
});

test('ROM defaults retain independent GPS channels and omit unavailable accelerometers',()=>{
  const gps='RX[2], RY[2], RZ[2], UX[2], UY[2], UZ[2]';
  assert.equal(defaultSensorRomOutputs(collinear),gps);
  assert.equal(defaultSensorRomOutputs({index:2,axes_available:false}),gps);
  assert.equal(defaultSensorRomOutputs({index:2,acceleration_sensor:null}),gps);
  assert.equal(defaultSensorRomOutputs({index:2}),gps+', Ax[2], Ay[2], Az[2]');
  assert.equal(defaultSensorRomOutputs({index:2,axes_available:true,acceleration_sensor:[0,0,0]}),gps+', Ax[2], Ay[2], Az[2]');
  assert.equal(defaultSensorRomOutputs(null),'V, A, B, Ax, Ay, Az, Wx, Wy, Wz');
});

class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.textContent='';this._value=null;}
  get value(){return this._value??(this.tagName==='select'?this.children[0]?.value??'':'');}
  set value(value){this._value=String(value);}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;if(this.tagName==='select')this._value=null;}
  setAttribute(name,value){this[name]=value;}
  addEventListener(){}
}
function withDocument(fn){
  const previous=globalThis.document,elements=new Map(),rows=[];
  const get=id=>{if(!elements.has(id))elements.set(id,new Element(id==='sensor-select'?'select':'div'));return elements.get(id);};
  globalThis.document={getElementById:get,createElement:tag=>new Element(tag),querySelectorAll:()=>rows};
  try{return fn({get,rows});}finally{globalThis.document=previous;}
}
const descendants=node=>[node,...node.children.filter(child=>child instanceof Element).flatMap(descendants)];

test('custom constraint menu excludes unavailable fields but preserves a typed expression for kernel validation',()=>withDocument(({get,rows})=>{
  const model={sensors:[{index:2,axes_available:false,v_axis_available:true},{index:3,axes_available:false,v_axis_available:false}]};
  const row=new Element();row.querySelector=selector=>({value:selector==='.constraint-quantity'?'user':'alpha'});rows.push(row);
  const constraints=createCustomConstraints(()=>model,()=>{});
  constraints.remember(row,{quantity:'user.saved',expression:'sensor("2.alpha")',unit:'deg',residual_scale:1});
  constraints.refresh();
  const select=descendants(get('custom-trim-equations')).find(node=>node.tagName==='select');
  const options=new Set(select.children.map(option=>option.value));
  for(const channel of ['2.speed','2.heading','2.elevation','2.position_earth.x','2.force_local.c','3.speed','3.displacement_body.y'])assert.ok(options.has(channel),channel);
  for(const channel of ['2.alpha','2.beta','2.bank','2.acceleration_sensor.x','2.rates_sensor.z','3.heading','3.elevation'])assert.equal(options.has(channel),false,channel);
  assert.equal(constraints.read(row).expression,'sensor("2.alpha")');
}));

test('sensor table and CSV retain null channels as gaps, independent values and original records',()=>withDocument(({get})=>{
  const sensor=structuredClone(collinear),before=structuredClone(sensor),downloads=[];
  const view=createSensorResults(()=>({result:{sensors:[sensor]}}),(...args)=>downloads.push(args));
  view.render();
  assert.match(get('sensor-detail').textContent,/directions are collinear/);
  assert.doesNotMatch(get('sensor-detail').textContent,/zero airflow|zero airspeed/);
  const table=get('sensor-table').children[0],body=table.children[1];
  const values=new Map(body.children.map(row=>[row.children[0].textContent,row.children[2].textContent]));
  assert.equal(values.get('Airspeed'),'10.00000');
  assert.equal(values.get('Flow alpha'),'—');
  assert.equal(values.get('Specific force (a − g) V'),'—');
  assert.equal(values.get('GPS position X'),'1.000000');
  get('sensor-csv').onclick();
  const csv=downloads[0][1];
  assert.match(csv,/"speed","input L\/T","10"/);
  assert.match(csv,/"alpha","deg",""/);
  assert.match(csv,/"acceleration_sensor\.0","input L\/T²",""/);
  assert.match(csv,/"position_earth\.0","input L","1"/);
  assert.deepEqual(sensor,before);
}));
