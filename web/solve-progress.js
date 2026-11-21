// Track every assembly start in the worker, before throttling its messages.
export function progressBoundary(stage, current, total, previousStage) {
  return stage !== previousStage || stage === 'static_load' || stage === 'time_step' || stage === 'time_retry'
    || (['static_tangent', 'time_tangent', 'time_rank', 'equilibrium_tangent', 'equilibrium_rank',
      'equilibrium_iteration_tangent', 'equilibrium_final_tangent', 'linearizing', 'inertia', 'frequency'].includes(stage)
      && (current === 0 || current === total));
}

export function mountedProgress() {
  let load = null, update = 0;
  return (stage, current, total) => {
    if (stage === 'static_load') { load = current / total; update = 0; }
    if (stage === 'static_tangent' && current === 0) update++;
    return { load, update };
  };
}

export function mountedStatus(data) {
  if (data.stage === 'equilibrium_iteration') return {
    message: `Correcting saved equilibrium · iteration ${data.time + 1} · residual ${Number(data.steps).toExponential(2)}…`,
    detail: 'Balancing the full equations from the saved state. Iterations and residuals describe the current correction, not overall completion.',
  };
  if (data.stage === 'equilibrium_iteration_tangent') return {
    message: data.time === data.steps ? 'Correcting saved equilibrium · solving equations…'
      : `Correcting saved equilibrium · assembling ${data.time}/${data.steps} columns…`,
    detail: 'Building a matrix for the current correction. This count restarts when the matrix is rebuilt; final equilibrium checks follow.',
  };
  if (data.stage === 'equilibrium_final_tangent') return {
    message: `Preparing final equilibrium check · ${data.time}/${data.steps} columns…`,
    detail: 'Assembling derivatives at the corrected state. The constraint check follows; this column count is not overall completion.',
  };
  if (data.stage === 'equilibrium_tangent') return {
    message: `Preparing final equilibrium check · ${data.time}/${data.steps} columns…`,
    detail: 'Assembling derivatives at the corrected state. The column count describes this check, not overall solve completion.',
  };
  if (data.stage === 'equilibrium_rank') return {
    message: `Checking equilibrium equations · ${data.time}/${data.steps} columns…`,
    detail: 'Checking constraint independence at the corrected state. The column count describes this check, not overall solve completion.',
  };
  if (data.stage === 'equilibrium_rank_svd') return {
    message: 'Completing the full equilibrium check…',
    detail: 'Checking constraint independence with the full matrix. The result is accepted only after this check passes.',
  };
  if (!['static_load', 'static_tangent'].includes(data.stage)) return null;
  if (data.load == null || data.load === 0) {
    if(data.stage==='static_tangent')return {
      message:data.time===data.steps?'Checking initial constraint independence…'
        :`Preparing equilibrium · assembling ${data.time}/${data.steps} columns…`,
      detail:'Building the initial matrix before applying loads. The column count describes this matrix, not overall solve completion.',
    };
    return { message: 'Checking model constraints…', detail: 'Preparing the coupled aerodynamic and structural solve.' };
  }
  const load = Math.round(100 * data.load);
  const prefix = `Balancing forces · applied load ${load}%`;
  const update = data.update ? ` · update ${data.update}` : '';
  const stage = data.stage === 'static_tangent'
    ? data.time === data.steps ? ' · solving equations…' : ` · assembling ${Math.round(100 * data.time / data.steps)}%…`
    : '…';
  return {
    message: prefix + update + stage,
    detail: 'Forces are applied gradually. Each update balances aerodynamic loads and wing deformation; the assembly percentage restarts for each update. Applied load is not overall completion.',
  };
}

export function timeProgress() {
  let accepted = 0, target = 0, update = 0;
  return (stage, current, total) => {
    if (stage == null) accepted = current;
    if (stage === 'time_step') { target = total; update = 0; }
    if (stage === 'time_tangent' && current === 0) update++;
    return { acceptedTime: accepted, targetTime: target, timeUpdate: update };
  };
}

