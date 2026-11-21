"""Durable actual-Pyodide seeded-corrector regression using shared saved baseline."""
import copy,json,sys,time,traceback
from pathlib import Path
import numpy as np
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork,equilibrate,network_result
from openswing.equilibrium_state import capture,restore
from openswing.time_state import portable
import openswing.seeded_corrector as corrector
from openswing.harmonic_structure import StructureUnavailable

reference=json.loads(Path('/test-data/seeded-corrector-reference.json').read_text())
model_text=Path('/test-data/seeded-corrector-flexible.asw').read_text()
report=dict(status='RUNNING',checks=[],cases={},comparisons={},operations=dict(network_constructions=0,equilibrium_calls=0,fresh_residual_calls=0,result_evaluations=0,injected_unavailable_calls=0,derivative_calls=0),limitations=['Small actual-Pyodide compatibility regression, not mesh convergence or experimental validation.','Uses a previously completed baseline seed/target; no baseline or cold solve is repeated.','Reported timings are diagnostics, not a controlled speedup claim.'])

def check(name,predicate,**details):
    report['checks'].append(dict(check=name,pass_=bool(predicate),**details))
    if not predicate:raise AssertionError(name)

def normalized(value):return json.loads(json.dumps(portable(value),allow_nan=False))

def condition():
    data=copy.deepcopy(reference['target']['state']['launch']['condition'])
    for name in ['controls','powers']:data[name]={int(k):v for k,v in data[name].items()}
    return FlightCondition(**data)

def compare(label,actual,expected,start):
    excluded={'result.evaluations','result.circulation_solver.evaluations'}
    stats=dict(numeric_values=0,leaf_values=0,maximum_fraction=0.,worst_path=None)
    report['comparisons'][label]=stats
    def visit(a,b,path):
        if path in excluded:return
        if isinstance(b,bool) or b is None or isinstance(b,str):
            stats['leaf_values']+=1
            if a!=b:raise AssertionError(label+' metadata '+path)
        elif isinstance(b,(int,float)):
            if not isinstance(a,(int,float)) or not np.isfinite(a) or not np.isfinite(b):raise AssertionError(label+' nonfinite '+path)
            error=abs(a-b);limit=2e-8+2e-8*abs(b);fraction=error/limit
            stats['numeric_values']+=1;stats['leaf_values']+=1
            if fraction>stats['maximum_fraction']:stats.update(maximum_fraction=fraction,worst_path=path,difference=error,limit=limit)
            if fraction>1:raise AssertionError(f'{label}: {path}: {error} > {limit}')
        elif isinstance(b,list):
            if not isinstance(a,list) or len(a)!=len(b):raise AssertionError(label+' shape '+path)
            for i,(x,y) in enumerate(zip(a,b)):visit(x,y,path+f'[{i}]')
        elif isinstance(b,dict):
            if not isinstance(a,dict) or a.keys()!=b.keys():raise AssertionError(label+' keys '+path)
            for key in b:visit(a[key],b[key],path+'.'+key)
        else:raise TypeError(path+' '+type(b).__name__)
    visit(actual,expected,start);check(label,True,**stats)

