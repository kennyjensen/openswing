import assert from 'node:assert/strict';

// Shared by the live UI check and reassessment of its retained, unedited output.
export function checkSourceWallContinuation(request,native,result,messages,audit){
  const check=(name,ok)=>{audit.checks.push({name,passed:!!ok});assert(ok,name);};
  function compare(a,b,p=''){
    if(audit.excluded.includes(p))return;
    if(typeof a==='number'){
      assert.equal(typeof b,'number',p);assert(Number.isFinite(a)&&Number.isFinite(b),p);
      const fraction=Math.abs(a-b)/(audit.absolute+audit.relative*Math.abs(a));
      audit.numeric_comparisons++;audit.maximum_fraction=Math.max(audit.maximum_fraction,fraction);
      assert(fraction<=1,p+' numerical parity');
    }else if(Array.isArray(a)){
      assert(Array.isArray(b)&&a.length===b.length,p);a.forEach((v,i)=>compare(v,b[i],`${p}[${i}]`));
    }else if(a!==null&&typeof a==='object'){
      assert(b!==null&&typeof b==='object',p);
      for(const [key,value] of Object.entries(a)){assert(Object.hasOwn(b,key),p+'.'+key);compare(value,b[key],p?p+'.'+key:key);}
    }else assert.deepEqual(b,a,p);
  }
  check('one actual warm worker solve',messages.length===1);
  // worker.js sends JSON.stringify(request) to Python. An undefined optional
  // JavaScript field is absent from that wire payload, not a changed input.
  assert.deepEqual(JSON.parse(JSON.stringify(messages[0].request)),request);
  check('exact native wire request and preceding state',true);
  assert.deepEqual(result.software_provenance.modules,audit.modules);check('exact current kernel',true);
  compare(native,result);check('complete native physical parity',true);
  const info=result.equilibrium_initialization,corrector=info.seeded_corrector;
  check('saved-state initialization',info.initialization==='saved physical equilibrium');
  check('sparse source corrector enabled',corrector.enabled&&corrector.eligible&&corrector.dense_tangent_builds===0);
  check('complete Newton factors',corrector.builds.length>0&&corrector.builds.every(b=>b.status==='BUILT'&&b.solve_completions>0));
  check('factor owners released',corrector.builder_detached&&corrector.factor_wrappers_alive_before_final_tangent===0);
  check('fresh final tangent and rank',corrector.phases.final_tangent.status==='COMPLETED'&&corrector.phases.final_rank.status==='COMPLETED');
  check('full residual',result.converged&&result.residual<=1e-8&&info.residual<=1e-8);
  check('offline execution',!audit.offline_requests.length&&!audit.external_requests.length);
  check('no page errors',!audit.page_errors.length);
}
