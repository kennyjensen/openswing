"""Distinguish ST-2 attachment interpretations without changing native inputs.

All derived models are explicit ASW decks with in-domain attachments. The
original printed fields and previously reviewed pylon model remain fixed.
One bounded physical solve per invocation; no solver is run by summarize.
"""
import argparse
from decimal import Decimal
from pathlib import Path
import resource
import time

import verify_sa14_defaults as common
from verify_st2_span_profile import BASE, FIELDS, printed_interval
from isae_st2_archive import COLUMNS

ROOT = common.ROOT
PRIOR = ROOT / 'artifacts/isae/st2-span-profile-20261109'
VARIANTS = ('tip_load', 'rigid_extension', 'elastic_massless', 'elastic_massive')


def prepare(out):
    prior = common.read(PRIOR/'plan.json')
    common.authenticate(prior['pins'])
    pins = dict(prior['pins'])
    for path in [Path(__file__), PRIOR/'plan.json', PRIOR/'summary.json']:
        pins[path.relative_to(ROOT).as_posix()] = common.sha(path)
    for i in (0, 1):
        folder = PRIOR/f'job-{i}'
        report = common.read(folder/'report.json')
        assert report['plan_sha256'] == common.sha(PRIOR/'plan.json')
        for name, digest in report['artifacts'].items():
            assert common.sha(folder/name) == digest
        for name in ('request.json', 'result.json', 'report.json'):
            path = folder/name
            pins[path.relative_to(ROOT).as_posix()] = common.sha(path)
    catalog = common.read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for entry in catalog['files']:
        if entry['id'] in ('isae-part-3', 'drela-steady'):
            for field, key in [('local_pdf', 'sha256'), ('local_text', 'text_sha256')]:
                assert common.sha(ROOT/entry[field]) == entry[key]
                pins[entry[field]] = entry[key]
    jobs = [dict(variant=v, nominal=n, extension_intervals=m, stride=s,
                 baseline_index=i)
            for v in VARIANTS
            for i, (n, m, s) in enumerate([(45, 2, 1), (90, 4, 2)])]
    common.write(out/'plan.json', dict(observed_utc=common.utc(), pins=pins,
        jobs=jobs, profile=prior['profile'], required_per_variant=368,
        computed_per_variant=276, unavailable_per_variant=92,
        limits=prior['limits'], mesh_peak_relative=.01,
        protocol='All original 46 stations and 368 fields retained separately per interpretation. '
        'Original main beam, 3kg total point load and chord arm .05m unchanged. '
        'tip_load moves physical y to .55; the other variants keep physical y=.558 '
        'and attach at the end of an explicit .008m beam joined rigidly to the main tip. '
        'rigid_extension is massless and infinitely stiff; elastic_massless copies '
        'original finite stiffness with zero mass; elastic_massive additionally copies '
        'the .3745kg/m mass. Main-beam modified-cosine meshes are unchanged. '
        'Original source and native out-of-domain policy are not modified or inferred. '
        'No alternative is selected or fitted to raise primary pass counts.'))
    print('Prepared eight serial states; primary scopes unchanged.')


def derived_source(variant):
    from isae_st2 import static_model, replace_weights
    from openswing.asw import parse_asw
    _, baseline, _ = static_model('bending', 0, 3., 'archive_pylon')
    if variant == 'tip_load':
        derived = replace_weights(baseline, [[1, .55, .05, .55, 0, 1.5*9.81]]*2)
    else:
        assert variant in VARIANTS
        rigid = variant == 'rigid_extension'
        eicc, gj, einn, ea = (0., 0., 0., 0.) if rigid else (4.4, 6.5, 3300., 9.6e6)
        mg = .3745*9.81 if variant == 'elastic_massive' else 0.
        derived = replace_weights(baseline, [[2, .558, .05, .558, 0, 1.5*9.81]]*2)
        derived += '\nJoint\n1 2 .55 .55 0\nEnd\nBeam 2\nExplicit tip extension\n'
        derived += 't x y z chord Xax EIcc GJ EInn EA mg\n'
        for station in (.55, .558):
            derived += ' '.join(format(v, '.17g') for v in
                [station, 0, station, 0, .1, .5, eicc, gj, einn, ea, mg])+'\n'
        derived += 't Cea Nea Cta Nta Ccg Ncg\n.55 0 0 0 0 0 0\n.558 0 0 0 0 0 0\nEnd\n'
    original_beam = baseline[baseline.index('Beam 1'):].strip()
    assert derived[derived.index('Beam 1'):].startswith(original_beam)
    model = parse_asw(derived)
    assert model.beams[0].domain == (.0001, .55)
    if variant != 'tip_load':
        assert model.beams[1].domain == (.55, .558)
    return model, derived


