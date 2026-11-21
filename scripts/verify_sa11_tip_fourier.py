"""Eight fixed-mesh main-circulation representation controls at alpha3."""
import argparse
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
RECORDER=ROOT/'scripts/verify_sa11_paper_aligned.py'
spec=importlib.util.spec_from_file_location('aligned_recorder',RECORDER)
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
BASE=ROOT/'artifacts/isae/sa11-same-mainwing-20261108'
UPPER=ROOT/'artifacts/isae/sa11-minimum-spacing-20261108'
LOCAL=ROOT/'artifacts/isae/sa11-tip-local-mesh-20261108'
FACTOR=ROOT/'artifacts/isae/sa11-tip-factorization-20261108'


def prepare(out):
    driver.bounded();assert not out.exists()
    analysis=driver.read(LOCAL/'analysis.json');assert analysis['verified']
    pins=dict(analysis['pins']);driver.check(pins)
    parent=driver.read(LOCAL/'plan.json');base=driver.read(BASE/'plan.json');upper=driver.read(UPPER/'plan.json')
    cases=[]
    for count in (32,46):
        for modes in (20,30):
            for config in ('wing_alone','upper_winglet'):
                if count==46:seed=next(c for c in parent['cases'] if c['configuration']==config and c['alpha']==3)
                elif config=='wing_alone':seed=next(c for c in base['cases'] if c['label']=='0_70' and c['alpha']==3)
                else:
                    old=next(c for c in upper['cases'] if c['label']=='0_70' and c['alpha']==3)
                    seed=dict(old,configuration=config,model_path=str((UPPER/'model.asw').relative_to(ROOT)),
                              mesh=driver.read(UPPER/'mesh-import.json')['panels'],reused_accepted=None)
                condition=deepcopy(seed['condition']);assert condition['circulation_modes']=={}
                condition['circulation_modes']={'1':modes}
                cases.append(dict(seed,id=f'{config}-main{count}-modes{modes}-a12',condition=condition,
                                  configuration=f'{config}_main{count}',physical_configuration=config,
                                  main_intervals=count,main_modes=modes))
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    preflight={}
    for case in cases:
        if case['configuration'] not in preflight:
            model=parse_asw((ROOT/case['model_path']).read_text(),beam_interpolation='natural-v1')
            preflight[case['configuration']]=[dict(beam=m.beam.index,nodes=[float(m.t0[0]),*map(float,m.t1)],
                intervals=len(m.tm),minimum=float(min(m.length))) for m in model_meshes(model,case['mesh'])]
    for i in (11,12):
        p=FACTOR/f'a{i:02d}'/'constraint-verification.json';proof=driver.read(p);assert proof['verified']
        pins[str(p.relative_to(ROOT))]=driver.sha(p)
        p=FACTOR/f'a{i:02d}'/'report.json';pins[str(p.relative_to(ROOT))]=driver.sha(p)
    for path in (Path(__file__),RECORDER,FACTOR/'plan.json',FACTOR/'constraint-plan-r2.json',
                 LOCAL/'plan.json',LOCAL/'analysis.json',BASE/'plan.json',UPPER/'plan.json'):
        pins[str(path.relative_to(ROOT))]=driver.sha(path)
    driver.check(pins);out.mkdir(parents=True)
    (out/'driver-used.py').write_text(Path(__file__).read_text());(out/'recorder-used.py').write_text(RECORDER.read_text())
    driver.write(out/'plan.json',dict(observed_utc=driver.utc(),pins=pins,cases=cases,preflight=preflight,physical_calls=8,primary_passes_added=0,
        preparation_correction='First plan omitted recorder preflight; stopped before any physical solve. This distinct r2plan records nodes for each model/mesh configuration. Prior plan and failure receipt retained.',
        protocol='At240m/s andalpha3, both bare/upper models on existing main32 andtip-local46 meshes. Change only main-beam circulation to20 or30Fourier modes; winglets stay pointwise16each. Compare physical-mesh sensitivity and local/projected residuals with authenticated pointwise controls. Do not select a representation by reference error or change defaults.',
        source_basis='Drela steady Eqs62--63,150--153,200--204 document pointwise/Fourier alternatives. Jan PartI section5,p21 recommends20--40circulation variables in an elliptical-wing study; this motivates sensitivity counts,not an authenticated SA11 default or mode domain.',
        scope='Main-only representation check. Does not validate a coupled whole-surface Fourier domain or identify historical run settings. No new primary acceptance gate. All rejections remain evidence.',
        previous_goal_turn='Progress: exact common-interval factorization and conditional winglet equations show full cross-beam force change is~99%circulation-step/winglet-response and~1%receiver quadrature; stall negligible.',
        limits='One BLAS thread,512MiB address-space,15CPU/25wall seconds,at most3serialphysicalcalls. No browser/background tests.'))
    driver.signal.alarm(0);print(dict(prepared=True,physical_calls=len(cases)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','batch'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--start',type=int);p.add_argument('--count',type=int,default=2)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:driver.batch(a.output.resolve(),a.start,a.count)
