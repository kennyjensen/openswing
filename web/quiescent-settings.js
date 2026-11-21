export const isQuiescentResult=result=>result?.fluid?.kind==='quiescent'||result?.base?.fluid?.kind==='quiescent';
export const hasQuiescentEquilibrium=data=>isQuiescentResult(data)||data?.identity?.quiescent_density!=null||data?.launch?.quiescent_density!=null;
export function quiescentCondition({density,position_earth,attitude,gravity_magnitude=null,body_added_mass_factor}){
  if(typeof density!=='number'||!Number.isFinite(density)||density<=0)throw new Error('Enter a positive finite still-air density in input M/L³ units.');
  for(const [name,value] of Object.entries({position_earth,attitude}))if(!Array.isArray(value)||value.length!==3||!value.every(Number.isFinite))throw new Error(`Enter three finite values for ${name==='attitude'?'aircraft attitude':'Earth position'}.`);
  if(gravity_magnitude!==null&&(!Number.isFinite(gravity_magnitude)||gravity_magnitude<0))throw new Error('Enter a nonnegative finite gravity magnitude.');
  // Deliberately construct a fresh condition. Saved ordinary flight controls,
  // wind angles, motion, gust, ground, wake and trim settings cannot enter it.
  const result={speed:0,density,position_earth:[...position_earth],attitude:[...attitude],gravity_magnitude};
  if(body_added_mass_factor!==undefined){
    if(![1,2].includes(body_added_mass_factor))throw new Error('Choose cylinder or printed ASWING fuselage apparent mass.');
    result.body_added_mass_factor=body_added_mass_factor;
  }
  return result;
}