def run(out, index):
    plan = common.read(out/'plan.json'); common.authenticate(plan['pins'])
    job = plan['jobs'][index]; folder = out/f'job-{index}'; folder.mkdir()
    import numpy as np
    from openswing.bridge import dispatch
    from isae_st2 import observables
    model, source = derived_source(job['variant'])
    request = common.read(PRIOR/f"job-{job['baseline_index']}"/'request.json')
    request['source'] = source
    if len(model.beams) == 2:
        request['panels']['beams']['2'] = dict(count=job['extension_intervals'], spacing='uniform')
    (folder/'model.asw').write_text(source)
    common.write(folder/'request.json', request)
    started = time.monotonic(); result = dispatch(request); seconds = time.monotonic()-started
    common.write(folder/'result.json', result)
    nodes = sorted((n for n in result['nodes'] if n['beam'] == 1), key=lambda n:n['t'])
    assert len(nodes) == job['nominal']+1
    baseline = common.read(PRIOR/f"job-{job['baseline_index']}"/'result.json')
    assert [n['t'] for n in nodes] == [n['t'] for n in baseline['nodes']]
    all_nodes = {n['index']: n for n in result['nodes']}
    applied = np.zeros(3); moment = np.zeros(3); lengths = {b.index:0. for b in model.beams}
    for element in result['elements']:
        beam = element['beam']; lengths[beam] += element['length']
        density = .3745 if beam == 1 or job['variant'] == 'elastic_massive' else 0.
        force = np.array([0., 0., -9.81*density*element['length']/2])
        for trace in element['endpoint_traces']:
            node = all_nodes[trace['node']]
            applied += force; moment += np.cross(node['position'], force)
    last_beam = 1 if job['variant'] == 'tip_load' else 2
    tip = max((n for n in result['nodes'] if n['beam']==last_beam), key=lambda n:n['t'])
    point = np.asarray(tip['position']) + np.asarray(tip['rotation']) @ [.05, 0., 0.]
    point_force = np.array([0., 0., -3*9.81]); applied += point_force
    moment += np.cross(point, point_force)
    assert abs(lengths[1]-.55)<1e-12
    if last_beam == 2: assert abs(lengths[2]-.008)<1e-12
    checks = dict(residual=result['residual'],
        force_balance=float(np.max(abs(np.asarray(result['force_balance'])))),
        moment_balance=float(np.max(abs(np.asarray(result['moment_balance'])))),
        independent_force=float(np.max(abs(applied-result['applied_force']))),
        independent_moment=float(np.max(abs(moment-result['applied_moment']))),
        clamp_position=float(np.max(abs(np.asarray(nodes[0]['position'])))),
        clamp_rotation=float(np.max(abs(np.asarray(nodes[0]['rotation'])-np.eye(3)))))
    assert result['converged'] and max(checks.values()) < 1e-7
    traces = {tr['node']:tr for e in result['elements'] if e['beam']==1 for tr in e['endpoint_traces']}
    rows = []
    for i, row in enumerate(plan['profile']['rows']):
        node = nodes[i*job['stride']]; tr = traces[node['index']]
        target_t, half_t = printed_interval(row['fields']['t'])
        assert abs(Decimal.from_float(node['t'])-target_t)<=half_t
        obs = observables(node['position'],node['rotation'])
        values = {'y':node['position'][1], 'z-z0':node['position'][2]-node['jig_position'][2],
            'tw-tw0':obs['twist_asw_deg'], "Mc'/10":tr['moment_axes'][0],
            "Ms'/10":tr['moment_axes'][1], 'Fn/10':tr['force_local'][2]}
        for name in COLUMNS[1:]:
            target, tolerance = printed_interval(row['fields'][name]); value = values.get(name)
            error = abs(Decimal.from_float(value)-target) if value is not None else None
            gate = max(tolerance, Decimal('.05')*abs(target)) if abs(target)>Decimal('1e-8') else tolerance
            rows.append(dict(row=i, field=name, predicted=value, expected=float(target),
                expected_token=row['fields'][name]['token'], tolerance=float(tolerance),
                strict_passed=error is not None and error<=tolerance,
                passed=error is not None and error<=gate,
                error_percent=float(100*error/abs(target)) if error is not None and abs(target)>Decimal('1e-8') else None))
    equivalence = {key:float(np.max(abs(np.asarray([n[key] for n in nodes])-
                     np.asarray([n[key] for n in baseline['nodes']])))) for key in ('position','rotation')}
    if job['variant'] == 'rigid_extension': assert max(equivalence.values())<1e-9
    common.authenticate(plan['pins'])
    report = dict(observed_utc=common.utc(), job=job, checks=checks, rows=rows,
        main_beam_difference_from_pylon=equivalence, applied_force=result['applied_force'],
        passed=sum(r['passed'] for r in rows), strict_passed=sum(r['strict_passed'] for r in rows),
        required=368, computed=276, unavailable=92, seconds=seconds,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=common.sha(out/'plan.json'), artifacts={p.name:common.sha(p) for p in folder.iterdir()})
    common.write(folder/'report.json', report)
    print({k:v for k,v in report.items() if k not in ('rows','artifacts')})