try:
    check('Original physical gates retained',reference['gates']==dict(absolute=2e-8,relative=2e-8,full_residual=1e-8,dense_column_scaled_rcond=1e-10))
    check('Declared baseline fixture and target',reference['fixture']==dict(panels=4,speed=20,seed_alpha=2,target_alpha=2.05,mach=.1,beta=0,gravity_body=[0,0,0],freeze_influences=False))
    seed=copy.deepcopy(reference['seed']['state']);seed_before=json.dumps(seed,sort_keys=True,allow_nan=False)
    for label,injected in [('structured',False),('unavailable-factor-fallback',True)]:
        row=dict(status='RUNNING');report['cases'][label]=row
        report['operations']['network_constructions']+=1
        n=StaticNetwork(parse_asw(model_text),4,condition(),[0,0,0],())
        check(label+' exact eligible native instance',type(n) is StaticNetwork)
        factory=corrector.NewtonBeamFactor;injections=[]
        if injected:
            def unavailable(*args,**kwargs):
                injections.append(True);report['operations']['injected_unavailable_calls']+=1
                raise StructureUnavailable('Deliberate WASM factor unavailability; retain dense recovery')
            corrector.NewtonBeamFactor=unavailable
        before=time.perf_counter();nfev=n.nfev
        try:
            report['operations']['equilibrium_calls']+=1
            x,steps=equilibrate(n,tolerance=1e-9,initial_state=copy.deepcopy(seed))
        finally:
            corrector.NewtonBeamFactor=factory
            row['factor_factory_restored']=corrector.NewtonBeamFactor is factory
            row['partial_diagnostics']=normalized(getattr(n,'_seeded_corrector_diagnostics',None))
        row.update(equilibrium_seconds=time.perf_counter()-before,equilibrium_residual_calls=n.nfev-nfev,steps=steps,unknowns=x.tolist(),diagnostics=normalized(n.equilibrium_diagnostics))
        report['operations']['result_evaluations']+=1
        result=normalized(network_result(n,x));state=normalized(capture(n,x,residual=result['residual']))
        row.update(result=result,state=state)
        report['operations']['network_constructions']+=1
        fresh=StaticNetwork(parse_asw(model_text),4,condition(),[0,0,0],())
        fresh_x=restore(fresh,state);report['operations']['fresh_residual_calls']+=1
        residual=fresh.residual(fresh_x)
        row.update(fresh_unknowns=fresh_x.tolist(),fresh_residual=residual.tolist(),fresh_residual_norm=float(np.max(abs(residual))))
        diag=row['diagnostics'];observed=diag['seeded_corrector']
        check(label+' full residual gates',np.isfinite(residual).all() and max(result['residual'],state['residual'],diag['residual'],row['fresh_residual_norm'])<=1e-8)
        check(label+' sparse final rank certificate at unchanged threshold',diag['rank_check']=='sparse inverse-norm certificate' and diag['column_scaled_reciprocal_condition'] is None and np.isfinite(diag['column_scaled_reciprocal_condition_lower_bound']) and diag['column_scaled_reciprocal_condition_lower_bound']>reference['gates']['dense_column_scaled_rcond'])
        check(label+' one warm corrected step',steps==1 and diag['initialization']=='saved physical equilibrium')
        check(label+' eligible sparse path activated',observed['eligible'] and observed['enabled'] and observed['decline_reasons']==[])
        check(label+' factor owners released',observed['builder_detached'] and observed['factor_wrappers_alive_before_final_tangent']==0 and n.iteration_fields is None and n.tangent_influences is None and n._tangent_loads is None)
        check(label+' fresh sparse matrix and original rank threshold declared',observed['final_tangent_values_unchanged'] is True and observed['rank_acceptance_threshold_unchanged'] is True and observed['final_tangent_storage']=='sparse' and observed['final_rank_strategy']=='conservative certificate with full SVD fallback')
        check(label+' every temporary build owner restored',all(b['tangent_owner_restored'] and b['iteration_fields_unchanged'] and b['tangent_load_owner_restored'] for b in observed['builds']))
        check(label+' full final tangent and rank completed',observed['phases']['final_tangent']['status']==observed['phases']['final_rank']['status']=='COMPLETED')
        if injected:
            check(label+' exactly1unavailable failure then dense recovery',len(injections)==1 and len(observed['builds'])==1 and observed['builds'][0]['status']=='BUILD_EXCEPTION' and observed['builds'][0]['exception_type']=='StructureUnavailable' and observed['dense_tangent_builds']>=1 and row['factor_factory_restored'])
        else:
            check(label+' actual sparse factor solve',any(b['status']=='BUILT' and b['solve_completions']>0 for b in observed['builds']) and observed['dense_tangent_builds']==0)
        compare(label+' complete physical outputs',result,reference['target']['result'],'result')
        compare(label+' complete physical saved state',state,reference['target']['state'],'state')
        row['status']='PASS'
    check('Shared original seed unchanged',json.dumps(seed,sort_keys=True,allow_nan=False)==seed_before)
    check('Only prescribed two warm solves and four networks',report['operations']==dict(network_constructions=4,equilibrium_calls=2,fresh_residual_calls=2,result_evaluations=2,injected_unavailable_calls=1,derivative_calls=0))
    paths={name:getattr(module,'__file__',None) for name,module in sys.modules.items() if name=='openswing' or name.startswith('openswing.')}
    report['source_origins']=paths
    check('Every imported solver module owned by mounted source',all(p and p.startswith('/home/pyodide/openswing/') for p in paths.values()))
    report['status']='PASS_SEEDED_CORRECTOR_WASM'
except BaseException as error:
    report['status']='FAIL_SEEDED_CORRECTOR_WASM_RETAINED'
    report['error']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
report['counts']=dict(passed=sum(row['pass_'] for row in report['checks']),total=len(report['checks']))
Path('/test-data/result.json').write_text(json.dumps(report,allow_nan=False,indent=2)+'\n')
