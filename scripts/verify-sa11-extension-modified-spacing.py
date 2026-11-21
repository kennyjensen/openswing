"""Transfer the fixed SA-2 coordinate-derived spacing to eight SA-11 controls."""
import argparse
import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'scripts/verify-sa11-extension-mesh-limit.py'
spec=importlib.util.spec_from_file_location('mesh_limit_driver',SOURCE)
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
PARENT=ROOT/'artifacts/isae/sa11-extension-drag-budget-r2-20261108'


def prepare(out):
    driver.bounded();assert not out.exists()
    parent=driver.read(PARENT/'plan.json');driver.check(parent['pins'])
    analysis=driver.read(PARENT/'analysis.json')
    assert analysis['verified'] and analysis['plan_sha256']==driver.sha(PARENT/'plan.json')
    controls=[r for r in analysis['cases'] if r['settings']['alpha'] in (3,5) and not r['settings']['freeze_influences']]
    assert len(controls)==8
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    pins=dict(parent['pins']);cases=[]
    for control in controls:
        original=control['case']['original_job'];n=original['settings']['panels']
        model=parse_asw((ROOT/original['model_path']).read_text(),beam_interpolation='natural-v1')
        mesh_spec=dict(default=n,beams={'1':dict(count=n,spacing='modified-cosine',min_spacing=driver.MINIMUM)})
        mesh,=model_meshes(model,mesh_spec)
        assert min(mesh.length)>=driver.MINIMUM-1e-12 and len(mesh.tm)<=160
        cases.append(dict(id=control['id']+'-modified',requested_intervals=n,control=control,mesh=mesh_spec,
            preflight=dict(actual_intervals=len(mesh.tm),minimum_interval=float(min(mesh.length)),
                maximum_interval=float(max(mesh.length)),nodes=np.r_[mesh.t0[0],mesh.t1].tolist())))
        folder=PARENT/control['id'];assert driver.sha(folder/'report.json')==control['report_sha256']
        pins[str((folder/'report.json').relative_to(ROOT))]=control['report_sha256']
        for name,digest in control['artifacts'].items():
            assert driver.sha(folder/name)==digest;pins[str((folder/name).relative_to(ROOT))]=digest
    for path in (Path(__file__),SOURCE,PARENT/'plan.json',PARENT/'analysis.json',
        ROOT/'docs/validation/modified-cosine-option-20261030.md',ROOT/'docs/validation/isae-sa1-sa5-spacing-20261029.md'):
        pins[str(path.relative_to(ROOT))]=driver.sha(path)
    driver.check(pins)
    out.mkdir(parents=True);(out/'driver-used.py').write_text(Path(__file__).read_text())
    (out/'solver-recorder-used.py').write_text(SOURCE.read_text())
    driver.write(out/'plan.json',dict(observed_utc=driver.utc(),cases=cases,pins=pins,
        source_basis='Existing modified-cosine option reproduces a fixed distribution inferred from printed native SA-2 coordinates without fitting forces. This cross-case evidence does not authenticate SA-11 node placement or a universal ASWING default.',
        protocol='Original extension;alpha3/5 at240/272m/s; original64/128 requests and16.466mm minimum. Change only spacing from cosine to existing modified-cosine. All eight cases declared before solves;retain rejected outcomes. No primary default/scope replacement.',
        minimum_spacing=driver.MINIMUM,physical_calls=8,primary_passes_added=0))
    driver.signal.alarm(0)
    print([dict(id=c['id'],actual=c['preflight']['actual_intervals'],minimum=c['preflight']['minimum_interval']) for c in cases],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('action',choices=('prepare','run'));parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:driver.run(args.output.resolve(),args.index)
