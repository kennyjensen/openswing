// The saved transfer is per input time. A playback clock changes phase only;
// it never changes the solved response or normalizes its physical amplitude.
const seconds=model=>model?.units?.T?.[0]===1&&['s','sec','second','seconds'].includes(String(model.units.T[1]).toLowerCase());
const number=value=>Number(value.toPrecision(6)).toString();

export const frequencyCycleUnit=model=>!model||seconds(model)?'Hz':'cycles/input T';

export function frequencySampleLabel(omega,units='cycles',model){
  const cycles=`${number(omega/(2*Math.PI))} ${seconds(model)?'Hz':'cycles/T'}`;
  const radians=`${number(omega)} ${seconds(model)?'rad/s':'rad/T'}`;
  return units==='radians'?`${radians} · ${cycles}`:`${cycles} · ${radians}`;
}

export function frequencyPlaybackPhase(startDegrees,elapsedMs,omega,clock='model'){
  const rate=clock==='inspection'?360/4000:omega*180/Math.PI/1000;
  return ((startDegrees+Math.max(0,elapsedMs)*rate)%360+360)%360;
}

export function frequencyPlaybackNote(omega,clock='model',model){
  if(clock==='inspection')return 'Phase inspection: every frequency plays in 4 seconds per cycle. Visible turning speed is not the physical angular rate shown in the Bode plot.';
  if(omega===0)return 'Zero-frequency response: static in model time.';
  const time=seconds(model)?'Real-time playback':'Model-time playback: 1 input T per wall-clock second';
  const period=number(2*Math.PI/omega);
  return `${time} · ${period} ${period==='1'?'second':'seconds'} per cycle. Input amplitude scales the motion; Bode magnitudes remain per unit input.`;
}

export function frequencyMotionSummary(output,amplitude=1,units='degrees',model){
  const rate=output?.frame?.rates_body,angle=output?.frame?.attitude_rad;
  const values=[rate?.real?.[2],rate?.imag?.[2],angle?.real?.[2],angle?.imag?.[2]];
  if(!Number.isFinite(amplitude)||amplitude<0||!values.every(Number.isFinite))return '';
  const scale=amplitude*(units==='radians'?1:180/Math.PI),unit=units==='radians'?'rad':'°';
  const yaw=scale*Math.hypot(values[0],values[1]),heading=scale*Math.hypot(values[2],values[3]);
  return `Aircraft-frame amplitudes at input ×${number(amplitude)}: body yaw rate ${number(yaw)} ${unit}/${seconds(model)?'s':'T'} · heading angle ${number(heading)} ${unit}.`;
}