def summarize(out):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);reports=[]
    for i, job in enumerate(plan['jobs']):
        folder=out/f'job-{i}';r=common.read(folder/'report.json')
        assert r['job']==job and r['plan_sha256']==common.sha(out/'plan.json')
        for name,digest in r['artifacts'].items():assert common.sha(folder/name)==digest
        reports.append(r)
    variants={}
    for variant in VARIANTS:
        coarse,fine=[r for r in reports if r['job']['variant']==variant]
        fields={}
        for field in FIELDS:
            a=[r for r in coarse['rows'] if r['field']==field]
            b=[r for r in fine['rows'] if r['field']==field]
            change=max(abs(x['predicted']-y['predicted']) for x,y in zip(a,b,strict=True))
            peak=max(abs(y['predicted']) for y in b)
            metric=change/max(peak,1e-12)
            fields[field]=dict(passed_both=sum(x['passed'] and y['passed'] for x,y in zip(a,b,strict=True)),
                strict_fine=sum(y['strict_passed'] for y in b), required=46,
                max_error_percent=max(y['error_percent'] or 0 for y in b),
                mesh_peak_percent=100*metric,mesh_pass=metric<plan['mesh_peak_relative'])
        assert all(v['mesh_pass'] for v in fields.values())
        variants[variant]=dict(passed_both=sum(v['passed_both'] for v in fields.values()), required=368,
            computed=276, unavailable=92,fields=fields,
            tip_rows=[r for r in fine['rows'] if r['row']==45],
            main_beam_difference_from_pylon=fine['main_beam_difference_from_pylon'],
            applied_force=fine['applied_force'])
    summary=dict(observed_utc=common.utc(),variants=variants,
        primary_scope_changed=False,primary_passes_added=0,native_attachment_policy_verified=False,
        production_changed=False,solver_seconds=sum(r['seconds'] for r in reports),
        peak_rss_kib=max(r['peak_rss_kib'] for r in reports),
        qualification='Independent alternative models, not combined counts or recovered historical input semantics. '
                      'Original point coordinates and main-beam samples distinguish the physical hypotheses.')
    common.write(out/'summary.json',summary)
    print({k:dict(passed=v['passed_both'],required=v['required'],fields=v['fields']) for k,v in variants.items()})


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','summarize'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    a=p.parse_args();common.bounded()
    if a.action=='prepare':prepare(a.output)
    elif a.action=='run':run(a.output,a.index)
    else:summarize(a.output)


if __name__=='__main__':main()
