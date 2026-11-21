import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
export const sha=b=>createHash('sha256').update(b).digest('hex');
export async function cases(){
 const reports={},studies={};
 for(const name of ['static','zero','modes']){
  const file=`pazy-loaded-${name}.json`,bytes=await readFile('docs/validation/'+file),data=JSON.parse(bytes);
  if(data.status!=='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED')throw Error('Native study incomplete: '+name);
  if(!data.scripts['pazy_primary_conm2.py'])throw Error('Superseded inertia convention');
  reports[file]=sha(bytes);studies[name]=data;
 }
 const selected=[];
 for(const [skin,kind,mass] of [[0,'bending',3.5],[0,'torsion',3.25],[1,'bending',3],[1,'torsion',2.8]]){
  selected.push(studies.static.runs.find(r=>r.specification.skin===skin&&r.specification.kind===kind&&r.specification.mass_kg===mass&&r.specification.refinement===4));
 }
 selected.push(...studies.zero.runs.filter(r=>r.specification.refinement===1));
 selected.push(...studies.modes.runs.filter(r=>r.specification.refinement===4));
 if(selected.length!==10||selected.some(r=>!r||r.status!=='computed'))throw Error('Runtime cases missing or rejected');
 const runs=[];
 for(const row of selected){const bytes=await readFile(row.cache);if(sha(bytes)!==row.sha256)throw Error('Native cache changed');runs.push(JSON.parse(bytes));}
 if(Object.values(studies).some(d=>JSON.stringify(d.modules)!==JSON.stringify(studies.zero.modules)))throw Error('Mixed production modules');
 return {reports,modules:studies.zero.modules,runs,selector_sha256:sha(await readFile(new URL(import.meta.url)))};
}
