import {readFile,writeFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {frequencySeries,comparisonCSV} from '../web/frequency-data.js';
import {comparisonGroups,comparisonFigure} from '../web/frequency-comparison.js';
const sha=data=>createHash('sha256').update(data).digest('hex');
const studyFile='docs/validation/frequency-refinement.json',bytes=await readFile(studyFile),study=JSON.parse(bytes);
for(const [file,hash] of Object.entries(study.source_sha256))if(sha(await readFile(file))!==hash)throw new Error('Numerical reference source changed: '+file);
const result=study.cases.find(c=>c.specification.name==='gust_phase').result.result,before=JSON.stringify(result);
const traces=['force','moment'].flatMap(key=>result.inputs.map(c=>({inputName:c.name,display:'response',group:'global',key,component:key==='force'?2:0,station:null})));
let checked=0,maxError=0;
for(const s of traces){const input=result.inputs.find(c=>c.name===s.inputName),factor=2.45*(input.symmetry==='cosine'?Math.cos(Math.PI*.6):Math.sin(Math.PI*.6))*(s.key==='moment'?.6:1);
  for(const v of frequencySeries(result,s)){for(const [a,b] of [[v.real,factor*Math.cos(-v.omega*.12)],[v.imag,factor*Math.sin(-v.omega*.12)]]){const error=Math.abs(a-b)/Math.max(1,Math.abs(b));maxError=Math.max(maxError,error);checked++;if(error>1e-8)throw new Error('Analytical gust reference failed.');}}
}
const groups=comparisonGroups(result,traces);if(groups.length!==2||groups.some(g=>g.traces.length!==2))throw new Error('Force and moment groups were mixed.');
const svg=comparisonFigure(groups[0]),csv=comparisonCSV(result,traces);if(JSON.stringify(result)!==before)throw new Error('Report mutated.');
const artifacts={'docs/validation/frequency-comparison.svg':svg,'docs/validation/frequency-comparison.csv':csv};
for(const [file,data] of Object.entries(artifacts))await writeFile(file,data);
const files=[...Object.keys(study.source_sha256),studyFile,'scripts/verify-frequency-comparison.mjs','tests/frequency-comparison.test.mjs','tests/browser/frequency-comparison.spec.js','tests/browser/broken-loop.spec.js','examples/gust-modes.asw',...(await readdir('web')).filter(n=>/\.(js|css)$/.test(n)).map(n=>'web/'+n)];
const source_sha256=Object.fromEntries(await Promise.all(files.map(async file=>[file,sha(await readFile(file))])));
const report={description:'Browser comparison extraction and standalone figures from the unchanged source-hashed native gust response, checked against independent offset-point force/moment formulas. This is a display/export check, not another numerical-kernel solve.',source_sha256,reference_series_source:studyFile,independent_scalar_force_moment_components:checked,maximum_scaled_reference_error:maxError,axis_groups:groups.length,independent_traces:traces.length,frequencies:result.samples.map(s=>s.omega),csv_data_rows:csv.trim().split('\n').length-1,report_unchanged:true,artifact_sha256:Object.fromEntries(Object.entries(artifacts).map(([file,data])=>[file,sha(data)]))};
await writeFile('docs/validation/frequency-comparison.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({checked,maxError,axis_groups:groups.length,source_hashes:files.length,csv_data_rows:report.csv_data_rows}));
