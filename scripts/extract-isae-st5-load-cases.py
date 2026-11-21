#!/usr/bin/env python3
"""Extract two untouched ST-5 rigid-joint reference snapshots without physics.

This stdlib-only catalog uses the existing, independently checked selective
export rule, but reads each file's own exponents and verifies it again using
literal root geometry, root traction balance and all rear shell rows. It does
not import OpenSwing, select a spline, recover unprinted nodes or fit a load.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
RELATIVE = Path('3 - Structure/CASE - ST5 Joined Wing/Rigid_Joint')
CASES = ('JW_1_20lb_90_10', 'JW_1_30lb_90_10')
BASELINE = 'JW_1_20lb_80_20'
NAMES = ['t', 'x-x0', 'y', 'z-z0', 'phi', 'tw-tw0', 'psi', 'Mc_prime',
         'Ms_prime', 'Mn_prime', 'Fc', 'Fs', 'Fn', 'ux', 'uy', 'uz', 'wc',
         'ws', 'wn', 'eps', 'tau', 'chord', 'cl', 'cm', 'f_aero', 'f_reac',
         'da_eff', 'a_flap']
SCALED = {7, 8, 9, 10, 11, 12, 19, 20}
STRUCTURAL = list(range(1, 13)) + [19, 20]
CONDITIONAL = list(range(13, 19)) + [22, 24, 26, 27]


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def tables(path):
    """Literal table arithmetic only, preserving row locations and scales."""
    beams, beam, table = {}, None, None
    for line, text in enumerate(path.read_text().splitlines(), 1):
        words = text.split('#', 1)[0].split()
        if not words:
            continue
        if words[0] == 'Beam':
            beam = int(words[1]); beams[beam] = []; table = None
        elif words[0] == 'End':
            table = beam = None
        elif beam and words[0] == 't':
            table = dict(fields=words, header_line=line, offset=[0.] * len(words),
                         multiplier=[1.] * len(words), rows=[])
            beams[beam].append(table)
        elif table is not None:
            if words[0] in ('+', '*'):
                table['offset' if words[0] == '+' else 'multiplier'] = list(map(float, words[1:]))
            else:
                try:
                    values = list(map(float, words))
                except ValueError:
                    continue
                assert len(values) == len(table['fields']), (path, line)
                scaled = [x * m + a for x, m, a in zip(values, table['multiplier'], table['offset'])]
                table['rows'].append(dict(line=line, raw=values, scaled=scaled))
    return beams


def field_table(tab, beam, name):
    return next(t for t in tab[beam] if name in t['fields'])


def value(tab, beam, name, t):
    """Only literal knots or exactly two-point rear tables; never spline-fit."""
    table = field_table(tab, beam, name)
    col = table['fields'].index(name)
    t = abs(t)
    for row in table['rows']:
        if abs(row['scaled'][0] - t) < 1e-12:
            return row['scaled'][col]
    assert len(table['rows']) == 2, (beam, name, t)
    a, b = [row['scaled'] for row in table['rows']]
    w = (t - a[0]) / (b[0] - a[0])
    return a[col] + w * (b[col] - a[col])


def observations(path):
    lines = path.read_text().splitlines()
    blocks = []
    for i, line in enumerate(lines):
        match = re.search(r'Surface\s+Beam\s+(\d+):\s*(.*)', line)
        if not match:
            continue
        beam = int(match.group(1))
        exponents = [0] + list(map(int, lines[i + 1].split()))
        assert len(exponents) == 28
        scales = [10. ** e if j in SCALED else 1. for j, e in enumerate(exponents)]
        rows = []
        for k in range(i + 4, len(lines)):
            tokens = lines[k].split()
            if len(tokens) != 28 or not all(re.fullmatch(r'-?\d+\.\d{6}', x) for x in tokens):
                break
            raw = list(map(float, tokens))
            t = raw[0]
            exact, reason = None, None
            if t == 0:
                exact, reason = 0., 'literal mirrored root and rigid Ground'
            elif abs(abs(t) - 1.0005) < 1e-12:
                exact, reason = t, 'literal doubled control-property station'
            elif beam == 1 and abs(abs(t) - 2.001) < 2e-6:
                exact, reason = math.copysign(2.001, t), 'literal rigid joint; retain printed ordinate separately'
            elif abs(abs(t) - (3.335 if beam == 1 else 2.001)) < 1e-12:
                exact, reason = t, 'literal span endpoint'
            rows.append(dict(beam=beam, row=len(rows) + 1, source_line=k + 1,
                             raw_tokens=tokens, raw=raw, physical=[x * f for x, f in zip(raw, scales)],
                             historical_matlab=[x * 10. ** e for x, e in zip(raw, exponents)],
                             printed_t=t, exact_anchor_t=exact, anchor_reason=reason))
        duplicates = []
        for t in dict.fromkeys(row['printed_t'] for row in rows):
            group = [row for row in rows if row['printed_t'] == t]
            if len(group) > 1:
                duplicates.append(dict(printed_t=t, rows=[r['row'] for r in group],
                    source_lines=[r['source_line'] for r in group],
                    exact_anchor_t=group[0]['exact_anchor_t'],
                    differing_columns=[NAMES[j] for j in range(28) if len({r['raw'][j] for r in group}) > 1]))
        nodes = sorted({r['printed_t'] if r['exact_anchor_t'] is None else r['exact_anchor_t'] for r in rows})
        blocks.append(dict(beam=beam, name=match.group(2).strip(), row_count=len(rows),
                           header_line=i + 1, exponent_line=i + 2, header_exponents=exponents,
                           physical_multipliers=scales, printed_half_unit_by_column=[.5e-6 * f for f in scales],
                           rows=rows, duplicate_groups=duplicates, replay_nodes=nodes))
    return blocks


def frame(degrees):
    """Body columns c,s,n: direct transpose of primary steady Eq.4."""
    p, t, s = map(math.radians, degrees)
    cp, sp, ct, st, cs, ss = math.cos(p), math.sin(p), math.cos(t), math.sin(t), math.cos(s), math.sin(s)
    return [[ct*cs, -ss, st*cs], [ct*ss*cp+st*sp, cs*cp, st*ss*cp-ct*sp],
            [ct*ss*sp-st*cp, cs*sp, st*ss*sp+ct*cp]]


def mv(a, b):
    return [sum(x*y for x, y in zip(row, b)) for row in a]


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def shell_interval(tab, row, scales):
    t, v = row['printed_t'], row['physical']
    lo, hi = max(0., abs(t)-.5e-6), min(2.001, abs(t)+.5e-6)
    properties = {name: sorted((value(tab, 2, name, lo), value(tab, 2, name, hi)))
                  for name in ('EA', 'EIcc', 'EInn', 'Cshell', 'Nshell', 'Atshell')}
    wrench = {j: (max(0., abs(v[j])-.5e-6*scales[j]), abs(v[j])+.5e-6*scales[j]) for j in (7, 8, 9, 11)}
    p, w = properties, wrench
    eps = [w[11][0]/p['EA'][1] + p['Cshell'][0]*w[9][0]/p['EInn'][1] + p['Nshell'][0]*w[7][0]/p['EIcc'][1],
           w[11][1]/p['EA'][0] + p['Cshell'][1]*w[9][1]/p['EInn'][0] + p['Nshell'][1]*w[7][1]/p['EIcc'][0]]
    tau = [w[8][0]/(2*p['Atshell'][1]), w[8][1]/(2*p['Atshell'][0])]
    return eps, tau


def build_case(base, name, baseline, columns, *, expected_load_changes=None):
    model, output, driver = [base / (name + suffix) for suffix in ('.asw', '.txt', '.sh')]
    tab, blocks = tables(model), observations(output)
    checks = []
    def check(label, passed, **details):
        checks.append(dict(name=label, passed=bool(passed), **details))
    check('80 rows and 28 columns', [b['row_count'] for b in blocks] == [44, 36] and
          all(len(r['raw_tokens']) == 28 for b in blocks for r in b['rows']))
    script = driver.read_text().splitlines()
    check('named model and output; one solve', script[0].endswith(name + ' <<EOF') and
          script.count('x') == 1 and name + '.txt' in script)
    check('same original driver commands except basename', driver.read_text().replace(name, BASELINE) ==
          (base / (BASELINE + '.sh')).read_text())
    changes = []
    oldtab = tables(base / (BASELINE + '.asw'))
    for beam in (1, 2):
        for old, new in zip(oldtab[beam], tab[beam]):
            check(f'beam{beam}:table columns {new["header_line"]}', old['fields'] == new['fields'])
            check(f'beam{beam}:table row count {new["header_line"]}', len(old['rows']) == len(new['rows']))
            for col, prop in enumerate(new['fields']):
                before, after = [r['scaled'][col] for r in old['rows']], [r['scaled'][col] for r in new['rows']]
                if before != after:
                    changes.append(dict(beam=beam, property=prop, header_line=new['header_line'],
                                        old_multiplier=old['multiplier'][col], multiplier=new['multiplier'][col],
                                        old_values=before, values=after))
    if expected_load_changes is None:
        expected_load_changes = {(1, 'Dmg'), (2, 'Dmg'), (2, 'mg')}
        change_label = 'only three declared load-property changes'
    else:
        change_label = 'only declared load-property changes'
    check(change_label, {(x['beam'], x['property']) for x in changes} == set(expected_load_changes))
    check('rear self weight retained', field_table(tab, 2, 'mg')['multiplier'][1] == 1.1699)
    for b, old in zip(blocks, baseline):
        check(f'beam{b["beam"]}:printed station tokens match prior snapshot',
              [r['raw_tokens'][0] for r in b['rows']] == [r['raw_tokens'][0] for r in old['rows']])
        check(f'beam{b["beam"]}:constant channels zero', all(r['physical'][j] == 0 for r in b['rows'] for j in CONDITIONAL))
        check(f'beam{b["beam"]}:final seven display zeros', all(x == 0 for x in b['rows'][-1]['physical'][21:]))
        check(f'beam{b["beam"]}:known anchor mapping unchanged',
              [r['exact_anchor_t'] for r in b['rows']] == [r['exact_anchor_t'] for r in old['rows']])
        check(f'beam{b["beam"]}:finite values', all(math.isfinite(x) for r in b['rows'] for x in r['physical']))
    roots = {b['beam']: [r for r in b['rows'] if r['printed_t'] == 0] for b in blocks}
    d = [value(tab, 2, k, 2.001) - value(tab, 2, k, 0) for k in ('x', 'y', 'z')]
    phi, psi = math.degrees(math.atan2(d[2], d[1])), math.degrees(math.atan2(-d[0], math.hypot(d[1], d[2])))
    clamp = roots[2][1]['physical']
    check('raw rear clamp phi source evidence, not strict digit match', abs(clamp[4]-phi) < 6e-6,
          difference_deg=clamp[4]-phi, declared_diagnostic_limit_deg=6e-6)
    check('raw rear clamp psi source evidence, not strict digit match', abs(clamp[6]-psi) < 9e-6,
          difference_deg=clamp[6]-psi, declared_diagnostic_limit_deg=9e-6)
    for beam in (1, 2):
        root = roots[beam][0]['physical']
        for prop, col in [('chord', 21), ('Cm', 23)]:
            check(f'beam{beam}:raw root {prop}', root[col] == value(tab, beam, prop, 0))
        weight = -(value(tab, beam, 'mg', 0) + value(tab, beam, 'Dmg', 0))
        check(f'beam{beam}:raw root scalar signed weight', abs(root[25]-weight) <= .5e-6,
              original_value=root[25], literal_value=weight)
    alternatives = {}
    for mode in ('raw', 'historical_matlab', 'physical'):
        force, moment = [0.]*3, [0.]*3
        for beam in (1, 2):
            neg, pos = [r[mode] for r in roots[beam]]
            f = sub(mv(frame(pos[4:7]), pos[10:13]), mv(frame(neg[4:7]), neg[10:13]))
            m = sub(mv(frame(pos[4:7]), pos[7:10]), mv(frame(neg[4:7]), neg[7:10]))
            arm = cross([value(tab, beam, k, 0) for k in ('x', 'y', 'z')], f)
            force = [a+b for a, b in zip(force, f)]
            moment = [a+b+c for a, b, c in zip(moment, m, arm)]
        alternatives[mode] = dict(force_lb=force, moment_about_body_origin_lbft=moment)
    header = output.read_text().splitlines()[:28]
    header_values = {}
    for label in ('sum Fx', 'sum Fy', 'sum Fz', 'sum Mx', 'sum My', 'sum Mz', 'Weight'):
        token = re.search(re.escape(label)+r'\s*:\s*([-+\d.Ee]+)', '\n'.join(header)).group(1)
        header_values[label] = dict(token=token, value=float(token))
    for label, value_ in [('sum Fz', alternatives['physical']['force_lb'][2]),
                          ('sum My', alternatives['physical']['moment_about_body_origin_lbft'][1])]:
        check('selective root balance ' + label, abs(value_ - header_values[label]['value']) <= .005,
              decoded=value_, printed=header_values[label]['value'], printed_half_unit=.005)
    shells = []
    rear = blocks[1]
    for row in rear['rows']:
        bounds = shell_interval(tab, row, rear['physical_multipliers'])
        for col, interval in zip((19, 20), bounds):
            half = rear['printed_half_unit_by_column'][col]
            ok = interval[0] - half <= row['physical'][col] <= interval[1] + half
            check(f'rear row{row["row"]}:{NAMES[col]} propagated printing interval', ok)
            shells.append(dict(row=row['row'], source_line=row['source_line'], column=NAMES[col],
                               value=row['physical'][col], input_interval=interval, output_half_unit=half, overlap=ok))
    check('rear last strain and stress remain nodal/nonzero', all(rear['rows'][-1]['physical'][j] != 0 for j in (19, 20)))
    settings = dict(airflow_ft_per_s=0., density_slug_per_ft3=.002378, altitude_kft=0.,
                    mach=0., mach_pg=0., gravity_ft_per_s2=32.18, pose_angles_and_position=0.,
                    frame_velocity_rates_accelerations=0., flaps=[0.]*6,
                    evidence='Original output header lines4–27 and literal Constant lines34–37; driver has no setting override.',
                    mesh_request='No NODE command retained; coordinates exported to six decimal places only.',
                    executable='Aswing_R_5_92/bin/aswing is a path label, not recovered binary provenance.')
    # Keep every printed global/header field, including sign of zero, as source evidence.
    source_pins = [pin(base/(name+s)) for s in ('.asw', '.sh', '.txt', '.mat')]
    return dict(schema='st5-additional-original-output-target-v1', case=name,
        status='PASS_SOURCE_SUPPORTED_TARGET' if all(c['passed'] for c in checks) else 'FAIL_RETAINED',
        acceptance='Archived tested ASWING outputs; experimental agreement is optional.',
        source_commit=COMMIT, source_pins=source_pins, columns=columns, beams=blocks,
        header_lines=header, header_force_moment_weight=header_values, driver_lines=script,
        settings=settings, literal_changes_from_20lb80_20=changes,
        scale_policy='Use each file/beam printed exponent only for Mc_prime/Ms_prime/Mn_prime/Fc/Fs/Fn/eps/tau; all other columns raw. No blanket MATLAB conversion and no fixed multipliers copied from the earlier case.',
        root_balance_alternatives=alternatives, rear_shell_interval_checks=shells,
        checks=checks, checks_total=len(checks), checks_passed=sum(c['passed'] for c in checks))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--archive-dir', type=Path, default=ROOT / '.reference/isae-validation' / COMMIT / RELATIVE)
    args = parser.parse_args()
    stage, base = args.stage.resolve(), args.archive_dir.resolve()
    stage.mkdir(parents=True, exist_ok=False)
    oldpath = ROOT / 'docs/validation/isae-st5-reference-target.json'
    old = json.loads(oldpath.read_text())
    # Reuse names/units only. Old case-specific descriptions and scaling values
    # deliberately do not become a new case's evidence.
    columns = [dict(index0=i, index1=i+1, name=name, physical_unit=old['columns'][i]['physical_unit'],
                    location='coordinate' if i == 0 else 'nodal derived shell' if i in (19, 20) else
                    'following interval; final dummy' if i >= 21 else 'nodal') for i, name in enumerate(NAMES)]
    baseline = observations(base / (BASELINE + '.txt'))
    targets = [build_case(base, name, baseline, columns) for name in CASES]
    uncertainty = [
        'Interior unrounded historical stations are unavailable. Use printed centers and exact literal anchors, retaining both original coordinates. This is a finite-grid replay, not proof of identical historical node arrays.',
        'Positive forward joint prints2.000999 versus literal2.001; that difference exceeds the token half-unit. Do not enlarge output intervals or silently rewrite the archived coordinate.',
        'All duplicate rows retain sided state/resultants and zero-width display intervals; one unique computational vertex does not recreate an original zero-length element.',
        'Source policy drela-segspl-v1 plus drela-steady-section-v1 is explicit. Primary-generic zero-third interpolation is not proven by an original ASWING caller; loaded/unloaded-length and scalar EA averaging qualifications remain.',
        'Selective export scaling has independent literal geometry/balance/shell support, not recovered exporter source. All-zero channels cannot determine their nonzero-rate scaling.',
        'eps/tau are nodal here, including the nonzero last rear row; only the final seven columns have following-interval/final-dummy behavior.',
        'For chord/Cm use endpoint VALUE averages under the current source display evidence, including both sides at zero-width intervals; do not reuse the obsolete parameter-midpoint display rule.',
        'f_reac requires a separately labeled original-display comparison: the prior endpoint-weight and arithmetic-Euler-normal hypothesis is not a proven universal exporter law. Preserve this channel and every failure rather than relabel it solved.',
        'Global traction sums compare about body origin; Xmom is a coefficient reference, not evidence for moving this sum. Tiny printed residual components are diagnostics, not loads to fit.',
        'No matching startup .set/.pnt/.con or original binary is retained. The output directly establishes the no-flow static state; internal solver/startup and mesh policies remain unknown.',
        'Both new literals include rear mg multiplier1.1699, unlike the old80/20 target. Preserve signed distributed loads exactly and do not normalize to filenames or experimental labels.',
    ]
    for target in targets:
        target['uncertainties'] = uncertainty
        target['proposed_comparison'] = dict(
            policy={'beam_interpolation':'drela-segspl-v1','structural_operator':'drela-steady-section-v1'},
            structural_indices0=STRUCTURAL, structural_values=1120,
            conditional_zero_indices0=CONDITIONAL, conditional_zero_values=800,
            input_echo_indices0=[21,23], input_echo_values=160,
            scalar_weight_display_index0=25, scalar_weight_values=80,
            coordinate_index0=0, coordinate_values=80, all_exported_tokens=2240,
            reference_gate='Original half-last-place intervals per column/beam, unchanged and descriptive; no engineering pass band or fitted data.',
            physics_gate='Reuse existing source static fresh-residual/balance/clamp/rigid-joint gates; root freezes executable protocol separately.',
            replay='First use original-output stations with exact literal anchors:38/32 intervals; optionally76/64 and152/128 nested bisections separately from archive agreement.',
            global_scope='Retain every original header line; compare total signed weight, all six root force/moment sums and declared metadata; no-flow derived quantities remain conditional, not independent aerodynamic validation.')
        write(stage / (target['case'] + '-target.json'), target)
        with (stage / (target['case'] + '-rows.csv')).open('w', newline='') as f:
            w = csv.writer(f); w.writerow(['beam','row','source_line','printed_t','exact_anchor_t']+NAMES)
            for b in target['beams']:
                for r in b['rows']:
                    w.writerow([b['beam'],r['row'],r['source_line'],r['printed_t'],r['exact_anchor_t']]+r['physical'])
    pins = [pin(Path(__file__)),pin(oldpath)] + [pin(base/(BASELINE+s)) for s in ('.asw','.sh','.txt')]
    pins += [pin(base / n) for n in ('extract_local_distribution_data.m','Rigid_joint.m')]
    pins += [pin(ROOT/'.reference'/n) for n in ('aswing_doc.txt','asw_theory.txt','version_notes.txt')]
    report = dict(status='PASS_TWO_ORIGINAL_STATIC_TARGETS' if all(t['status'].startswith('PASS') for t in targets) else 'FAIL_RETAINED',
        checks_total=sum(t['checks_total'] for t in targets), checks_passed=sum(t['checks_passed'] for t in targets),
        targets=[pin(stage/(n+'-target.json')) for n in CASES], pins=pins,
        decision='Both unchanged originals qualify for the same explicitly scoped source-policy replay. Exact historical unrounded-node equivalence does not follow.',
        preferred_first=CASES[0], reason='20lb90/10 isolates distribution and rear self-weight changes at the same nominal load;30lb90/10 then adds load amplitude without changing stiffness/geometry.',
        source_urls=['https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/'+COMMIT+'/3%20-%20Structure/CASE%20-%20ST5%20Joined%20Wing/Rigid_Joint',
                     'https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf','https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt'],
        uncertainties=uncertainty, operations={'production_imports':0,'physics_calls':0,'solves':0,'residuals':0,'kernel_edits':0},
        no_old_artifacts_modified=True)
    write(stage/'report.json',report)
    print(json.dumps(dict(status=report['status'],checks_passed=report['checks_passed'],checks_total=report['checks_total'],report=pin(stage/'report.json'),targets=report['targets'])))
    if not report['status'].startswith('PASS'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
