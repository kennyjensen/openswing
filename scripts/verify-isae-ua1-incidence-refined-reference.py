"""Prepare and independently verify the complete eight-cycle inclined reference."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time

import numpy as np
from isae_ua_incidence_periodic import reference_history,GATES,ALPHA,K
from isae_ua_incidence_reference import trajectory
from isae_ua_periodic import fourier

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-incidence-periodic-refined-20261101'


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    if (BASE/'reference.json').exists() or (BASE/'reference-plan.json').exists():raise SystemExit('Preserve reference evidence')
    BASE.mkdir(parents=True,exist_ok=True)
    paths=[Path(__file__).resolve(),*[ROOT/'scripts'/n for n in ('isae_ua_incidence_periodic.py',
        'isae_ua_incidence_reference.py','isae_suite_unsteady.py','isae_ua_periodic.py','isae_ua_section_reference.py')],
        ROOT/'tests/test_isae_ua_incidence_periodic.py',ROOT/'.reference/asw_uns_theory.txt',ROOT/'.reference/asw_theory.txt',
        ROOT/'artifacts/isae/ua1-incidence-20261101/ref-k094-a9/report.json',
        ROOT/'artifacts/isae/ua1-incidence-20261101/source-review.json']
    pins={str(p.relative_to(ROOT)):digest(p) for p in paths}
    plan=dict(source_sha256=pins,gates=GATES,native_ASWING_comparison=False,steps=320,cycles=8)
    (BASE/'reference-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for p in paths:
        frozen=BASE/'frozen-code'/p.relative_to(ROOT);frozen.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,frozen)
    started=time.monotonic();reference=reference_history(320)
    direct=trajectory([r['time'] for r in reference['cold_rows']],alpha_deg=ALPHA,k=K,boundary='steady',method='DOP853')
    differences={}
    for key in ('circulation','circulation_rate','CL','CF'):
        a=np.array([r[key] for r in reference['cold_rows']]);b=np.array([r[key] for r in direct['rows']])
        differences[key]=float(np.max(abs(a-b))/np.max(abs(b)))
    passed=max(differences.values())<GATES['reference_agreement_fraction']
    phase=reference['periodic']['rows']
    measured=fourier([r['time'] for r in phase],[r['CL'] for r in phase],reference['period'])
    # The prior 512-interval, three-method reference supplies independent
    # harmonic quadrature evidence at exactly the same physical settings.
    previous=json.loads(paths[-2].read_text())
    old=previous['measured_periodic']
    harmonic_change=max(abs(measured['mean']-old['mean']),
        *(abs(a['amplitude']-b['amplitude']) for a,b in zip(measured['harmonics'],old['harmonics'])))
    assert harmonic_change<1e-10
    output=dict(plan=plan,reference=reference,direct_cold=direct,agreement_fractions=differences,
        passed=passed,measured_periodic=measured,maximum_harmonic_quadrature_change=harmonic_change,
        seconds=time.monotonic()-started,native_ASWING_comparison=False)
    assert all(digest(ROOT/n)==h for n,h in pins.items())
    (BASE/'reference.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=passed,agreement_fractions=differences,harmonic_change=harmonic_change,seconds=output['seconds'])))
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
