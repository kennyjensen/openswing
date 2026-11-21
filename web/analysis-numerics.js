// App defaults follow the documented ASWING beam formulation.
// Historical numerical identities remain in saved configurations and results.
export function analysisStructuralSelection(mode,{vacuum=false,stillAir=false,frame='fixed'}={}){
  if(mode==='rigid')return 'midpoint'; // No structural equations in this analysis.
  if(mode==='structural')return 'aswing-section';
  if(mode==='mounted')return 'aswing-airflow';
  if(!['modes','frequency','time'].includes(mode))throw new Error('Unknown analysis type.');
  if(vacuum&&stillAir)throw new Error('Choose either vacuum or still air.');
  if(stillAir){
    if(mode==='time')throw new Error('Still-air nonlinear time response is not available. Select airflow or vacuum in the eigenmode settings first.');
    return 'aswing-still-air';
  }
  if(vacuum)return mode==='time'||frame!=='fixed'?'aswing-moving-vacuum':'aswing-vacuum';
  return 'aswing-airflow';
}
