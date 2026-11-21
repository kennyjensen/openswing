"""Independently reduce saved interaction matrices and locate their mesh change."""
from datetime import datetime, timezone
from decimal import Decimal as D
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]).resolve()
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    assert os.environ.get(key) == '1'
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU, (15, 15)); signal.alarm(25)
import numpy as np

read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
plan = read(OUT/'plan.json'); pins = dict(plan['pins'])
for path, digest in pins.items():
    assert sha(ROOT/path) == digest, path
rows = []; matrices = {}; geometries = {}; maximum_reduction_error = 0.
bin_edges = [0., .125, .25, .5, 1.2426000001]


def near(actual, expected):
    global maximum_reduction_error
    maximum_reduction_error = max(maximum_reduction_error, abs(actual-expected))
    assert abs(actual-expected) < 2e-12, (actual, expected)


for case in plan['cases']:
    folder = OUT/case['id']; row = read(folder/'report.json')
    assert row['case'] == case and row['plan_sha256'] == sha(OUT/'plan.json')
    assert sha(folder/'pairs.npz') == row['pairs_sha256']
    for path in (folder/'report.json', folder/'pairs.npz'):
        pins[str(path.relative_to(ROOT))] = sha(path)
    with np.load(folder/'pairs.npz') as f:
        saved = {key: f[key] for key in f}
    beams = saved['beam'].tolist(); n = len(beams)
    scalar = {}; scalar_details = {}; flat = {}
    for term in ('bound', 'half_wake', 'finite_origin'):
        p = saved[term].tolist()
        buckets = {key: [] for key in row['blocks'][term]}
        details = {key: [] for key in row['details'][term]}
        for i in range(n):
            for j in range(n):
                receiver = 'main' if beams[i] == 1 else 'winglet'
                source = 'main' if beams[j] == 1 else 'winglet'
                key = receiver+'_from_'+source
                buckets[key].append(p[i][j])
                detail = ('main_own' if i == j else 'main_adjacent' if abs(i-j) == 1 else 'main_other') if key == 'main_from_main' else key
                details[detail].append(p[i][j])
        scalar[term] = {key: math.fsum(values) for key, values in buckets.items()}
        scalar_details[term] = {key: math.fsum(values) for key, values in details.items()}
        for key, value in scalar[term].items():
            near(value, row['blocks'][term][key])
            flat[f'{term}:{key}'] = value
        for key, value in scalar_details[term].items():
            near(value, row['details'][term][key])
            flat[f'detail:{term}:{key}'] = value
        near(math.fsum(scalar[term].values()), row['totals'][term])
        flat[term] = math.fsum(scalar[term].values())
    near(math.fsum(flat[term] for term in scalar), row['CDi_near'])
    near(row['CDi_near']+row['CDp'], row['CD'])
    for key in row['blocks']['bound']:
        flat[key] = math.fsum(scalar[term][key] for term in scalar)
    # Exploratory localization: bin ordered cross-beam finite-origin pairs by
    # their MAIN member's material distance to the nearest main-wing tip.
    # This was selected after the complete beam partition, not an acceptance
    # condition. Both ordered directions and both winglets are retained.
    localized = [0.]*(len(bin_edges)-1)
    contributions = [[] for _ in localized]
    for i in range(n):
        for j in range(n):
            if (beams[i] == 1) == (beams[j] == 1):
                continue
            main = i if beams[i] == 1 else j
            distance = max(0., 1.2426-abs(float(saved['t'][main])))
            k = next(k for k in range(len(localized)) if bin_edges[k] <= distance < bin_edges[k+1])
            contributions[k].append(float(saved['finite_origin'][i,j]))
    localized = [math.fsum(v) for v in contributions]
    near(math.fsum(localized), flat['finite_origin:main_from_winglet']+flat['finite_origin:winglet_from_main'])
    for k, value in enumerate(localized):
        flat[f'root_bin_{k}'] = value
    flat.update({key: row[key] for key in ('CD','CDp','CDi','CDi_near')})
    rows.append(dict(case=case, CL=row['CL'], values=flat))
    matrices[case['id']] = saved
    geometries[case['configuration'],case['main_intervals']] = saved

# Geometry and operator invariants at the common alpha=3 sample.
kernel_error = 0.
for count in (32,62):
    b = matrices[f'bare-main{count}-a12']; u = matrices[f'upper-main{count}-a12']
    for key in ('a','b','hv','ds','span','t'):
        assert np.array_equal(b[key],u[key][:count]), key
    for term in ('bound','half_wake','finite_origin'):
        kb = b[term]/np.outer(b['gamma'],b['gamma'])
        ku = u[term][:count,:count]/np.outer(u['gamma'][:count],u['gamma'][:count])
        kernel_error = max(kernel_error,float(np.max(abs(kb-ku))))
