"""A conditional SA-15 anchor; the version-specific .set is NOT decoded.

Never credits the blocked historical registration. Literal model, exact driver
angle and all seven native columns are retained. Zero controls, sea level,
Mach=0, current influences and default source cosine nodes are explicit choices.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def pin(p):
    return dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def run(folder,panels,row,*,frozen=False):
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition,solve_rigid
    from scripts.isae_suite_polars import reconstructed_wrench
    from scripts.isae_suite_sa6 import stability_coefficients
    from scripts.isae_suite_extra_polars import decode_table
    family=next((ROOT/'.reference/isae-validation').glob('*/1 - Aerodynamics/SA - Steady Aerodynamics Cases/SA - 15*'))
    model_path=family/'JW-1_FW_Only_Body.asw'
    driver=family/'JW-1_FW_Only_Body.sh'
    target=family/'JW1_FW_Only_Body_Aswing_simulations/JW1_FW_Only_Body_CL_alpha.txt'
    angles=[line.split()[1] for line in driver.read_text().splitlines() if line.startswith('!A ')]
    reference=decode_table(target.read_text(),15)[row-1]
    assert len(angles)==13 and 1<=row<=13
    pins=[pin(p) for p in (model_path,driver,target,family/'JW-1_FW_Only_Body.set')]
    manifest=json.loads((ROOT/'.reference/isae-validation/manifest.json').read_text())
    for p in pins:
        original=p['path'].split(manifest['revision']+'/',1)[1]
        assert manifest['files'][original]['sha256']==p['sha256']
    kernels=[pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))]
    model=parse_asw(model_path.read_text(),beam_interpolation='drela-segspl-v1')
    condition=FlightCondition(speed=380.,density=float(model.constants[1]),alpha=float(angles[row-1]),
        beta=0.,mach=0.,controls={},freeze_influences=frozen,stall=True,stall_factor=40.,stall_width=.05,
        wake_core_ratio=.25,aero_lag=True)
    plan=dict(row=row,panels=panels,alpha_token=angles[row-1],source_pins=pins,kernel_pins=kernels,
        speed=380.,density=condition.density,mach=0.,beam_interpolation='drela-segspl-v1',
        freeze_influences=frozen,helper=pin(Path(__file__)),
        reference=reference,original_set_decoded=False,registered_passes_credited=0,
        scope='Conditional setup and stability-axis moments about Reference. Original startup, .set, node distribution and OPER coefficient conventions remain unverified.')
    folder.mkdir(parents=True,exist_ok=False)
    def save(name,value):
        def encode(v):
            if isinstance(v,np.ndarray):return v.tolist()
            if isinstance(v,np.generic):return v.item()
            raise TypeError(type(v).__name__)
        with (folder/name).open('w') as f:json.dump(value,f,indent=2,allow_nan=False,default=encode)
    save('plan.json',plan)
    began=time.monotonic()
    result=solve_rigid(model,condition,panels=panels)
    elapsed=time.monotonic()-began
    save('result.json',result)
    force,moment,_=reconstructed_wrench(model,result)
    area,chord,span=model.reference[0];qS=.5*condition.density*condition.speed**2*area
    independently=stability_coefficients(force,moment,condition.alpha,qS,chord,span)
    a=np.deg2rad(condition.alpha);c,s=np.cos(a),np.sin(a)
    outputs=dict(CD=result['CD'],CY=result['CY'],CL=result['CL'],
        Cl=c*result['Cl']+s*result['Cn'],Cm=result['Cm'],Cn=-s*result['Cl']+c*result['Cn'],efficiency=result['efficiency'])
    checks=[dict(name='circulation convergence',passed=bool(result['converged']) and result['residual']<=1e-8,value=result['residual']),
        dict(name='literal parser',passed=not model.diagnostics),
        dict(name='complete force reconstruction',passed=bool(np.max(abs(force-result['force']))/qS<=2e-10)),
        dict(name='complete moment reconstruction',passed=bool(np.max(abs(moment-result['moment']))/(qS*chord)<=2e-10)),
        dict(name='source unchanged',passed=all(pin(ROOT/p['path'])==p for p in pins+kernels))]
    for name,value in independently.items():
        actual=-outputs['CD'] if name=='CX' else outputs[name]
        checks.append(dict(name=name+' normalization',passed=bool(abs(value-actual)<=2e-10)))
    valid=all(c['passed'] for c in checks)
    comparisons=[]
    for name,value in outputs.items():
        ref=reference['fields'][name];expected=ref['value'];error=abs(value-expected)
        limit=max(ref['tolerance'],.05*abs(expected)) if abs(expected)>1e-8 else ref['tolerance']
        comparisons.append(dict(name=name,predicted=float(value),expected=expected,
            error_percent=100*error/abs(expected) if abs(expected)>1e-8 else None,
            absolute_error=float(error),passed=bool(valid and error<=limit),tolerance=limit))
    report=dict(status='computed' if valid else 'numerical_failure',solve_seconds=elapsed,
        numerical_checks=checks,reference_checks=comparisons,
        conditional_passed=sum(c['passed'] for c in comparisons),required=7,
        registered_passes_credited=0,original_set_decoded=False,
        diagnostic_Cm_origin=result['Cm_origin'],plan=pin(folder/'plan.json'),result=pin(folder/'result.json'))
    save('report.json',report);print(json.dumps(report,default=float),flush=True)
    assert valid


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder',type=Path);p.add_argument('--panels',type=int,choices=(64,128),default=64)
    p.add_argument('--row',type=int,choices=range(1,14),default=4)
    p.add_argument('--frozen-influences',action='store_true',help='Separate declared F-toggle diagnostic')
    a=p.parse_args();run(a.folder.resolve(),a.panels,a.row,frozen=a.frozen_influences)
