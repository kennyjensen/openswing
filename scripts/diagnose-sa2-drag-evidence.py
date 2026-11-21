"""Saved-only SA2 drag evidence; no production imports or aerodynamic solves.

The opposite-half substitution is a falsification diagnostic, not a proposed
force law. Original archived precision remains the comparison criterion.
"""
from pathlib import Path
from decimal import Decimal, localcontext
import datetime
import hashlib
import json
import math
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'artifacts/isae/sa2-force-decomposition-20261028'
OUT = ROOT / 'artifacts/isae/sa2-drag-evidence-20261029/report.json'
CHANNELS = ('lift', 'drag', 'CL', 'CD', 'CDi', 'Cm', 'efficiency')
# Consecutive decimal bounds on mathematical pi, not a fitted constant.
PI_LO = Decimal('3.141592653589793238462643383279502884197169399375105820974944592307816406286')
PI_HI = Decimal('3.141592653589793238462643383279502884197169399375105820974944592307816406287')


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def load(path):
    return json.loads(path.read_text())


def bounds(token):
    x = Decimal(token)
    h = Decimal('0.5') * Decimal(10) ** x.as_tuple().exponent
    return x-h, x+h


def compare(values, row):
    checks = []
    for name in CHANNELS:
        value = float(values[name])
        assert math.isfinite(value)
        token = row['tokens'][name]
        expected = Decimal(token)
        tolerance = Decimal('0.5') * Decimal(10) ** expected.as_tuple().exponent
        error = Decimal(str(value))-expected
        checks.append(dict(channel=name, native_token=token, native_line=row['line'],
                           predicted=value, signed_decimal_error=str(error),
                           original_print_tolerance=str(tolerance),
                           matches_printed_precision=abs(error) <= tolerance))
    return checks


def fsum_rows(array):
    return np.array([[math.fsum(map(float, row[:, j])) for j in range(3)] for row in array])