assert kernel_error < 2e-12
for key in ('a','b','hv','ds','span','t'):
    assert np.array_equal(geometries['upper',32][key][32:], geometries['upper',62][key][62:]),key


def sample(selected, target, coordinate):
    selected = sorted(selected,key=lambda row:row['case']['alpha'])
    x = lambda row: row['case']['alpha'] if coordinate == 'alpha' else row['CL']
    for row in selected:
        if x(row) == target:
            return dict(row['values']),[row['case']['alpha']]
    for a,b in zip(selected,selected[1:]):
        if x(a) < target < x(b):
            assert b['case']['alpha']-a['case']['alpha'] <= .25+1e-12
            w = (D(str(target))-D(str(x(a))))/(D(str(x(b)))-D(str(x(a))))
            return {key:float((1-w)*D(str(a['values'][key]))+w*D(str(b['values'][key]))) for key in a['values']},[a['case']['alpha'],b['case']['alpha']]
    raise AssertionError('No accepted adjacent bracket')


comparisons = {}
for name,target,coordinate in [('equal_CL',.5,'CL'),('equal_alpha',3.,'alpha')]:
    samples = {}; deltas = {}
    for count in (32,62):
        samples[str(count)] = {}
        for configuration in ('bare','upper'):
            selected = [row for row in rows if row['case']['main_intervals']==count and row['case']['configuration']==configuration]
            values,bracket = sample(selected,target,coordinate)
            samples[str(count)][configuration] = dict(values=values,alpha_bracket=bracket)
        pair = samples[str(count)]
        deltas[str(count)] = {key:pair['upper']['values'][key]-pair['bare']['values'][key] for key in pair['bare']['values']}
    change = {key:deltas['62'][key]-deltas['32'][key] for key in deltas['32']}
    near(sum(change[key] for key in ('bound','half_wake','finite_origin','CDp')),change['CD'])
    comparisons[name] = dict(target=target,coordinate=coordinate,samples=samples,deltas=deltas,change=change)

prior = read(ROOT/'artifacts/isae/sa11-same-mainwing-mesh-20261108/analysis.json')
change = comparisons['equal_CL']['change']
near(change['CD'],prior['change_in_drag_increment'])
for count,key in [('32','previous32'),('62','current62')]:
    near(comparisons['equal_CL']['deltas'][count]['CD'],prior[key]['actual_delta_CD'])
cross_finite = change['finite_origin:main_from_winglet']+change['finite_origin:winglet_from_main']
diagnosis = dict(
    total_drag_increment_change=change['CD'],
    shares_of_total_change_percent={key:100*change[key]/change['CD'] for key in ('bound','half_wake','finite_origin','CDp')},
    finite_origin_cross_beam_change=cross_finite,
    finite_origin_cross_beam_percent_of_total=100*cross_finite/change['CD'],
    within_125mm_cross_change=change['root_bin_0'],
    within_125mm_percent_of_cross_change=100*change['root_bin_0']/cross_finite,
    localization_scope='Exploratory signed accounting: main-member distance to the nearest main-wing tip. Does not prove singularity, a wrong vortex term, or a valid replacement.',
    next_action='Test main-tip source/receiver resolution on a matched frozen geometry; separate bound-line offset/receiver placement from changes in circulation. Do not remove finite-origin wakes or replace near-field drag with Trefftz.')
for path in (Path(__file__),OUT/'plan.json'):
    pins[str(path.relative_to(ROOT))] = sha(path)
reports = [read(OUT/c['id']/'report.json') for c in plan['cases']]
result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,pins=pins,
    comparisons=comparisons,diagnosis=diagnosis,root_distance_bin_edges_m=bin_edges,
    maximum_scalar_reduction_error=maximum_reduction_error,main_operator_identity_error=kernel_error,
    maximum_field_errors={key:max(r['errors'][key] for r in reports) for key in reports[0]['errors']},
    maximum_audit_seconds=max(r['seconds'] for r in reports),total_audit_seconds=sum(r['seconds'] for r in reports),
    peak_rss_kib=max(r['peak_rss_kib'] for r in reports),saved_states=9,physical_solves=0,
    primary_count=dict(passed=21,required=48,changed=False),original_count=dict(passed=1060,required=9184,changed=False),
    preparation_note='First preparation rejected the older COMPUTED_DIAGNOSTIC status label before output creation. The schema recognition was corrected; no physical state was computed, replaced or discarded.')
with (OUT/'analysis.json').open('x') as f:
    json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
signal.alarm(0)
print(json.dumps(dict(verified=True,diagnosis=diagnosis,maximum_scalar_reduction_error=maximum_reduction_error,
                     main_operator_identity_error=kernel_error,pins=len(pins)),indent=2))
