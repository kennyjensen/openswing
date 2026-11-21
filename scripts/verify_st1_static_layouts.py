"""ST-1 static layout comparisons with explicit empty-block termination only.

One foreground cold solve per invocation. Original models and target tokens
are preserved; nominal 200 is a refinement diagnostic, not an extra archive vote.
"""
import argparse
from decimal import Decimal
import hashlib
import math
from pathlib import Path
import resource
import time

import verify_sa14_defaults as common

ROOT = common.ROOT
BASE = ROOT/'artifacts/isae/st1-current-20261109/plan.json'
CASES = {
    '20': dict(index=23, mass=.7, twist=46., density=.0683,
        fields=dict(EIcc=.983, GJ=1.18, EInn=290., GKc=1.1e6, EA=3.9e6, GKn=1.2e5, EIcs=0.),
        producer_lines=[461,463], producer_call="change_mass2('[20_m70_20]_2a.asw',M(i),45)"),
    '45': dict(index=26, mass=.4, twist=45., density=.07,
        fields=dict(EIcc=.522, GJ=.368, EInn=298., GKc=2.6e5, EA=3.7e6, GKn=2.9e5, EIcs=.102),
        producer_lines=[313,315], producer_call="change_mass('[45_0]_3s.asw',M(i),45)"),
}


