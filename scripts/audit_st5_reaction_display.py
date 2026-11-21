"""Compare documented static normal loading with retained ST-5 f_reac tables.

Saved data only. Alternative display conventions do not add validation passes.
Run one four-case family per bounded serial invocation.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / 'docs/validation/isae-st5-mechanics-scope.json'
FORMS = (
    'scalar_parameter_midpoint', 'scalar_endpoint_average',
    'midpoint_weight_mean_normal', 'endpoint_weight_mean_normal',
    'endpoint_weight_unit_mean_normal', 'endpoint_weight_euler_mid_normal',
    'endpoint_projected_weight_average', 'midpoint_weight_euler_mid_normal',
)
FAMILIES = ('rigid', 'roller', 'forward', 'elliptical')


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def stamp(): return datetime.now(timezone.utc).isoformat()
def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def family(case):
    return next((kind for kind in FAMILIES[1:] if case.startswith('st5-'+kind+'-')), 'rigid')


def prepare(out):
    assert not out.exists()
    scope = read(SCOPE)
    assert sha(SCOPE) == 'b896edc1abfb8194cff98e6d3d3782dd7634e07e1ba17f92479d4046b48ad323'
    pins = {str(SCOPE): sha(SCOPE), str(Path(__file__).resolve()): sha(__file__)}
    catalog_path = ROOT / 'docs/validation/aswing-authoritative-sources.json'
    assert sha(catalog_path) == scope['authoritative_catalog_sha256']
    pins[str(catalog_path)] = sha(catalog_path)
    for ref in read(catalog_path)['files']:
        if ref['id'] in ('isae-part-3', 'drela-steady', 'drela-unsteady'):
            for path, expected in ((ref['local_pdf'], ref['sha256']), (ref['local_text'], ref['text_sha256'])):
                assert sha(ROOT/path) == expected; pins[str(ROOT/path)] = expected
    pins[str(ROOT/'reference/aswing_doc.txt')] = sha(ROOT/'reference/aswing_doc.txt')
    cases = []
    for entry in scope['cases']:
        path = ROOT/entry['reference_plan']; assert sha(path) == entry['reference_plan_sha256']
        plan = read(path); target = read(plan['target'])
        assert sha(plan['target']) == plan['target_sha256']
        for pin in target['source_pins']:
            assert sha(ROOT/pin['path']) == pin['sha256']; pins[str(ROOT/pin['path'])] = pin['sha256']
        for name, digest in plan['kernel_pins'].items():
            assert sha(ROOT/name) == digest; pins[str(ROOT/name)] = digest
        packet = path.parent/'run-0/level0/comparison.json'
        assert read(packet)['numerical_gates_pass']
        for p in (path, Path(plan['target']), packet): pins[str(p)] = sha(p)
        cases.append(dict(case=entry['case'], family=family(entry['case']), source=plan['source'],
                          target=plan['target'], comparison=str(packet)))
    out.mkdir()
    save(out/'plan.json', dict(observed_utc=stamp(), cases=cases, pins=pins, forms=FORMS,
        references=['ASWING user guide, spanwise variable 25: normal gravity/inertial/apparent load.',
                    'Steady theory Eq.78: distributed gravity force; Eqs.48-50: endpoint averaging.',
                    'Surface Euler frame: distinguish averaging transformations from averaging angles.'],
        physical_scope='Static file gravity, zero accelerations and airflow. No dynamic inference.',
        frames=['current saved deformation', 'decoded native angles with original jig twist'],
        hypotheses='Separate source-weight sampling, normal projection and display interpolation. Retain all alternatives, duplicates and final dummy rows; do not fit.',
        acceptance='Diagnostic 5% plus printed half-unit and strict printed precision both reported. No primary scope change.',
        limits=dict(address_space_bytes=512*1024**2,cpu_seconds=15,wall_seconds=25),
        solver_calls=0, primary_passes_added=0, production_changes=False))
    print(json.dumps(dict(prepared=16, families=FAMILIES, forms=FORMS, solver_calls=0)))


def check_pins(plan):
    for path, digest in plan['pins'].items(): assert sha(path) == digest, path


def run(out, group):
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    plan = read(out/'plan.json'); check_pins(plan)

    def angles(frame):
        r = np.asarray(frame); s = r[:,1]
        phi, psi = math.atan2(s[2],s[1]), -math.asin(float(np.clip(s[0],-1,1)))
        c0 = np.array([math.cos(psi),math.sin(psi)*math.cos(phi),math.sin(psi)*math.sin(phi)])
        n0 = np.array([0,-math.sin(phi),math.cos(phi)])
        return np.array([phi,math.atan2(-r[:,0]@n0,r[:,0]@c0),psi])

    def normal(q):
        phi, theta, psi = q
        return math.sin(theta)*np.array([math.cos(psi),math.sin(psi)*math.cos(phi),math.sin(psi)*math.sin(phi)]) + math.cos(theta)*np.array([0,-math.sin(phi),math.cos(phi)])

    def predictions(weight_a, weight_b, weight_mid, qa, qb):
        na, nb = normal(qa), normal(qb)
        mean = (na+nb)/2; unit = mean/np.linalg.norm(mean)
        euler = normal((qa+qb)/2); w = (weight_a+weight_b)/2
        return dict(zip(FORMS, map(float, (-weight_mid,-w,-weight_mid*mean[2],-w*mean[2],
            -w*unit[2],-w*euler[2],-(weight_a*na[2]+weight_b*nb[2])/2,-weight_mid*euler[2]))))

    results = []
    for entry in plan['cases']:
        if entry['family'] != group: continue
        model = parse_asw((ROOT/entry['source']).read_text(), beam_interpolation='drela-segspl-v1')
        packet, target = read(entry['comparison']), read(entry['target'])
        references = {r['source_line']:r for b in target['beams'] for r in b['rows']}
        beams = {b.index:b for b in model.beams}; rows = []
        for beam_id, beam in beams.items():
            current = [r for r in packet['rows'] if r['beam'] == beam_id]
            for i, row in enumerate(current):
                final = i == len(current)-1; following = row if final else current[i+1]
                a, b = row['t_evaluated'], following['t_evaluated']
                weight = lambda t: float(beam.value('mg',t)+beam.value('Dmg',t))
                wa, wb, wm = weight(a), weight(b), weight((a+b)/2)
                qa, qb = angles(row['frame']), angles(following['frame'])
                np.testing.assert_allclose(normal(qa),np.asarray(row['frame'])[:,2],atol=1e-14,rtol=0)
                np.testing.assert_allclose(normal(qb),np.asarray(following['frame'])[:,2],atol=1e-14,rtol=0)
                # The archived theta column is theta-theta_jig; other angles are absolute.
                native_a = np.radians(row['expected'][4:7]); native_b = np.radians(following['expected'][4:7])
                native_a[1] += angles(row['jig_frame'])[1]; native_b[1] += angles(following['jig_frame'])[1]
                values = {}
                for label,x,y in (('current',qa,qb),('native_angles',native_a,native_b)):
                    values[label] = {name:0. for name in FORMS} if final else predictions(wa,wb,wm,x,y)
                expected, half = row['expected'][25], row['half_last_place'][25]
                assert expected == references[row['source_line']]['physical'][25]
                rows.append(dict(beam=beam_id, source_line=row['source_line'], t=a, following_t=b,
                    row_kind='final_dummy' if final else 'zero_width' if a==b else 'ordinary',
                    expected=expected,half_last_place=half,weights=[wa,wb,wm],predictions=values))
        results.append(dict(case=entry['case'], rows=rows))
    assert len(results) == 4
    check_pins(plan)
    save(out/(group+'.json'),dict(observed_utc=stamp(),family=group,cases=results,solver_calls=0,primary_passes_added=0))
    print(json.dumps(dict(family=group,cases=4,rows=sum(len(c['rows']) for c in results),solver_calls=0)))


def summarize(out):
    plan = read(out/'plan.json');check_pins(plan)
    cases = [c for f in FAMILIES for c in read(out/(f+'.json'))['cases']]
    assert {c['case'] for c in cases} == {c['case'] for c in plan['cases']}
    metrics = []
    for frame in ('current','native_angles'):
        for form in FORMS:
            for kind in ('all','ordinary','zero_width','final_dummy'):
                rows = [r for c in cases for r in c['rows'] if kind=='all' or r['row_kind']==kind]
                errors = [abs(r['predictions'][frame][form]-r['expected']) for r in rows]
                relative = sorted(100*e/abs(r['expected']) for r,e in zip(rows,errors) if r['expected'])
                metrics.append(dict(frame=frame,form=form,rows=kind,count=len(rows),
                    strict_matches=sum(e<=r['half_last_place'] for r,e in zip(rows,errors)),
                    five_percent_matches=sum(e<=.05*abs(r['expected'])+r['half_last_place'] for r,e in zip(rows,errors)),
                    max_absolute_error=max(errors),max_relative_percent=max(relative,default=0),
                    median_relative_percent=relative[len(relative)//2] if relative else 0))
    result=dict(observed_utc=stamp(),cases=16,rows=sum(len(c['rows']) for c in cases),metrics=metrics,
                solver_calls=0,primary_passes_added=0,production_changes=False,
                qualification='Alternative display diagnostics; native-angle reconstruction is not an independent prediction. No finite-grid exporter identity is assumed.')
    save(out/'summary.json',result)
    print(json.dumps([m for m in metrics if m['rows']=='all'],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run','summarize'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--family',choices=FAMILIES)
    args=p.parse_args();out=args.output.resolve()
    if args.action=='run':
        assert args.family
        resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
        run(out,args.family)
    else: (prepare if args.action=='prepare' else summarize)(out)
