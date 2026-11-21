import {validateSolutionList} from './solution-data.js';
import {validateEquilibriumPacket} from './saved-state-data.js';
import {sourceNumerics,vacuumNumerics,stillAirNumerics,movingVacuumNumerics,numericalSelection,selectionAllowsMode,numericalModeLabel,assertNumericalIdentity,assertVacuumInputs,assertStillAirInputs,assertStillAirIdentity,assertMovingVacuumInputs,airflowNumerics,assertAirflowInputs} from './numerical-policy.js';
// Editable cases and immutable computed solutions have separate records.
export const PROJECT_LIMIT=64*1024*1024;
const plain=x=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.getPrototypeOf(x)===Object.prototype;
const fail=message=>{throw new Error(message);};
function object(value,label){if(!plain(value))fail(`${label} must be an object.`);}
function keys(value,allowed,label){object(value,label);for(const key of Object.keys(value))if(!allowed.includes(key))fail(`Unknown ${label} field: ${key}.`);}
function text(value,label,max=PROJECT_LIMIT){if(typeof value!=='string'||value.length>max||value.includes('\0'))fail(`Invalid ${label}.`);}
export function projectName(value){text(value,'name',160);const name=value.trim();if(!name)fail('Enter a name.');return name;}
export function validateJSON(value){
  const pending=[[value,0]];let count=0;
  while(pending.length){const [item,depth]=pending.pop();if(++count>2000000||depth>80)fail('Project structure is too large or deeply nested.');
    if(item===null||typeof item==='boolean'||typeof item==='string')continue;
    if(typeof item==='number'){if(!Number.isFinite(item))fail('Project numbers must be finite.');continue;}
    if(!Array.isArray(item)&&!plain(item))fail('Project values must be JSON data.');
    for(const v of Object.values(item))pending.push([v,depth+1]);
  }
}
export function validateConfiguration(value){
  keys(value,['source','filename','mesh','fields','controls','powers','circulation','derivative_parameters','constraints','equilibrium','numerics'],'case configuration');
  text(value.source,'ASW source',8*1024*1024);if(!value.source.trim())fail('A case needs ASW source text.');text(value.filename,'ASW filename',240);
  if(typeof value.mesh!=='number'&&!plain(value.mesh))fail('A case needs applied mesh settings.');
  object(value.fields,'Workbench settings');for(const v of Object.values(value.fields))if(typeof v!=='string'&&typeof v!=='boolean')fail('Workbench fields must contain text or checkbox values.');
  if(sourceNumerics(value.numerics)&&!selectionAllowsMode(numericalSelection(value.numerics),value.fields.mode))fail(`The selected ASWING equations require ${numericalModeLabel(value.numerics)}.`);
  if(vacuumNumerics(value.numerics))assertVacuumInputs(value.fields,value.constraints);
  if(stillAirNumerics(value.numerics))assertStillAirInputs(value.fields,value.constraints);
  if(movingVacuumNumerics(value.numerics))assertMovingVacuumInputs(value.fields,value.constraints);
  if(airflowNumerics(value.numerics))assertAirflowInputs(value.fields,value.constraints,{savedLaunch:value.fields.mode==='time'&&value.equilibrium?.enabled===true});
  for(const name of ['controls','powers','circulation']){object(value[name],name);for(const [key,v] of Object.entries(value[name]))if(!/^[1-9]\d*$/.test(key)||typeof v!=='string')fail(`Invalid ${name} setting.`);}
  if(!Array.isArray(value.derivative_parameters)||value.derivative_parameters.some(v=>typeof v!=='string')||new Set(value.derivative_parameters).size!==value.derivative_parameters.length)fail('Invalid derivative selection.');
  if(!Array.isArray(value.constraints)||value.constraints.length>200)fail('Invalid operating constraints.');
  for(const c of value.constraints){keys(c,['variable','quantity','target','weight','preferred','expression','unit','residual_scale'],'operating constraint');
    for(const k of ['variable','quantity']){text(c[k],k,160);if(!c[k])fail(`Missing constraint ${k}.`);}
    if(!Number.isFinite(c.target))fail('Constraint targets must be finite.');
    for(const k of ['weight','preferred','residual_scale'])if(Object.hasOwn(c,k)&&!Number.isFinite(c[k]))fail(`Constraint ${k} must be finite.`);
    for(const k of ['expression','unit'])if(Object.hasOwn(c,k))text(c[k],k);
  }
  keys(value.equilibrium,['state','enabled','label'],'loaded equilibrium');
  if(typeof value.equilibrium.enabled!=='boolean')fail('Invalid equilibrium enable setting.');text(value.equilibrium.label,'equilibrium label',240);
  const seed=value.equilibrium.state;
  if(seed!==null){validateEquilibriumPacket(seed);assertNumericalIdentity(value.numerics,seed.identity);}
  if(seed!==null&&stillAirNumerics(value.numerics))assertStillAirIdentity(seed,Number(value.fields['modal-quiescent-density']),Number(value.fields['body-added-mass']??1));
  if(seed?.launch!==undefined&&sourceNumerics(value.numerics)&&!vacuumNumerics(value.numerics)&&!stillAirNumerics(value.numerics)&&!movingVacuumNumerics(value.numerics)&&!airflowNumerics(value.numerics))fail('ASWING static equilibria cannot contain a dynamic launch.');
  if(seed===null&&value.equilibrium.enabled)fail('An enabled equilibrium needs a saved state.');
  validateJSON(value);return structuredClone(value);
}
export function validateProject(value){
  keys(value,['format','version','name','selected','cases','solutions','selected_solution'],'project');
  if(value.format!=='openswing-project'||![1,2].includes(value.version))fail('Expected a version-1 or version-2 OpenSwing project JSON file.');
  if(value.version===1&&(Object.hasOwn(value,'solutions')||Object.hasOwn(value,'selected_solution')))fail('Solution archives require project version 2.');
  const name=projectName(value.name);
  if(!Array.isArray(value.cases)||value.cases.length>200)fail('A project supports at most 200 cases.');
  const ids=new Set(),names=new Set();
  const cases=value.cases.map(c=>{keys(c,['id','name','configuration'],'case');text(c.id,'case identifier',100);if(!/^[a-zA-Z0-9_-]+$/.test(c.id)||ids.has(c.id))fail('Case identifiers must be unique.');ids.add(c.id);
    const label=projectName(c.name);if(names.has(label))fail('Case names must be unique.');names.add(label);return {id:c.id,name:label,configuration:validateConfiguration(c.configuration)};});
  if(value.selected!==null&&!ids.has(value.selected))fail('The selected case is missing.');
  const solutions=validateSolutionList(value.version===1?[]:value.solutions),selected_solution=value.version===1?null:value.selected_solution;
  if(selected_solution!==null&&!solutions.some(s=>s.id===selected_solution))fail('The selected solution is missing.');
  const out={format:'openswing-project',version:2,name,selected:value.selected,cases,solutions,selected_solution};
  if(new TextEncoder().encode(JSON.stringify(out)).length>PROJECT_LIMIT)fail('Project exceeds the 64 MiB file limit.');return out;
}
export function parseProject(source){text(source,'project file');if(new TextEncoder().encode(source).length>PROJECT_LIMIT)fail('Project exceeds the 64 MiB file limit.');return validateProject(JSON.parse(source));}
export const emptyProject=()=>({format:'openswing-project',version:2,name:'Untitled project',selected:null,cases:[],solutions:[],selected_solution:null});
export function sameConfiguration(a,b){
  const ordered=value=>Array.isArray(value)?value.map(ordered):plain(value)?Object.fromEntries(Object.keys(value).sort().map(key=>[key,ordered(value[key])])):value;
  return JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
}
export function changeCase(project,action,{id,name,configuration}={}){
  const next=validateProject(project),index=next.cases.findIndex(c=>c.id===id);
  if(action==='add'){if(index>=0)fail('Case identifier already exists.');next.cases.push({id,name:projectName(name),configuration:validateConfiguration(configuration)});next.selected=id;}
  else {if(index<0)fail('Select a saved case first.');
    if(action==='update')next.cases[index].configuration=validateConfiguration(configuration);
    else if(action==='rename')next.cases[index].name=projectName(name);
    else if(action==='delete'){next.cases.splice(index,1);if(next.selected===id)next.selected=next.cases[Math.min(index,next.cases.length-1)]?.id??null;}
    else if(action==='select')next.selected=id;
    else fail('Unknown project operation.');
  }
  return validateProject(next);
}

