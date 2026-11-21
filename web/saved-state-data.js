// Syntax checks only. The numerical core owns model, branch and residual checks.
const plain=x=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.getPrototypeOf(x)===Object.prototype;
const fail=message=>{throw new Error(message);};
const supported=value=>Number.isInteger(value)&&[1,2].includes(value);
// Trajectories share identical wire values. A standalone, editable checkpoint
// owns each occurrence separately, including its accepted endpoint evidence.
// Unlike JSON stringify/parse, this also preserves signed zero in memory.
const copyTree=value=>value===null||typeof value!=='object'?value:Array.isArray(value)
  ?value.map(copyTree):Object.fromEntries(Object.entries(value).map(([key,item])=>[key,copyTree(item)]));

function jointIds(identity){
  if(!plain(identity)||!Array.isArray(identity.constraints))fail('Version-2 hinge state needs its constraint identity.');
  const ids=[];let row=0;
  for(const constraint of identity.constraints){
    if(constraint?.kind==='joint'){row++;if(constraint.type===3)ids.push(row);}
  }
  if(!ids.length)fail('Version-2 hinge state needs a type-3 Joint identity.');
  return ids;
}

function hingeRows(rows,ids,label){
  if(!Array.isArray(rows)||rows.length!==ids.length)fail(`Invalid ${label} hinge chart count.`);
  const seen=new Set();
  rows.forEach((row,index)=>{
    if(!plain(row)||Object.keys(row).length!==2||!Object.hasOwn(row,'joint')||!Object.hasOwn(row,'angle_rad')||
      !Number.isSafeInteger(row.joint)||row.joint<1||seen.has(row.joint)||row.joint!==ids[index]||!Number.isFinite(row.angle_rad))
      fail(`Invalid ${label} hinge chart joint or finite angle_rad.`);
    seen.add(row.joint);
  });
}

export function validateEquilibriumPacket(seed){
  if(!plain(seed)||seed.format!=='openswing-equilibrium'||!supported(seed.version)||!Array.isArray(seed.positions))
    fail('Load a version-1 or version-2 OpenSwing equilibrium JSON or an analysis containing one.');
  if(seed.version===2)hingeRows(seed.hinge_charts,jointIds(seed.identity),'equilibrium');
  // Old hinge reconstruction/rejection belongs to the core. Never add a turn.
  return structuredClone(seed);
}

export function validateCheckpointPacket(data){
  if(!plain(data)||data.format!=='openswing-time-checkpoint'||!supported(data.version)||
      !Number.isFinite(data.state?.time)||!plain(data.context?.method))
    fail('Load a version-1 or version-2 OpenSwing time checkpoint or a time result containing checkpoints.');
  if(data.version===2){
    const ids=jointIds(data.context.identity);
    const state=(value,label)=>{
      if(!plain(value)||!Number.isFinite(value.time)||!plain(value.network)||value.network.version!==2||!Array.isArray(value.network.positions))
        fail(`Invalid version-2 ${label} physical state.`);
      hingeRows(value.network.hinge_charts,ids,label);
    };
    const options=value=>{
      if(!plain(value)||!Array.isArray(value.hinge_charts)||value.hinge_charts.length!==ids.length||!value.hinge_charts.every(Number.isFinite))
        fail('Invalid checkpoint option hinge chart references.');
      // Fixed residual reference charts may differ from actual endpoint angles.
    };
    state(data.state,'current');if(data.older!=null)state(data.older,'older');options(data.options);
    // Accepted-method seeds, predecessors and endpoints each own their charts.
    // Preserve unknown metadata; inspect declared network states/options only.
    const pending=data.accepted_method==null?[]:[[data.accepted_method,0]];let count=0;
    while(pending.length){
      const [value,depth]=pending.pop();
      if(++count>2000000||depth>80)fail('Checkpoint accepted method is too large or deeply nested.');
      if(value===null||typeof value!=='object')continue;
      if(plain(value)&&Object.hasOwn(value,'network'))state(value,'accepted-method');
      if(plain(value)&&Object.hasOwn(value,'options'))options(value.options);
      for(const child of Object.values(value))pending.push([child,depth+1]);
    }
  }
  return copyTree(data);
}

export function checkpointRecord(record,context){
  if(!plain(record))fail('The selected result has no time checkpoint. Run a new time analysis.');
  return validateCheckpointPacket({format:'openswing-time-checkpoint',context,...record,version:record.version??1});
}