def main():
    started = time.monotonic()
    if OUT.exists():
        raise FileExistsError(f'Preserving existing evidence: {OUT}')
    paths = [Path(__file__).resolve(), ROOT/'.reference/isae-sa2/SA_2.asw',
             ROOT/'.reference/isae-sa2/SA_2.sh', ROOT/'.reference/isae-sa2/SA_2_CL.txt',
             ROOT/'.reference/asw_theory.txt', ROOT/'.reference/asw_theory.pdf',
             ROOT/'docs/validation/sa2.json', ROOT/'docs/validation/sa2.md',
             ROOT/'docs/validation/sa2-sources.json']
    paths += [OLD/name for name in ('protocol.json', 'run.py', 'run-receipt.json',
                                   'geometry.json', 'result.json', 'operators.npz',
                                   'analyze.py', 'analysis.json', 'summary.json')]
    before = [pin(p) for p in paths]
    polar = load(ROOT/'docs/validation/sa2.json')
    protocol, raw, geometry, prior = [load(OLD/n) for n in
                                     ('protocol.json', 'result.json', 'geometry.json', 'analysis.json')]
    with np.load(OLD/'operators.npz', allow_pickle=False) as stored:
        op = {key: stored[key].copy() for key in stored.files}
    # Historical code pins are evidence of the old producers, not claims about
    # today's worktree. Only immutable source/artifact pins are revalidated here.
    prior_pins = protocol['pins'] + prior['inputs']
    verified_prior = []
    for p in paths[1:]:
        if not (p.is_relative_to(ROOT/'.reference') or p.is_relative_to(OLD)):
            # Current documentation can incorporate later findings. Its fresh
            # pin is provenance, not an assertion of the old producer digest.
            continue
        matches = [q for q in prior_pins if q['path'] == str(p.relative_to(ROOT))]
        for q in matches:
            assert pin(p) == q, q['path']
            verified_prior.append(q['path'])
    model_lines = (ROOT/'.reference/isae-sa2/SA_2.asw').read_text().splitlines()
    def after_header(words):
        index = next(i for i, line in enumerate(model_lines) if line.split() == words)
        return model_lines[index+1].split()
    ref = list(map(Decimal, after_header(['#', 'Sref', 'Cref', 'Bref'])))
    rho_input = Decimal(after_header(['#', 'g', 'rhoSL', 'VsoSL'])[1])
    foil = after_header(['t', 'CLmin', 'CLmax', 'Cdf', 'Cdp'])
    cdf, cdp = float(foil[3]), float(foil[4])
    assert ref == list(map(Decimal, map(str, geometry['reference'][0])))
    assert cdf == protocol['literal']['Cdf'] and cdp == protocol['literal']['Cdp']
    rows = []
    for line_number, line in enumerate((ROOT/'.reference/isae-sa2/SA_2_CL.txt').read_text().splitlines(), 1):
        if not line.strip() or line.startswith('#'):
            continue
        tokens = line.split()
        assert len(tokens) == 10
        rows.append(dict(index=int(tokens[0]), line=line_number, raw_line=line,
                         alpha_token=tokens[2], tokens=dict(zip(CHANNELS, tokens[3:]))))
    assert [r['alpha_token'] for r in rows] == ['2.10000', '4.20000', '6.30000', '8.40000', '10.5000']
    polar_rows = []
    with localcontext() as ctx:
        ctx.prec = 80
        for index, row in enumerate(rows):
            name = f'current_fixed_zero/polar/200/{index}'
            candidates = [c for c in polar['cases'] if c['specification']['name'] == name]
            assert len(candidates) == 1 and candidates[0]['status'] == 'computed'
            case = candidates[0]
            spec, result = case['specification'], case['result']
            assert spec['panels'] == 200 and spec['mach'] == 0 and spec['freeze_influences'] is False
            assert Decimal(str(spec['alpha_deg'])) == Decimal(row['alpha_token'])
            for key in ('CL', 'CD', 'CDi', 'CDp', 'Cm'):
                assert math.isfinite(result[key])
            eb, db = bounds(row['tokens']['efficiency']), bounds(row['tokens']['CDi'])
            ar = ref[2]**2/ref[0]
            # Positive lift branch follows these positive-incidence native rows;
            # CYi=0 follows the conditional symmetric, zero-sideslip setup.
            cli = (PI_LO*ar*Decimal(row['tokens']['efficiency'])*Decimal(row['tokens']['CDi'])).sqrt()
            lo = (PI_LO*ar*eb[0]*db[0]).sqrt().next_minus()
            hi = (PI_HI*ar*eb[1]*db[1]).sqrt().next_plus()
            clb = bounds(row['tokens']['CL'])
            qbounds = {}
            for force, coefficient in (('lift', 'CL'), ('drag', 'CD')):
                fb, cb = bounds(row['tokens'][force]), bounds(row['tokens'][coefficient])
                qbounds[force] = [str(fb[0]/cb[1]), str(fb[1]/cb[0])]
            qs = rho_input*Decimal(str(protocol['condition']['speed']))**2*ref[0]/2
            assert all(Decimal(v[0]) <= qs <= Decimal(v[1]) for v in qbounds.values())
            gap = Decimal(row['tokens']['CD'])-Decimal(str(result['CD']))
            values = {key: result[key] for key in ('CL', 'CD', 'CDi', 'Cm')}
            polar_rows.append(dict(native=row, old_saved_case=name, old_saved_specification=spec,
                current_saved_coefficients=values, current_saved_profile_CD=result['CDp'],
                CD_native_minus_current=str(gap), gap_over_native_CDi=str(gap/Decimal(row['tokens']['CDi'])),
                native_CLi_inferred=str(cli), native_CLi_print_interval=[str(lo), str(hi)],
                native_CL_minus_CLi=str(Decimal(row['tokens']['CL'])-cli),
                native_CL_minus_CLi_print_interval=[str(clb[0]-hi), str(clb[1]-lo)],
                native_force_over_coefficient_qS_intervals=qbounds,
                original_reference_qS=str(qs)))
    checks = []
    def check(name, actual, expected, scale=1., gate=1e-10):
        x, y = np.asarray(actual), np.asarray(expected)
        assert x.shape == y.shape, name
        error = float(np.max(abs(x-y), initial=0.)/scale)
        checks.append(dict(name=name, normalized_error=error, gate=gate,
                           passed=bool(np.isfinite(x).all() and np.isfinite(y).all() and error <= gate)))
    g = {key: np.asarray(value) for key, value in geometry.items()}
    gamma = op['circulation']; n = len(gamma)
    assert n == 200 and all(np.isfinite(value).all() for value in op.values())
    for key in ('bound_hv', 'wake_hv', 'bound_cp', 'wake_cp', 'infinite_wake'):
        assert op[key].shape == (n, n, 3)
    ds, span, chord_axis = g['length'], g['frames'][:, :, 1], g['frames'][:, :, 0]
    check('physical_span_columns', (g['r1']-g['r0'])/ds[:, None], span)
    check('saved_Gamma_binding', gamma, [s['circulation'] for s in raw['strips']])
    half = np.sign(g['tm']); same = half[:, None] == half[None, :]
    assert np.array_equal(op['half_mask'], same) and np.array_equal(op['half'], half)
    e, up = g['wind'], g['lift']; rho = float(rho_input); speed = protocol['condition']['speed']
    area, cref, bref = map(float, ref); qs = .5*rho*speed**2*area
    velocity = speed*e+fsum_rows((op['bound_hv']+op['wake_hv'])*gamma[None, :, None])
    check('retained_HV_velocity', velocity, [s['relative_velocity'] for s in raw['strips']], speed)
    cp_velocity = speed*e+fsum_rows((op['bound_cp']+op['wake_cp'])*gamma[None, :, None])
    perpendicular = velocity-np.sum(velocity*span, axis=1)[:, None]*span
    normal_speed = np.linalg.norm(perpendicular, axis=1)
    check('retained_normal_speed', normal_speed, [s['normal_speed'] for s in raw['strips']], speed)
    tangent = np.sum(cp_velocity*g['frames'][:, :, 2], axis=1)
    chord = g['chord']; weight = rho*gamma*ds
    lift_force = weight[:, None]*np.cross(velocity, span)
    friction = .5*rho*np.linalg.norm(velocity, axis=1)[:, None]*velocity*(chord*cdf*ds)[:, None]
    pressure = .5*rho*normal_speed[:, None]*perpendicular*(chord*cdp*ds)[:, None]
    separation = 2*rho*perpendicular/normal_speed[:, None]*(tangent**2*chord*ds)[:, None]
    profile = friction+pressure+separation
    strip_force = lift_force+profile
    strip_moment = np.cross(g['rm']-g['reference'][1], strip_force)+np.cross((.25*chord)[:, None]*chord_axis, lift_force)
    force, moment = strip_force.sum(axis=0), strip_moment.sum(axis=0)
    check('retained_strip_forces', strip_force, [s['force'] for s in raw['strips']], qs)
    check('original_force', force, raw['force'], qs)
    check('original_moment', moment, raw['moment'], qs*cref)
    wake_velocity = fsum_rows(op['infinite_wake']*gamma[None, :, None])
    trace = np.cross(e, g['b']-g['a'])
    cdi = -.5*rho*math.fsum(map(float, gamma*np.sum(wake_velocity*trace, axis=1)))/qs
    cli = float((rho*speed*gamma[:, None]*trace).sum(axis=0)@up/qs)
    efficiency = cli**2/(math.pi*(bref**2/area)*cdi)
    base = dict(lift=float(force@up), drag=float(force@e), CL=float(force@up/qs),
                CD=float(force@e/qs), CDi=cdi, Cm=float(moment[1]/(qs*cref)), efficiency=efficiency)
    for name in ('CL', 'CD', 'CDi', 'Cm', 'efficiency'):
        check('original_'+name, base[name], raw[name])
    check('original_CLi', cli, raw['CLi'])
    check('original_CD_profile', float(profile.sum(axis=0)@e/qs), raw['CDp'])
    # Explicitly replace the entire opposite-half velocity vector in Eq67,
    # keeping the original Gamma, profile loads, control residual and all wake
    # outputs fixed. This is not an alternative equilibrium or physical result.
    dv = fsum_rows((.5*op['infinite_wake']-op['bound_hv']-op['wake_hv'])*
                   (~same)[:, :, None]*gamma[None, :, None])
    df = weight[:, None]*np.cross(dv, span)
    quarter_position = g['rm']+(.25*chord)[:, None]*chord_axis-g['reference'][1]
    dm = np.cross(quarter_position, df)
    delta_f, delta_m = df.sum(axis=0), dm.sum(axis=0)
    expected_drag_delta = -sum(value for key, value in prior['near_minus_far']['parts_N'].items() if key.endswith('opposite_half'))
    check('opposite_half_drag_matches_prior_partition', float(delta_f@e), expected_drag_delta, qs)
    hypothetical = dict(base)
    hypothetical.update(lift=base['lift']+float(delta_f@up), drag=base['drag']+float(delta_f@e),
                        CL=base['CL']+float(delta_f@up/qs), CD=base['CD']+float(delta_f@e/qs),
                        Cm=base['Cm']+float(delta_m[1]/(qs*cref)))
    original_checks, hypothetical_checks = compare(base, rows[2]), compare(hypothetical, rows[2])
    assert all(math.isfinite(v) for v in hypothetical.values())
    assert all(not c['matches_printed_precision'] for c in hypothetical_checks)
    for key in ('CL', 'Cm'):
        old_error = next(abs(Decimal(c['signed_decimal_error'])) for c in original_checks if c['channel'] == key)
        new_error = next(abs(Decimal(c['signed_decimal_error'])) for c in hypothetical_checks if c['channel'] == key)
        assert new_error > old_error
    after = [pin(p) for p in paths]
    assert before == after
    report = dict(format='sa2-saved-drag-evidence-v1', created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status='SAVED_ARITHMETIC_VERIFIED' if all(c['passed'] for c in checks) else 'ARITHMETIC_CHECK_FAILURE',
        operations=dict(aerodynamic_solves=0, production_imports=0, parameter_fits=0,
                        saved_polar_rows=5, saved_operator_states=1, algebraic_counterfactuals=1),
        preparation_history=[dict(attempt=1, terminal_exit=1, terminal_chunk='729d2f',
                                  stage='prior-pin classification', report_written=False,
                                  detail='An overbroad historical-pin check rejected subsequently updated docs/validation/sa2.md before arithmetic. Restricted that check to immutable originals and retained decomposition artifacts; current documentation remains freshly pinned. No physical evaluations occurred.')],
        source_pins=before, source_pins_unchanged=True, prior_immutable_pins_verified=sorted(set(verified_prior)),
        provenance=dict(full_polar='docs/validation/sa2.json: older producer, historical code digests retained in that file; not rerun with current kernel.',
                        full_polar_versions=polar['versions'], full_polar_historical_aero_sha256=polar['source_sha256']['openswing/aero.py'],
                        exact_field_state='20261028 force-decomposition result.json: current/PG0/alpha6.3/n200, independently replayed here; not conflated with older polar.',
                        exact_field_condition=protocol['condition'], current_kernel_executed=False),
        source_equations=[dict(path='.reference/asw_theory.txt', lines='770-806', page=16, equations='67,69,70',
                               interpretation='Full vector Kutta-Joukowski force at bound vortex; separate local profile forces.'),
                          dict(path='.reference/asw_theory.txt', lines='2474-2499', page=49, equations='207-211',
                               interpretation='Trefftz CLi, CDi and efficiency are separate functionals; infer positive CLi=sqrt(pi*(Bref^2/Sref)*e*CDi) conditionally on CYi=0.'),
                          dict(path='.reference/asw_theory.txt', lines='2687-2692', page=53, equations='220-221',
                               interpretation='Total aerodynamic force and moment integrate full applied lift/profile vectors.')],
        native_CLi_uncertainty=dict(method='Monotone interval evaluation of original e/CDi half-last-place bounds; CL-minus-CLi also propagates native CL rounding.',
                                    pi_interval=[str(PI_LO), str(PI_HI)], decimal_precision=80,
                                    reference_inputs='Literal Sref/Bref treated as exact input decimals; no inferred historical changes.',
                                    qualifications=['Conditional on documented Eq211 exporter convention, symmetric CYi=0 and positive lift branch.',
                                                    'Intervals propagate aggregate output rounding only; they do not recover native Gamma or historical settings.']),
        full_polar=polar_rows, saved_state_arithmetic_checks=checks,
        exact_field_original=dict(values=base, CLi=cli, CL_minus_CLi=base['CL']-cli,
                                  native_checks=original_checks,
                                  matches=sum(c['matches_printed_precision'] for c in original_checks)),
        opposite_half_counterfactual=dict(definition='V_hv += sum_opposite_j[(0.5*W_infinite-B_bound-W_semi)_ij*Gamma_j]; only Eq67 forces and their physical quarter-chord moments change.',
            qualification='Fixed-field algebra only; not an equilibrium, exporter reconstruction, production change, or proposed correction. Profile and Trefftz outputs remain original.',
            delta_force_N=delta_f.tolist(), delta_moment_Nm=delta_m.tolist(),
            delta_drag_N=float(delta_f@e), delta_lift_N=float(delta_f@up),
            values=hypothetical, CLi_unchanged=cli, CL_minus_CLi=hypothetical['CL']-cli,
            native_checks=hypothetical_checks, matches=sum(c['matches_printed_precision'] for c in hypothetical_checks),
            CL_and_Cm_disagreements_increase=True),
        interpretation=[
            'At the four lower incidences, missing total CD is approximately 8.8 percent of native CDi while saved profile CD is nearly constant. This is descriptive scaling, not a fitted correction.',
            'A missing constant profile-drag offset cannot reproduce that attached-range trend. This does not rule out every unobserved historical profile velocity or force-recovery convention.',
            'Removing the opposite-half near-minus-far drag term nearly closes drag alone, but applying the same vector operation worsens CL and Cm and fails all seven original printed targets.',
            'A drag-only opposite-half replacement is unsupported by Eqs67/220; the scalar coincidence does not establish a native policy.',
            'Near-field induced-force recovery remains the investigation priority. Native aggregate CDi agreement does not prove identical Gamma; historical finite load recovery remains unidentified.',
            'No registered scores, original targets, tolerances, coefficients, geometry, cores, or physics were changed.'],
        wall_seconds=time.monotonic()-started)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=report['status'], report=pin(OUT), checks=len(checks),
                          checks_passed=sum(c['passed'] for c in checks),
                          counterfactual=hypothetical, native_matches=report['opposite_half_counterfactual']['matches']), indent=2))
    if not all(c['passed'] for c in checks):
        sys.exit(1)


if __name__ == '__main__':
    main()