def prepare(out):
    prior = common.read(BASE); common.authenticate(prior['pins'])
    pins = dict(prior['pins']); pins[BASE.relative_to(ROOT).as_posix()] = common.sha(BASE)
    pins[Path(__file__).relative_to(ROOT).as_posix()] = common.sha(Path(__file__))
    jobs = []
    for key, config in CASES.items():
        original = prior['jobs'][config['index']]
        source_path = ROOT/original['model_path']
        source = source_path.read_text()
        assert source.rstrip().endswith('\nEngine')
        assert len(original['observations']) == 3 and original['pairing_status'] == 'SINGLE_RETAINED_DRIVER_WRITE_NAME'
        derived = source+'End\n'
        folder = out/key; folder.mkdir()
        (folder/'original.asw').write_bytes(source_path.read_bytes())
        (folder/'model.asw').write_text(derived)
        producer = source_path.parent/'Post_analysis.m'
        lines = producer.read_text().splitlines()
        assert config['producer_call'] in lines[config['producer_lines'][1]-1]
        assert str(config['mass']) in lines[config['producer_lines'][0]-1]
        for nominal in (100,200):
            jobs.append(dict(key=key, nominal=nominal, config=config, archive_job=original,
                source_path=(folder/'model.asw').relative_to(ROOT).as_posix(),
                original_sha256=common.sha(source_path), derived_sha256=common.sha(folder/'model.asw'),
                transformation='Append End to the existing empty trailing Engine block. No numeric token changes.',
                primary_archive_slots=3 if nominal==100 else 0))
    common.write(out/'plan.json',dict(observed_utc=common.utc(),jobs=jobs,pins=pins,
        reference_relative_tolerance=.05, tiny_reference=1e-8,
        numerical_gates=dict(residual=1e-8,balance=1e-7,closure=2e-10,clamp=1e-10),
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25),
        qualification='Two syntax-normalized static layouts, original material properties/load/orientation and native position targets. '
        'No recovered historical node arrays, binary startup or continuation is claimed. Fine meshes are diagnostics only.'))
    print('Prepared two source-paired static layouts on nominal 100/200 grids.')


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins'])
    job=plan['jobs'][index]; config=job['config']
    source_path=ROOT/job['source_path'];assert common.sha(source_path)==job['derived_sha256']
    source=source_path.read_text()
    original=(ROOT/job['archive_job']['model_path']).read_text()
    assert source==original+'End\n' and original.rstrip().endswith('\nEngine')
    folder=out/f'job-{index}';folder.mkdir()
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing.source_discrete import SourceSectionNetwork
    from openswing.equilibrium_state import warm_start_recipe,restore,identity,matching_identity
    import numpy as np

    model=parse_asw(source,beam_interpolation='drela-segspl-v1')
    assert not model.diagnostics and len(model.beams)==1
    beam=model.beams[0];t=np.array([-.28,0.,.28])
    assert np.all(beam.value('twist',t)==config['twist'])
    for field,value in config['fields'].items():
        np.testing.assert_allclose(beam.value(field,t),value,rtol=2e-15,atol=0)
    np.testing.assert_allclose(beam.value('mg',t),config['density']*9.81,rtol=2e-15)
    for field in ('Cea','Nea','Cta','Nta','Ccg','Ncg','Dmg'):
        assert np.all(beam.value(field,t)==0),field
    assert len(model.records['weight'])==1
    np.testing.assert_allclose(model.records['weight'][0][:6],[1.,-.28,0.,-.28,0.,config['mass']*9.81],atol=0,rtol=2e-15)
    panels=dict(default=job['nominal'],beams={'1':dict(count=job['nominal'],spacing='cosine')})
    request=dict(action='solve',mode='structural',source=source,panels=panels,
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-steady-section-v1'),
        gravity=[0.,0.,-9.81],loads=[],tolerance=1e-8,continuation_steps=4)
    common.write(folder/'request.json',request)
    started=time.monotonic();result=dispatch(request);common.write(folder/'result.json',result)
    recipe=warm_start_recipe(model,panels,result['equilibrium_state'])
    network=SourceSectionNetwork(model,panels,None,[0.,0.,-9.81],(),mesh_recipe=recipe,
        allow_signed_point_weights=True,allow_signed_distributed_weights=True)
    assert matching_identity(result['equilibrium_state']['identity'],identity(network))
    state=restore(network,result['equilibrium_state']);assert network.nfev==0
    residual,_=network.residual(state,detail=True);assert network.nfev==1
    assert not network.engines and not network.loads and network.condition is None
    nodes=sorted(result['nodes'],key=lambda n:n['t'])
    t=np.array([n['t'] for n in nodes]);r=np.array([n['position'] for n in nodes])
    assert len(nodes)==job['nominal']+2 and t[0]==-.28 and t[-1]==.28 and -.22 in t
    # Straight jig, constant distributed mass, zero CG offsets: the documented
    # endpoint gravity rule independently gives each node's weight and wrench.
    nodal_mass=np.zeros(len(nodes));half=config['density']*np.diff(t)/2
    nodal_mass[:-1]+=half;nodal_mass[1:]+=half;nodal_mass[0]+=config['mass']
    force=nodal_mass[:,None]*np.array([0.,0.,-9.81])
    total_force=force.sum(axis=0);moment=np.cross(r,force).sum(axis=0)
    def relative(a,b):
        a,b=np.asarray(a),np.asarray(b)
        return float(np.max(abs(a-b))/(1+max(np.max(abs(a)),np.max(abs(b)))))
    checks=dict(residual=float(np.max(abs(residual))),
        force_balance=relative(np.asarray(result['applied_force'])+result['support_force'],[0.,0.,0.]),
        moment_balance=relative(np.asarray(result['applied_moment'])+result['support_moment'],[0.,0.,0.]),
        independent_force=relative(total_force,result['applied_force']),
        independent_moment=relative(moment,result['applied_moment']),
        clamp_position=float(np.max(abs(r[-1]-[0.,.28,0.]))),
        clamp_rotation=float(np.max(abs(np.asarray(nodes[-1]['rotation'])-np.eye(3)))))
    assert result['converged'] and checks['residual']<=1e-8
    assert checks['force_balance']<=1e-7 and checks['moment_balance']<=1e-7
    assert checks['independent_force']<=2e-10 and checks['independent_moment']<=2e-10
    assert checks['clamp_position']<=1e-10 and checks['clamp_rotation']<=1e-10
    sensor=result['sensors'][0]; assert sensor['t']==-.22 and sensor['beam']==1 and sensor['index']==1
    actual=sensor['anchor_position_body'];np.testing.assert_allclose(actual,r[np.where(t==-.22)[0][0]],rtol=0,atol=1e-12)
    comparisons=[]
    for value,ref in zip(actual,job['archive_job']['observations'],strict=True):
        expected=Decimal(ref['expected_token']);error=abs(Decimal(str(value))-expected)
        absolute=Decimal(ref['exact_decimal_tolerance'])
        limit=absolute if abs(expected)<=Decimal('1e-8') else max(absolute,abs(expected)*Decimal('.05'))
        comparisons.append(dict(name=ref['name'],expected_token=ref['expected_token'],predicted=value,
            error_m=float(error),error_percent=float(100*error/abs(expected)),passed=error<=limit,
            strict_passed=error<=absolute))
    report=dict(observed_utc=common.utc(),job=job,comparisons=comparisons,numerical_checks=checks,
        independently_reconstructed_force=total_force.tolist(),independently_reconstructed_moment=moment.tolist(),
        seconds=time.monotonic()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=common.sha(out/'plan.json'),
        artifacts={p.name:common.sha(p) for p in folder.iterdir() if p.is_file()},
        production_physics_changed=False,cold_solves=1,fresh_residuals=1)
    common.authenticate(plan['pins']);common.write(folder/'report.json',report)
    print(dict(layout=job['key'],nominal=job['nominal'],predicted=actual,
        errors_percent=[c['error_percent'] for c in comparisons],checks=checks,seconds=report['seconds']))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--index',type=int)
    args=parser.parse_args();common.bounded()
    if args.action=='prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