// Compare-and-swap in one IndexedDB transaction prevents an older tab from
// replacing another tab's saved project. A failed write leaves both records intact.
export function openProjectStore(indexedDB=globalThis.indexedDB){
  return new Promise((resolve,reject)=>{
    if(!indexedDB){reject(new Error('Browser storage is unavailable. Export projects to keep them.'));return;}
    const request=indexedDB.open('openswing-projects',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('workspace');
    request.onerror=()=>reject(request.error);request.onblocked=()=>reject(new Error('Close another OpenSwing tab to update browser storage.'));
    request.onsuccess=()=>{const db=request.result;db.onversionchange=()=>db.close();
      function transaction(write,operation){return new Promise((done,failed)=>{
        const tx=db.transaction('workspace',write?'readwrite':'readonly'),store=tx.objectStore('workspace');let result,error;
        tx.oncomplete=()=>done(result);tx.onabort=()=>failed(error??tx.error??new Error('Project storage failed.'));
        tx.onerror=()=>{};
        operation(store,value=>{result=value;},reason=>{error=reason;tx.abort();});
      });}
      resolve({read:()=>transaction(false,(store,set)=>{const r=store.get('current');r.onsuccess=()=>set(r.result??null);}),
        write:(project,expectedRevision)=>{const clean=validateProject(project);return transaction(true,(store,set,abort)=>{const r=store.get('current');r.onsuccess=()=>{
          const previous=r.result??null;if((previous?.revision??0)!==expectedRevision){abort(new Error('Another tab changed the saved project. Reload saved project, then save your current inputs again.'));return;}
          const record={revision:expectedRevision+1,project:clean};store.put(previous??{revision:0,project:emptyProject()},'previous');store.put(record,'current');set(record);
        };});},
        undo:async(expectedRevision,verify=validateProject)=>{
          // WebCrypto verification must finish before the write transaction;
          // awaiting it inside IndexedDB would allow the transaction to close.
          const previous=await transaction(false,(store,set)=>{const r=store.get('previous');r.onsuccess=()=>set(r.result);});
          if(!previous)throw new Error('No previous saved project is available.');
          const clean=await verify(previous.project);
          return transaction(true,(store,set,abort)=>{const r=store.get('current');r.onsuccess=()=>{
          if((r.result?.revision??0)!==expectedRevision){abort(new Error('Another tab changed the saved project. Reload it before undoing.'));return;}
          const record={revision:expectedRevision+1,project:clean};store.put(r.result,'previous');store.put(record,'current');set(record);
        };});},close:()=>db.close()});
    };
  });
}
