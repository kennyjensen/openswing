import preset from './daedalus-mesh.json' with {type:'json'};

// Approximate the drawing density in Drela's rudder GIF. These counts are
// presentation-driven starting settings, not recovered native NODE settings
// or a convergence claim. Required stations remain the mesher's responsibility.
export function isDaedalusSource(source) {
  if(typeof source!=='string')return false;
  const lines=source.split(/\r?\n/).map(line=>line.split(/[#!]/,1)[0].trim().toLowerCase()).filter(Boolean);
  const name=lines.indexOf('name');
  if(name<0||lines[name+1]!=='daedalus hpa'||lines[name+2]!=='end')return false;
  const beams=lines.flatMap((line,i)=>{
    const match=/^beam\s+(\d+)$/.exec(line);
    return match?[[Number(match[1]),lines[i+1]]]:[];
  });
  return JSON.stringify(beams)===JSON.stringify([[1,'wing'],[2,'stab'],[3,'rudder'],[4,'tailboom'],[5,'fairing']]);
}

export function daedalusDefaultMesh(source) {
  return isDaedalusSource(source)?structuredClone(preset):null;
}

export function daedalusMeshConfiguration(configuration) {
  const mesh=daedalusDefaultMesh(configuration.source);
  if(!mesh)throw new Error('Load the five-beam Daedalus model before applying its default mesh.');
  const next=structuredClone(configuration);
  next.mesh=mesh;
  // A previous trim belongs to its old discretization. Preserve the requested
  // flight/trim settings, but require a fresh solution on the new mesh.
  next.equilibrium={state:null,enabled:false,label:''};
  return next;
}
