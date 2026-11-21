// Explicit reconstruction used in the current SA-12 pilot, not recovered
// historical ASWING settings. Loading geometry alone does not apply this.
export const sa12Examples=Object.freeze({
  'isae-sa12-plain-wing':Object.freeze({alpha:8}),
  'isae-sa12-slotted-flap':Object.freeze({alpha:0}),
});
export const isSA12Example=key=>Object.hasOwn(sa12Examples,key);

export function sa12BaselineConfiguration(configuration,key) {
  if(!isSA12Example(key)||configuration.filename!==`${key}.asw`)
    throw new Error('Load an original SA-12 example before applying its baseline.');
  const next=structuredClone(configuration),alpha=String(sa12Examples[key].alpha);
  // The omitted numerical policy is natural-v1/midpoint-v1. Rigid flow does
  // not use the structural operator. A scalar mesh selects ordinary cosine
  // spacing and discards any preceding per-beam overrides.
  delete next.numerics;
  next.mesh=100;
  Object.assign(next.fields,{
    mode:'rigid',speed:'35.76',alpha,beta:'0',stall:true,
    'stall-factor':'40','stall-width':'0.05','freeze-influences':false,
    'aero-lag':true,'wake-core-ratio':'0.25','fourier-wake-diagnostic':false,
    'density-mode':'custom',density:'1.2256','mach-mode':'fixed','pg-mach':'0',
    altitude:'0','altitude-unit':'1000','gravity-mode':'file','load-factor':'1',
    'ground-effect':'1','ground-normal-x':'0','ground-normal-y':'0','ground-normal-z':'1',
    'position-earth-x':'0','position-earth-y':'0','position-earth-z':'0.127',
    'attitude-bank':'0','attitude-elevation':alpha,'attitude-heading':'0',
    'gust-kind':'none','body-added-mass':'1','sensor-flow':'full',
    'derivatives-enable':false,'feedback-enabled':false,
  });
  for(const key of ['rates','acceleration','angular_acceleration'])
    for(const axis of ['x','y','z'])next.fields[`${key}-${axis}`]='0';
  for(const name of ['controls','powers','circulation'])
    for(const key of Object.keys(next[name]))next[name][key]='0';
  next.constraints=[];
  next.derivative_parameters=[];
  next.equilibrium={state:null,enabled:false,label:''};
  return next;
}
