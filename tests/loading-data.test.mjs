import test from 'node:test';
import assert from 'node:assert/strict';
import {loadingValue,loadingQuantities} from '../web/loading-data.js';
import {distributionHistory,historyCSV,stripColumns} from '../web/distribution-history.js';

test('local Mach is dimensionless while raw velocity follows the input time and length units',()=>{
  const row=Object.freeze({lifting:true,normal_mach:.8,normal_speed:272,relative_velocity:[15,-2,270],force:[0,0,8],length:2});
  assert.equal(loadingValue(row,'normal_mach'),.8);assert.equal(loadingValue(row,'normal_speed'),272);
  assert.equal(loadingValue(row,'vy'),-2);assert.equal(loadingValue(row,'fz'),4);
  assert.equal(loadingQuantities.normal_mach.unit,'Mach');assert.equal(loadingQuantities.vz.unit,'input L/T');
});
test('older archives and body sections leave missing surface airflow as gaps',()=>{
  for(const q of ['normal_mach','normal_speed','vx','vy','vz']){
    assert.equal(loadingValue({lifting:true},q),null);
    assert.equal(loadingValue({lifting:false,normal_mach:0,normal_speed:0,relative_velocity:[0,0,0]},q),null);
  }
  assert.equal(loadingValue({normal_mach:0},'normal_mach'),0);
  assert.equal(loadingValue({normal_mach:NaN},'normal_mach'),null);
  assert.equal(loadingValue({normal_mach:'0'},'normal_mach'),null);
  assert.equal(loadingValue({force:[0,0,3],length:0},'fz'),null);
});
test('airflow histories retain missing samples and export physical sample locations and units',()=>{
  const snapshots=[{time:0,strips:[{beam:1,t:.8,lifting:true}]},
    {time:.1,strips:[{beam:1,t:.8,lifting:true,normal_mach:.6,normal_speed:204,relative_velocity:[30,0,202],velocity_position:[.3,.8,0]}]}];
  const history=distributionHistory(snapshots,'strips',1,row=>loadingValue(row,'normal_mach'));
  assert.equal(history.missing,1);assert.equal(history.stations[0].count,1);assert.equal(history.peak.time,.1);
  const csv=historyCSV(snapshots,'strips',stripColumns);
  for(const label of ['force_point_x [L]','V_relative_z [L/T]','V_normal [L/T]','Mach_normal'])assert.ok(csv.includes('"'+label+'"'));
  assert.ok(!csv.includes('undefined')&&!csv.includes('NaN'));
});

test('derived section outputs retain raw load units and convert only the displayed incidence measure',()=>{
  const row={lifting:true,cm:-.04,f_aero:12,f_reac:-8,da_eff:.2};
  assert.equal(loadingValue(row,'cm'),-.04);assert.equal(loadingValue(row,'f_aero'),12);
  assert.equal(loadingValue(row,'f_reac'),-8);assert.ok(Math.abs(loadingValue(row,'da_eff')-.2*180/Math.PI)<1e-12);
  for(const key of ['cm','f_aero','f_reac','da_eff']){
    assert.equal(loadingValue({},key),null);
    assert.equal(loadingValue({...row,lifting:false},key),null);
  }
  const snapshots=[{time:0,strips:[{beam:1,t:0,...row}]},{time:.1,strips:[{beam:1,t:0,lifting:true,da_eff:null}]}];
  const history=distributionHistory(snapshots,'strips',1,r=>loadingValue(r,'da_eff'));
  assert.equal(history.missing,1);assert.ok(Math.abs(history.stations[0].min.value-.2*180/Math.PI)<1e-12);
  const csv=historyCSV(snapshots,'strips',stripColumns);
  for(const heading of ['cm_quarter_chord','f_aero [F/L]','f_reac [F/L]','da_eff [rad]'])assert.ok(csv.includes('"'+heading+'"'));
  assert.ok(csv.includes('"-0.04","12","-8","0.2"')); // Raw CSV keeps radians.
});