export function timeStatus(data) {
  if (!['time', 'launch_time', 'resume_time'].includes(data.action)) return null;
  if (data.stage === 'time_reporting') return {
    message: 'Time integration finished · preparing plots and checkpoints…',
    detail: `Transferring ${data.steps} computed snapshots. Every accepted state and its restart history are retained.`,
  };
  const starting = mountedStatus(data);
  if (starting) return {
    message: `Finding starting equilibrium · ${starting.message}`,
    detail: 'Time integration begins after the initial forces balance. ' + starting.detail,
  };
  if (!data.stage?.startsWith('time_')) return null;
  const target = Number(data.targetTime).toPrecision(5);
  const detail = `Accepted through t = ${Number(data.acceptedTime).toPrecision(5)} T. Trial solves and retries do not advance the accepted response.`;
  if (data.stage === 'time_retry') return {
    message: `Retrying time step · Δt = ${data.steps.toPrecision(4)} T…`, detail,
  };
  if (data.stage === 'time_tangent' || data.stage === 'time_rank') {
    const label = data.stage === 'time_rank' ? 'checking constraint independence' : `matrix update ${data.timeUpdate}`;
    const part = data.time === data.steps ? 'solving equations' : `assembling ${Math.round(100 * data.time / data.steps)}%`;
    return { message: `Solving t = ${target} T · ${label} · ${part}…`, detail };
  }
  if (data.stage === 'time_iteration') return {
    message: `Solving t = ${target} T · iteration ${data.time + 1} · residual ${data.steps.toExponential(2)}…`, detail,
  };
  return { message: `Advancing to t = ${target} T…`, detail };
}

export function frequencyStatus(data) {
  if (!['frequency','extend_frequency'].includes(data.action)) return null;
  const stages={
    base:['Bode · finding loaded equilibrium…','Balancing the aircraft before computing its small-disturbance response.'],
    equilibrium_tangent:[`Bode · checking equilibrium and retaining derivatives · ${data.time}/${data.steps} columns…`,'These final-state derivatives also form the equilibrium block of the response model.'],
    equilibrium_rank:[`Bode · checking constraint independence · ${data.time}/${data.steps} columns…`,'Checking that the corrected equilibrium supports a unique small-disturbance response.'],
    equilibrium_rank_svd:['Bode · completing the full constraint check…','Checking the corrected equilibrium with the full constraint test and existing acceptance threshold.'],
    equilibrium_reuse:[`Bode · reusing ${data.time} equilibrium derivative columns…`,'Building the remaining velocity and inertia terms from the same loaded state.'],
    matrix_reuse:['Bode · reusing loaded equilibrium and response matrices…','The aircraft, operating conditions, constraints and derivative settings match the loaded model. Computing the requested inputs and frequencies.'],
    linearizing:[`Bode · building response model · ${data.time}/${data.steps} columns…`,'Computing aerodynamic and structural derivatives about the loaded aircraft. This model is reused for every frequency.'],
    inertia:[`Bode · computing inertia and damping · ${data.time}/${data.steps} columns…`,'Retaining structural inertia, apparent mass and rate-dependent loads in the response model.'],
    frequency_structure:['Bode · preparing reusable beam factors…','Preparing the fixed beam equations once for this response model. All aircraft states are recovered at every frequency.'],
    frequency:[`Bode · ${data.time}/${data.steps} frequencies completed…`,'Solving all selected input channels and recovering physical outputs at each frequency.'],
    reporting:['Bode · preparing plots and output…','The frequency solves are finished. Transferring the response to the workbench.'],
  };
  const stage=stages[data.stage];
  if(stage) return {message:stage[0],detail:stage[1]};
  const base=mountedStatus(data);
  return base ? {message:`Bode · finding loaded equilibrium · ${base.message}`,detail:base.detail} : null;
}
