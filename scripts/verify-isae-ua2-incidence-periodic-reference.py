"""Verify independent cold and periodic references before production starts."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time
import numpy as np
from isae_ua_wing_incidence_refined import AccurateInclinedWing
from isae_ua2_incidence_periodic import GATES, PERIOD, CYCLES, grid, full_request
from isae_ua_periodic import fourier

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua2-incidence-periodic-20261101'
OLD = ROOT/'artifacts/isae/ua2-incidence-20261101-r2/reference-n20-a9-k0950/report.json'


def main():
    assert not (BASE/'reference-plan.json').exists()
    old = json.loads(OLD.read_text())
    assert old['passed']
    paths = [Path(__file__).resolve(), OLD, BASE/'motion-diagnostic.json',
             *[ROOT/'scripts'/n for n in ('isae_ua2_incidence_periodic.py',
             'isae_ua2_incidence_time.py', 'isae_ua_incidence_periodic.py',
             'isae_ua_wing_incidence_refined.py', 'isae_ua_wing_incidence.py',
             'isae_ua_wing_nonlinear.py', 'isae_ua_wing_periodic.py',
             'isae_ua_periodic.py', 'isae_ua_section_reference.py', 'isae_suite_unsteady.py')],
             ROOT/'.reference/asw_theory.txt', ROOT/'.reference/asw_uns_theory.txt']
    pins = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in paths}
    grids = {str(n): grid(n) for n in (320, 640)}
    for n, times in grids.items():
        assert [float(r.split()[0]) for r in full_request(int(n))['time']['forcing'].splitlines()[1:]] == times
    np.testing.assert_array_equal(grids['640'][::2], grids['320'])
    plan = dict(gates=GATES, source_sha256=pins, grids=grids, cycles=CYCLES,
                panels=20, alpha_deg=9, k=.95, amplitude_ratio=.5, span=10.,
                periodic_seed='Each independent method resumes its own verified periodic boundary; production starts from its own steady solution.',
                native_ASWING_comparison=False)
    (BASE/'reference-plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    for p in paths:
        target=BASE/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target)
    times = grids['640']
    phase = PERIOD*np.arange(641)/640
    wing = AccurateInclinedWing(20, alpha_deg=9.)
    results = {}; durations = {}
    for method in ('DOP853', 'Radau'):
        started = time.monotonic()
        cold = wing.integrate(times, amplitude_ratio=.5, k=.95, method=method)
        seed = old['reference'][method]['periodic']['rows'][0]['circulation']
        periodic = wing.integrate(phase, amplitude_ratio=.5, k=.95, method=method, initial=seed)
        states = np.array([r['circulation'] for r in periodic['rows']])
        closure = float(np.max(abs(states[-1]-states[0])/np.max(abs(states), axis=0)))
        assert closure < 1e-10
        periodic.update(closure_fraction=closure,
                        measured=fourier(phase, [r['CL'] for r in periodic['rows']], PERIOD))
        results[method] = dict(cold=cold, periodic=periodic)
        durations[method] = time.monotonic()-started
        print(json.dumps(dict(method=method, seconds=durations[method], closure=closure)), flush=True)
    differences = {}
    for kind in ('cold', 'periodic'):
        for key in ('CL', 'circulation', 'circulation_rate'):
            x,y=(np.array([r[key] for r in results[m][kind]['rows']]) for m in ('DOP853','Radau'))
            differences[kind+'_'+key]=float(np.max(abs(x-y)/np.max(abs(y),axis=0)))
    passed = max(differences.values()) < GATES['reference_agreement_fraction']
    assert all(sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in pins.items())
    output=dict(passed=passed, reference=results, method_differences=differences,
                grids=grids, method_seconds=durations, native_ASWING_comparison=False)
    (BASE/'reference.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=passed, differences=differences)))
    if not passed: raise SystemExit(1)


if __name__ == '__main__': main()
