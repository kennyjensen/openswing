"""Independent sibling control scale under the conditional AE-3 roll constraint.

The 0.0686 coefficient comes from original 60O/80O/95O files; it is not fitted
to a native result and is not proven to have generated the 20O exports.
"""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae3_roll_constraint_r2 as run
from scripts.probe_isae_ae2_cold_trace import read,write,pin

OUT=ROOT/'artifacts/isae/ae3-roll-control-20261111'
BASE=ROOT/'artifacts/isae/ae3-roll-constraint-r2-20261111'
run.OUT=run.supervisor.OUT=OUT
run.supervisor.__file__=__file__


def prepare():
    assert not OUT.exists()
    parent=read(BASE/'plan.json')
    for p in parent['pins']:assert pin(p['path'])==p,p['path']
    source=Path(parent['cases'][0]['job']['source']).resolve()
    sibling=source.with_name('Straight_60O.asw')
    raw=source.read_text();other=sibling.read_text()
    assert raw.count('0.0581')==1 and '0.0686' in other and '-0.0102' in other
    variant=OUT/'model.asw';variant.parent.mkdir(parents=True);variant.write_text(raw.replace('0.0581','0.0686'))
    paths={p['path'] for p in parent['pins']}
    paths.update(str(p) for p in (Path(__file__),BASE/'plan.json',variant,sibling,
        ROOT/'scripts/probe_isae_ae3_roll_constraint_r2.py'))
    cases=[]
    for old in parent['cases']:
        case=deepcopy(old);case.pop('saved_result',None)
        case['job']['source']=str(variant)
        case['name']=case['name'].replace('roll-free','sibling-lift-roll-free')
        case['original_source']=str(source)
        cases.append(case)
    write(OUT/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        cases=cases,pins=[pin(p) for p in sorted(paths)],limits=run.supervisor.LIMITS,
        constraint=parent['constraint'],primary_votes_added=0,method=__doc__,
        control_change=dict(distribution='dCLdF1',literal=.0581,alternate=.0686,
            independently_sourced_from=pin(sibling),moment_slope_unchanged=-.0102),
        qualifications=parent['qualifications']+[
            'Only dCLdF1 scale changes in a copied model; the original 20O remains unchanged.',
            'Fixed-acceleration baseline in reports is the original literal model, not a same-slope diagnostic.',
            'Report highest-Re wording and sibling title/scale support investigation, not exact historical identity.']))
    print('Prepared two sibling-lift / roll-constraint diagnostics.',flush=True)


def worker(name):
    import numpy as np
    from openswing.asw import parse_asw
    plan=read(OUT/'plan.json');case=next(c for c in plan['cases'] if c['name']==name)
    parsed=[parse_asw(Path(p).read_text(),beam_interpolation='drela-segspl-v1')
            for p in (case['original_source'],case['job']['source'])]
    original,variant=parsed
    assert not original.diagnostics and not variant.diagnostics
    changed=[]
    for key,a in original.beams[0].distributions.items():
        b=variant.beams[0].distributions[key]
        assert np.array_equal(a.t,b.t)
        if not np.array_equal(a.values,b.values):changed.append(key)
    assert changed==['dCLdF1']
    for key,value in original.records.items():assert np.array_equal(value,variant.records[key])
    assert np.array_equal(original.reference,variant.reference) and np.array_equal(original.constants,variant.constants)
    run.worker(name)
    path=OUT/'cases'/name/'report.json';report=read(path)
    report.update(changed_distributions=changed,control_change=plan['control_change'],
        literal_fixed_acceleration=report.pop('fixed_acceleration'),
        exact_historical_input_recovered=False)
    write(path,report)


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='launch':run.supervisor.launch(sys.argv[2])
    elif sys.argv[1]=='worker':worker(sys.argv[2])
    else:raise ValueError(sys.argv[1])
