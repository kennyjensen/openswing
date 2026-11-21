// Presentation only: recorded response constraints determine the explanation.
const axes=['x','y','z'];
const names=['Roll','Pitch','Yaw'];

export function rateAxis(group,key,component){
  if(group==='operating')return axes.indexOf(/^rates\.([xyz])$/.exec(key??'')?.[1]);
  return group==='frame'&&key==='rates_body'&&Number.isInteger(component)&&component>=0&&component<3?component:-1;
}

export function rateLabel(group,key,component){
  if(group==='nodes'&&key==='rates'&&Number.isInteger(component)&&component>=0&&component<3)
    return `Elastic angular velocity ω_${axes[component]} · body ${axes[component]}`;
  const axis=rateAxis(group,key,component);
  return axis<0?null:`${names[axis]} angular velocity Ω_${axes[axis]} · body ${axes[axis]}`;
}

export function rateDefinition(group,key,component){
  const axis=rateAxis(group,key,component);
  if(axis>=0)return `Ω_${axes[axis]} is the aircraft-frame angular velocity along body ${axes[axis]} (ASWING W${axes[axis]}). The heading-angle derivative and rates transformed into stability axes are different quantities. Structural nodes offer the local elastic rate ω; an attached gyro measures Ω + ω in its sensor axes.`;
  if(group==='nodes'&&key==='rates'&&Number.isInteger(component)&&component>=0&&component<3)
    return `ω_${axes[component]} is the local elastic angular velocity relative to the aircraft frame, resolved along body ${axes[component]}. An attached gyro measures Ω + ω in its sensor axes. Flight frame offers the aircraft angular velocity Ω.`;
  return '';
}

export function frameSettingHelp(frame){
  return {
    fixed:'Aircraft translation and rotation are held fixed. Roll, pitch and yaw-rate responses to controls are zero by this constraint; aerodynamic loads and elastic deformation can still respond. Choose Free flight for aircraft motion.',
    free:'All six aircraft accelerations respond to net loads. Roll, pitch and yaw motion are included. Run analysis to compute this response; choosing the frame does not establish a steady-flight trim.',
    prescribed:'Aircraft accelerations keep their prescribed values. Frame kinematics remain active, but control inputs do not release these acceleration constraints.',
    mixed:'Only accelerations selected as Solve from a net force or moment respond to that load. Other accelerations remain prescribed. Check each translation and rotation axis below.',
  }[frame]??'';
}

export function constrainedRateHelp(result,selection){
  if(!result||selection?.display==='broken_loop')return '';
  const axis=rateAxis(selection?.group,selection?.key,selection?.component);
  if(axis<0)return result.frame_mode==='fixed'&&selection?.group==='frame'
    ? 'Aircraft motion was held fixed in this calculation, so no Flight frame outputs were computed. Other output groups use the saved result immediately. To compute flight motion, choose Free flight under Settings → Response frame and run a new analysis.' : '';
  const rate=`${names[axis].toLowerCase()} rate`;
  if(result.frame_mode==='fixed')return `This result holds aircraft motion fixed, so ${rate} is constrained to zero. This is not a free-flight ${rate} transfer. Use free-flight settings and run a new analysis to compute aircraft motion.`;
  if(result.frame_mode==='prescribed'||(result.frame_mode==='mixed'&&!Object.hasOwn(result.frame_load_targets??{},`moment.${axes[axis]}`)))
    return `This result prescribes ${names[axis].toLowerCase()} acceleration. For a response driven by net ${axes[axis]} moment, use Free flight or solve that rotation axis from its moment in Mixed motion, then run a new analysis.`;
  return '';
}

export function baseMotionNote(result){
  return result?.base?.modal_base?.kinematically_steady===false?
    'Frozen response about an accelerating state; compute a steady trim for a steady-flight Bode comparison.':'';
}

// Read the saved base, not the current input fields or the selected response.
// A converged residual or a free response frame alone does not certify trim.
export function baseConditionSummary(result,model){
  if(!result?.base)return '';
  const base=result.base,motion=base.modal_base;
  const frame=result.frame_mode??motion?.frame;
  let description=frame==='fixed'?'Base motion: held fixed; steady-flight trim is not established.':
    motion?.kinematically_steady===false?'Base motion: accelerating; compute a steady trim for a steady-flight comparison.':
    motion?.kinematically_steady===true?'Base motion: steady in the recorded flight frame.':
    'Base motion: not reported in this result.';
  const unit=key=>{
    const declaration=model?.units?.[key];
    return declaration?.[0]===1&&typeof declaration[1]==='string'&&declaration[1]?declaration[1]:`input ${key}`;
  };
  const number=value=>Number(value.toPrecision(5)).toString();
  const values=[];
  const speed=base.reference_flow?.speed;
  if(Number.isFinite(speed))values.push(`Reference airspeed ${number(speed)} ${unit('L')}/${unit('T')}`);
  const mass=base.mass_properties?.mass,gravity=base.gravity_body;
  const g=Array.isArray(gravity)&&gravity.length===3&&gravity.every(Number.isFinite)?Math.hypot(...gravity):base.atmosphere?.gravity_magnitude;
  if(base.mass_properties?.physical!==false&&Number.isFinite(mass)&&mass>=0&&Number.isFinite(g)&&g>=0)
    values.push(`Weight ${number(mass*g)} ${unit('F')}`);
  if(Number.isFinite(base.earth_state?.flight_path))
    values.push(`Flight path ${Number(base.earth_state.flight_path.toFixed(3))}°`);
  if(values.length)description+=' '+values.join(' · ')+'.';
  return description;
}

export function controlInputLabel(input,model){
  const match=/^control\.(\d+)$/.exec(input?.name??'');
  if(!match)return input?.name??'';
  const property=new RegExp(`^dC[LMD]dF${match[1]}$`);
  const names=[...new Set((model?.distributions??[]).filter(b=>b.properties?.some(k=>property.test(k))).map(b=>b.name).filter(Boolean))];
  return input.name+(names.length?` · ${names.join(', ')}`:'');
}
