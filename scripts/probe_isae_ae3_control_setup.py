"""Separate current AE-3 rigid control, influence and source-input effects.

These prospective diagnostics add no native-reference passes. Each numerical
launch is serial, limited and reaped; all original source bytes are retained.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/ae3-control-setup-20261111'
BASE=ROOT/'artifacts/isae/ae3-current-20261111'
sys.path.insert(0,str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read,write,pin,THREADS
LIMITS=dict(address_space_bytes=512*1024**2,cpu_seconds=15,wall_seconds=25)


def checked():
    plan=read(OUT/'plan.json')
    assert all(pin(p['path'])==p for p in plan['pins']), 'Pinned source or baseline changed.'
    return plan


def prepare():
    assert not OUT.exists()
    base=read(BASE/'plan.json');summary=read(BASE/'assessment.json')
    assert summary['passed']==50 and summary['computed']==72 and summary['physical_passed']==348
    assert all(pin(p['path'])==p for p in base['pins'])
    paths={p['path'] for p in base['pins']}
    paths.update(str(p) for p in (Path(__file__),BASE/'plan.json',BASE/'assessment.json',
        ROOT/'reference/aswing_doc.txt',ROOT/'docs/validation/isae-ae3-clamped-circulation.md'))
    selected=[j for j in base['jobs'] if j['execution_route']=='worker'
              and j['native_operating_point'] in (1,6)]
    original=Path(selected[0]['source']).read_text()
    assert original.count('0.0581')==original.count('-0.0102')==1
    sibling=Path(selected[0]['source']).with_name('Straight_60O.asw')
    sibling_text=sibling.read_text()
    assert '0.0686' in sibling_text and '-0.0102' in sibling_text
    paths.add(str(sibling))
    # Only independently sourced control scale tokens are changed in copies.
    sources=dict(literal=original,report_cm=original.replace('-0.0102','-0.0107'),
                 sibling_lift=original.replace('0.0581','0.0686'))
    for name,source in sources.items():
        target=OUT/'models'/(name+'.asw');target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(source);paths.add(str(target))
    cases=[]
    for job in selected:
        parent=BASE/'jobs'/job['id'];result=read(parent/'strict-result.json')
        assert result['status']=='computed'
        preflight=Path(result['artifact_directory'])/'preflight.json'
        paths.update(str(p) for p in (parent/'strict-result.json',parent/'terminal.json',preflight))
        for variant in (['rigid','frozen','report_cm','sibling_lift'] if job['nominal']==80 else ['rigid']):
            source_name=variant if variant in sources else 'literal'
            name=f"{variant}-op{job['native_operating_point']}-m{job['nominal']}"
            cases.append(dict(name=name,variant=variant,job=job,source=str(OUT/'models'/(source_name+'.asw')),
                baseline_result=str(parent/'strict-result.json'),baseline_preflight=str(preflight),
                control_lift=.0686 if variant=='sibling_lift' else .0581,
                control_moment=-.0107 if variant=='report_cm' else -.0102))
    assert len(cases)==10
    write(OUT/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        previous_goal_turn='progress: adopted exact AE-2 memory recovery and completed the current AE-3 finite-control replay',
        limits=LIMITS,cases=cases,pins=[pin(p) for p in sorted(paths)],primary_votes_added=0,
        method=__doc__,numerical_gates=dict(residual=1e-8,balance=1e-7,parity=2e-10,clamp=1e-10),
        hypotheses=dict(rigid='Same literal model/mesh; solve circulation at undeformed geometry, excluding structural response.',
            frozen='Only freeze_influences changes, to the documented fast option and production default.',
            report_cm='Only dCMdF1 scale changes from literal -0.0102 to Part IV p13 value -0.0107.',
            sibling_lift='Only dCLdF1 scale changes from literal 0.0581 to 0.0686 present in sibling 60O/80O/95O models; not a recovered 20O setup.'),
        qualifications=['No fitted coefficients or input chosen from archived agreement.',
            'Original baseline, all 725 targets and all failed comparisons are unchanged.',
            'No claim that either alternate input generated the native output.',
            'Original ASWING remains distinct from ASWING-m and experiments.',
            'Rigid comparisons have circulation checks, not full structural equilibrium checks.']))
    print(json.dumps(dict(cases=[c['name'] for c in cases],pins=len(paths))))


def worker(name):
    import numpy as np
    from openswing.aero import FlightCondition,evaluate_aerodynamics
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing.equilibrium_state import identity,matching_identity,restore,warm_start_recipe
    from openswing.network import network_snapshot
    from openswing.source_coupled import SourceCoupledNetwork
    from scripts.isae_suite_ae3 import coefficients
    from scripts.isae_suite_ap1 import reconstruct_wrenches
    plan=checked();case=next(c for c in plan['cases'] if c['name']==name)
    assert all(os.environ.get(k)=='1' for k in THREADS)
    job=case['job'];folder=OUT/'cases'/name;variant=case['variant']
    source=Path(case['source']).read_text()
    model=parse_asw(source,beam_interpolation=job['settings']['beam_interpolation'])
    original=parse_asw(Path(job['source']).read_text(),beam_interpolation=job['settings']['beam_interpolation'])
    assert not model.diagnostics and len(model.beams)==len(original.beams)==1
    changed=[]
    for key,d in original.beams[0].distributions.items():
        alternate=model.beams[0].distributions[key]
        assert np.array_equal(d.t,alternate.t)
        if not np.array_equal(d.values,alternate.values):changed.append(key)
    expected_changed={'report_cm':['dCMdF1'],'sibling_lift':['dCLdF1']}.get(variant,[])
    assert changed==expected_changed
    for key in original.records:
        assert np.array_equal(original.records[key],model.records[key])
    assert np.array_equal(original.reference,model.reference) and np.array_equal(original.constants,model.constants)
    stations=np.array([-.9*.6096,0.,.9*.6096])
    assert np.allclose(model.beams[0].value('dCLdF1',stations),[-case['control_lift'],0.,case['control_lift']],atol=1e-15,rtol=0)
    assert np.allclose(model.beams[0].value('dCMdF1',stations),[-case['control_moment'],0.,case['control_moment']],atol=1e-15,rtol=0)
    c=deepcopy(job['condition']);c['freeze_influences']=variant=='frozen'
    for key in ('powers','controls','circulation_modes'):c[key]={int(k):v for k,v in c[key].items()}
    condition=FlightCondition(**c)
    network=SourceCoupledNetwork(model,job['panels'],condition,job['gravity'])
    assert network.station_nodes[1][0].tolist()==read(case['baseline_preflight'])['stations']
    assert network.ne==job['expected_elements'] and network.nn==job['expected_nodes']
    checks=[]
    def check(name,value,gate):
        checks.append(dict(name=name,metric=float(value),gate=gate,passed=bool(np.isfinite(value) and value<=gate)))
    def difference(a,b):
        a,b=np.asarray(a),np.asarray(b)
        return float(np.max(abs(a-b),initial=0)/max(1.,np.max(abs(a),initial=0),np.max(abs(b),initial=0)))
    request=dict(action='solve',mode='mounted',source=source,panels=job['panels'],
        numerics=job['settings'],condition=c,gravity=job['gravity'])
    write(folder/'request.json',request)
    if variant=='rigid':
        result=evaluate_aerodynamics(model,condition,network.meshes)
        gamma=np.array([s['circulation'] for s in result['strips']])
        fresh=evaluate_aerodynamics(model,condition,network.meshes,circulation=gamma)
        check('fresh_circulation_residual',max(map(abs,fresh['circulation_residual'])),1e-8)
        scope='Fixed undeformed geometry; no structural solve or balance claim.'
    else:
        result=dispatch(request)
        recipe=warm_start_recipe(model,job['panels'],result['equilibrium_state'])
        network=SourceCoupledNetwork(model,job['panels'],condition,job['gravity'],mesh_recipe=recipe)
        assert matching_identity(identity(network),result['equilibrium_state']['identity'])
        state=restore(network,result['equilibrium_state']);assert network.nfev==0
        residual,data=network.residual(state,detail=True);assert network.nfev==1
        fresh=network_snapshot(network,residual,data)
        check('fresh_full_residual',np.max(abs(residual)),1e-8)
        for key in ('force','moment'):
            applied,support=np.array(result['applied_'+key]),np.array(result['support_'+key])
            check(key+'_balance',np.linalg.norm(applied+support)/max(1.,np.linalg.norm(applied)+np.linalg.norm(support)),1e-7)
        clamp=[item['a'] for item in network.constraints if item['kind']=='ground']
        assert len(clamp)==1
        check('root_position',np.max(abs(data['r'][clamp[0]]-job['root_position'])),1e-10)
        check('root_frame',np.max(abs(data['Q'][clamp[0]]-np.eye(3))),1e-10)
        scope='Mounted source-coupled equilibrium and one fresh restored full residual.'
    assert result['converged'] and fresh['converged']
    assert result['aerodynamic_influences']['frozen']==c['freeze_influences']
    assert result['atmosphere']['density']==c['density'] and result['mach']==0.
    wrench=reconstruct_wrenches(result,model.reference[1])
    for key in ('distributed_aero_force','distributed_aero_moment'):
        check('independent_'+key,difference(result[key],wrench[key]),2e-10)
        check('fresh_'+key,difference(result[key],fresh[key]),2e-10)
    qS=.5*c['density']*c['speed']**2*model.reference[0,0]
    def mapped(packet):return coefficients(packet['distributed_aero_force'],packet['distributed_aero_moment'],
        c['alpha'],qS,model.reference[0,1],model.reference[0,2])
    values=mapped(result);independent=mapped(wrench)
    check('coefficient_mapping',max(abs(values[k]-independent[k]) for k in values),2e-10)
    arm_moment=sum((np.cross(np.array(s['position'])-model.reference[1],s['force']) for s in result['strips']),np.zeros(3))
    couple=sum((np.array(s['moment']) for s in result['strips']),np.zeros(3))
    components=dict(force_arm=-float(arm_moment[0])/(qS*model.reference[0,2]),
        section_couple=-float(couple[0])/(qS*model.reference[0,2]))
    check('rolling_components_sum',abs(sum(components.values())-values['Cl']),2e-10)
    baseline=read(case['baseline_result'])
    baseline_values={item['name']:item['predicted'] for item in baseline['reference_checks']}
    reference={item['name']:item['expected'] for item in baseline['reference_checks']}
    maximum_incidence=max(abs(s['da_eff']) for s in result['strips'])
    write(folder/'result.json',result);write(folder/'fresh-result.json',fresh)
    report=dict(name=name,variant=variant,speed=c['speed'],nominal=job['nominal'],scope=scope,
        changed_distributions=changed,source_hash=pin(case['source']),checks=checks,
        checked_properties=dict(reference=model.reference.tolist(),constants=model.constants.tolist(),
            stations=network.station_nodes[1][0].tolist(),control_lift=case['control_lift'],control_moment=case['control_moment'],
            frozen=c['freeze_influences'],all_other_distributions_and_records_unchanged=True),
        values=values,baseline=baseline_values,reference=reference,
        rolling_components=components,maximum_linearized_da_eff_radians=maximum_incidence,
        primary_votes_added=0,numerical_pass=all(c['passed'] for c in checks),
        Cl_error_percent=100*abs(values['Cl']-reference['Cl'])/abs(reference['Cl']))
    write(folder/'report.json',report);checked()
    assert report['numerical_pass']
    print(json.dumps(dict(name=name,Cl=values['Cl'],baseline=baseline_values['Cl'],reference=reference['Cl'],
        Cl_error_percent=report['Cl_error_percent'],checks=len(checks))),flush=True)


def launch(name):
    plan=checked();case=next(c for c in plan['cases'] if c['name']==name)
    folder=OUT/'cases'/name;folder.mkdir(parents=True,exist_ok=False)
    write(folder/'started.json',dict(case=case,plan=pin(OUT/'plan.json'),observed_utc=datetime.now(timezone.utc).isoformat()))
    def limits():
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
    start=time.monotonic();pid=0;timeout=False
    with (folder/'stdout.log').open('x') as out,(folder/'stderr.log').open('x') as err:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker',name],cwd=ROOT,
            env={**os.environ,**THREADS},stdout=out,stderr=err,preexec_fn=limits,start_new_session=True)
        try:
            while not pid:
                pid,status,usage=os.wait4(child.pid,os.WNOHANG)
                if pid:break
                if time.monotonic()-start>LIMITS['wall_seconds']:
                    timeout=True;os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0);break
                time.sleep(.05)
        finally:
            if not pid:os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0)
            child.returncode=os.waitstatus_to_exitcode(status)
    terminal=dict(returncode=child.returncode,process_reaped=True,supervisor_timeout=timeout,
        cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-start,
        peak_rss_kib=usage.ru_maxrss,limits=LIMITS,observed_utc=datetime.now(timezone.utc).isoformat())
    write(folder/'terminal.json',terminal);checked()
    write(folder/'sources-verified.json',dict(all_pins_checked=True,plan=pin(OUT/'plan.json')))
    print(json.dumps(dict(name=name,**terminal)),flush=True)
    if child.returncode:sys.exit(1)
    print((folder/'stdout.log').read_text(),end='')


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='launch':launch(sys.argv[2])
    elif sys.argv[1]=='worker':worker(sys.argv[2])
    else:raise ValueError(sys.argv[1])
