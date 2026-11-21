// Values remain in the ASW input units. Missing historical fields are gaps.
const forceDescription='Strip force divided by strip length. This is an average over the interval, plotted at its reported station; it can differ from the force density evaluated at that station.';
export const loadingQuantities={
  cl:{label:'Section cℓ',title:'Circulatory section lift coefficient',unit:'cℓ',surface:true,path:'cl'},
  cm:{label:'Section cₘ',title:'Local quarter-chord moment coefficient',unit:'cₘ',surface:true,path:'cm',description:'Includes flap mixing and the local Mach correction. Moment arms and apparent-mass moments are excluded.'},
  f_aero:{label:'Normal aerodynamic load',title:'Normal circulatory load per length',unit:'input F/L',surface:true,path:'f_aero',description:'Circulatory lift plus enabled circulation-rate lift, projected on the current section normal. Profile drag and apparent mass are excluded.'},
  f_reac:{label:'Normal inertial load',title:'Normal gravity and inertial load per length',unit:'input F/L',surface:true,path:'f_reac',description:'Distributed mass gravity/inertia plus apparent mass, per current length. Interval averages exclude point masses and support reactions.'},
  da_eff:{label:'Elastic incidence change',title:'Effective incidence change from deformation',unit:'deg',surface:true,path:'da_eff',scale:180/Math.PI,description:'The documented normal-vector change projected on total relative airflow. This linearized measure can differ from an exact angle change; zero-speed samples are unavailable.'},
  fz:{label:'Force z / length',title:'Mean body-axis z force per length',unit:'input F/L',axis:2,description:forceDescription},
  fy:{label:'Force y / length',title:'Mean body-axis y force per length',unit:'input F/L',axis:1,description:forceDescription},
  fx:{label:'Force x / length',title:'Mean body-axis x force per length',unit:'input F/L',axis:0,description:forceDescription},
  normal_mach:{label:'Local normal Mach',title:'Local section-normal Mach',unit:'Mach',surface:true,path:'normal_mach'},
  normal_speed:{label:'Normal relative speed',title:'Section-normal relative speed',unit:'input L/T',surface:true,path:'normal_speed'},
  vx:{label:'Relative velocity x',title:'Body-axis x relative velocity at force points',unit:'input L/T',surface:true,path:'relative_velocity',component:0},
  vy:{label:'Relative velocity y',title:'Body-axis y relative velocity at force points',unit:'input L/T',surface:true,path:'relative_velocity',component:1},
  vz:{label:'Relative velocity z',title:'Body-axis z relative velocity at force points',unit:'input L/T',surface:true,path:'relative_velocity',component:2},
};
export function loadingValue(row,quantity){
  const q=loadingQuantities[quantity];
  if(!q||(q.surface&&row.lifting===false))return null;
  let value;
  if(q.axis!==undefined)value=typeof row.force?.[q.axis]==='number'&&row.length>0?row.force[q.axis]/row.length:null;
  else value=q.component===undefined?row[q.path]:row[q.path]?.[q.component];
  return typeof value==='number'&&Number.isFinite(value)?value*(q.scale??1):null;
}
