"""Structural modes reconstructed from Durrant (2024), with setup gaps retained.

This is a table reconstruction, NOT the thesis's exact ASWING input. The
independent Hermite/linear finite elements below check the unloaded continuum
limit without using OpenSwing geometry, beam, inertia or modal implementations.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from scipy.linalg import eigh
from scipy.optimize import linear_sum_assignment
from openswing.asw import parse_asw
from openswing.linear_dynamics import make_system, linearize, eigensystem

REFERENCE = ROOT/'docs/validation/durrant-reference.json'


def properties(wing, variant='tables'):
    ref = json.loads(REFERENCE.read_text())
    entry = ref['wings'][str(wing)]
    if variant == 'tables':
        data = dict(entry['tables'])
    elif variant == 'appendix_distributed':
        raw = entry['appendix']
        inertia = np.array(raw['raw_inertia'])
        inertia[:, [0, 3, 4]] *= raw['mass_multiplier']
        inertia[:, 1] += raw['Ccg_offset_m']
        data = dict(stiffness=raw['stiffness'], inertia=inertia.tolist(),
                    Xax=raw['Xax'], Cea_m=0., Nea_m=raw['Nea_m'])
    else:
        raise ValueError('Unknown reconstruction variant')
    return ref, data


def configuration(spec):
    ref, data = properties(spec['wing'], spec.get('variant', 'tables'))
    common = ref['common']
    length, chord = common['length_m'], common['chord_m']
    nea = spec.get('nea', data['Nea_m'])
    variant = spec.get('variant', 'tables')
    # Start t at 1 so the single cantilever is not implicitly mirrored.
    boundaries = 1+np.r_[0., np.cumsum(common['segment_lengths_m'])]/length
    header = (f'# Reconstruction from Durrant 2024, DOI {ref["source"]["doi"]}\n'
              '# Source/setup conflicts: docs/validation/durrant-reference.json\n'
              '# No concentrated objects; this is not the original published input.\n'
              '# Vacuum structural study only; aerodynamic coefficients are not reconstructed.\n'
              f'Name\nDurrant {spec["wing"]} percent {variant} structural reconstruction\nEnd\n'
              'Units\nL 1 m\nT 1 s\nM 1 kg\nEnd\nConstant\n'
              f'{common["gravity_m_s2"]} {common["density_kg_m3"]} {common["sound_speed_m_s"]}\nEnd\n'
              f'Reference\n{length*chord:.15g} {chord} {length}\n0 0 0\nEnd\n'
              'Ground\n1 1 0\nEnd\nBeam 1\nWing\n'
              f't z chord Xax\n1 0 {chord} {data["Xax"]}\n2 {length} {chord} {data["Xax"]}\n'
              't EIcc EInn EIcn GJ Cea Nea\n')
    stiffness = ' '.join(map(str, [*data['stiffness'], data['Cea_m'], nea]))
    source = header+f'1 {stiffness}\n2 {stiffness}\nt mg Ccg Ncg mgcc mgnn\n'
    for lo, hi, row in zip(boundaries[:-1], boundaries[1:], data['inertia']):
        for t in (lo, hi):
            source += f'{t:.16g} '+ ' '.join(map(str, row))+'\n'
    return source+'End\n'


def continuum(spec, subdivisions=48, count=9, *, material=None):
    """Independent small-motion Rayleigh beam with bending/torsion coupling.

    Coordinates at a section are chord/normal displacements w_c,w_n of the
    elastic axis and twist phi. Rotations are (w_n',phi,-w_c') in c,s,n axes.
    The ASWING tension-axis offsets are zero. The reference-axis displacement
    is (w_c-Nea*phi,0,w_n+Cea*phi). Adding theta cross CG offset gives the three
    translational mass fields used below. Intrinsic centroidal rotary inertia
    is diag(mgcc,mgcc+mgnn,mgnn)/g. Bending energy is the coupled EIcc/EInn/EIcn
    form in (w_n'',-w_c''); torsion energy is GJ*phi'^2.

    Cubic Hermite bending and linear torsion are integrated using six-point
    Gauss quadrature. This unloaded reference has no aerodynamic apparent mass,
    gravity prestress, concentrated accelerometers, damping or fitted values.
    """
    ref, data = properties(spec['wing'], spec.get('variant', 'tables'))
    if material is not None:
        data = material
    g = ref['common']['gravity_m_s2']
    lengths = ref['common']['segment_lengths_m']
    L = sum(lengths)
    nea, cea = spec.get('nea', data['Nea_m']), data['Cea_m']
    # Resolve every material boundary exactly; minimum one cell in short ends.
    counts = [max(1, int(np.ceil(subdivisions*h/L))) for h in lengths]
    nodes = 1+sum(counts)
    K, M = np.zeros((5*nodes, 5*nodes)), np.zeros((5*nodes, 5*nodes))
    components = [np.zeros_like(K) for _ in range(3)]
    xg, wg = np.polynomial.legendre.leggauss(6)
    EIcc, EInn, EIcn, GJ = data['stiffness']
    chord = ref['common']['chord_m']
    fluid_mass = spec.get('air_density', 0.)*np.pi*chord**2/4
    midchord = (.5-data['Xax'])*chord
    element = 0
    positions = [0.]
    for length, n, row in zip(lengths, counts, data['inertia']):
        h = length/n
        mass, ccg, ncg, icc, inn = np.asarray(row)/[g, 1, 1, g, g]
        for _ in range(n):
            ids = np.arange(5*element, 5*element+10)
            for xi, weight in zip((xg+1)/2, wg*h/2):
                H = np.array([1-3*xi**2+2*xi**3, h*(xi-2*xi**2+xi**3),
                              3*xi**2-2*xi**3, h*(-xi**2+xi**3)])
                D = np.array([(-6*xi+6*xi**2)/h, 1-4*xi+3*xi**2,
                              (6*xi-6*xi**2)/h, -2*xi+3*xi**2])
                B = np.array([(-6+12*xi)/h**2, (-4+6*xi)/h,
                              (6-12*xi)/h**2, (-2+6*xi)/h])
                wc, wn, dc, dn, bc, bn, phi, dp = np.zeros((8, 10))
                ci, ni = [0, 1, 5, 6], [2, 3, 7, 8]
                wc[ci], dc[ci], bc[ci] = H, D, B
                wn[ni], dn[ni], bn[ni] = H, D, B
                phi[[4, 9]], dp[[4, 9]] = [1-xi, xi], [-1/h, 1/h]
                v = np.array([wc+(ncg-nea)*phi, -ccg*dc-ncg*dn,
                              wn-(ccg-cea)*phi])
                theta = np.array([dn, phi, -dc])
                Me = mass*v.T@v+theta.T@np.diag([icc, icc+inn, inn])@theta
                # Optional still-air thin-plate inertia; no circulation stiffness
                # or damping. This sensitivity is not an ASWING run setting.
                fluid_normal = wn+(cea-midchord)*phi
                Me += fluid_mass*(np.outer(fluid_normal, fluid_normal)+chord**2/32*np.outer(phi, phi))
                terms = [EIcc*np.outer(bn, bn), EInn*np.outer(bc, bc), GJ*np.outer(dp, dp)]
                Ke = sum(terms)-EIcn*(np.outer(bn, bc)+np.outer(bc, bn))
                K[np.ix_(ids, ids)] += weight*Ke
                M[np.ix_(ids, ids)] += weight*Me
                for total, term in zip(components, terms):
                    total[np.ix_(ids, ids)] += weight*term
            element += 1
            positions.append(positions[-1]+h)
    # Clamp all five degrees at s=0. eigh returns the lowest physical frequencies.
    values, vectors = eigh(K[5:, 5:], M[5:, 5:], subset_by_index=[0, count-1])
    if np.any(values <= 0):
        raise ValueError('Independent reference contains a nonpositive frequency')
    shapes = np.vstack([np.zeros((5, count)), vectors])
    energies = np.array([[v@c@v for c in components] for v in shapes.T])
    labels = classify(energies)
    return dict(subdivisions=subdivisions, elements=element, air_density=spec.get('air_density', 0.),
                frequencies_Hz=(np.sqrt(values)/(2*np.pi)).tolist(), labels=labels,
                energy_fractions=(energies/energies.sum(axis=1)[:, None]).tolist(),
                span_m=positions, shapes=shapes.T.reshape(count, nodes, 5).tolist())


def reference_check():
    """Check the independent FE mass/stiffness against uniform torsion waves."""
    ref, data = properties('25')
    g, L = ref['common']['gravity_m_s2'], ref['common']['length_m']
    material = dict(data, Cea_m=0., Nea_m=0., inertia=[[.1*g, 0., 0., 2e-5*g, 3e-5*g]]*3)
    exact = np.arange(1, 6, 2)/(4*L)*np.sqrt(material['stiffness'][3]/5e-5)
    errors = []
    for n in (48, 96):
        c = continuum(dict(wing='25'), n, count=12, material=material)
        values = [v for v, e in zip(c['frequencies_Hz'], c['energy_fractions']) if e[2] > .999]
        error = abs(np.array(values[:3])/exact-1)
        if len(values) < 3 or max(error) > .002:
            raise ValueError('Independent torsion reference does not recover analytic waves')
        errors.append(error)
    if not np.all(errors[1] < .3*errors[0]):
        raise ValueError('Independent torsion mesh refinement does not converge quadratically')
    return dict(exact_frequencies_Hz=exact.tolist(), relative_errors=np.array(errors).tolist())


def compare_shapes(case, reference):
    """Match physical shapes, including rotation, without using published roots."""
    _, data = properties(case['spec']['wing'], case['spec'].get('variant', 'tables'))
    nea = case['spec'].get('nea', data['Nea_m'])
    cea = data['Cea_m']
    x = np.array(case['jig_span_m'])
    sr = np.array(reference['span_m'])
    ref_shapes = []
    for shape in np.array(reference['shapes']):
        rows = []
        for s in x:
            j = int(np.clip(np.searchsorted(sr, s, side='right')-1, 0, len(sr)-2))
            h = sr[j+1]-sr[j]
            xi = np.clip((s-sr[j])/h, 0., 1.)
            H = np.array([1-3*xi**2+2*xi**3, h*(xi-2*xi**2+xi**3),
                          3*xi**2-2*xi**3, h*(-xi**2+xi**3)])
            D = np.array([(-6*xi+6*xi**2)/h, 1-4*xi+3*xi**2,
                          (6*xi-6*xi**2)/h, -2*xi+3*xi**2])
            wc, dc = H@shape[j:j+2, :2].ravel(), D@shape[j:j+2, :2].ravel()
            wn, dn = H@shape[j:j+2, 2:4].ravel(), D@shape[j:j+2, 2:4].ravel()
            phi = (1-xi)*shape[j, 4]+xi*shape[j+1, 4]
            rows.append([wc-nea*phi, -wn-cea*phi, 0., dn, dc, phi])
        ref_shapes.append(rows)
    # Trapezoidal span metric, with rotations scaled by chord to match lengths.
    w = np.r_[np.diff(x)[0]/2, (x[2:]-x[:-2])/2, np.diff(x)[-1]/2]
    chord = json.loads(REFERENCE.read_text())['common']['chord_m']
    metric = np.sqrt(w)[:, None]*np.array([1., 1., 1., chord, chord, chord])
    r = (np.array(ref_shapes)*metric).reshape(len(ref_shapes), -1)
    q = (np.array([np.array(s['real'])+1j*np.array(s['imag']) for s in case['shapes']])*metric).reshape(len(case['shapes']), -1)
    mac = abs(q.conj()@r.T)**2/np.sum(abs(q)**2, axis=1)[:, None]/np.sum(r**2, axis=1)[None, :]
    rows, cols = linear_sum_assignment(1-mac)
    if not np.array_equal(rows, np.arange(len(q))):
        raise ValueError('Incomplete independent shape assignment')
    expected = np.array(reference['frequencies_Hz'])[cols]
    return dict(reference_indices=cols.tolist(), modal_assurance=mac[rows, cols].tolist(),
                reference_frequencies_Hz=expected.tolist(),
                relative_frequency_error=(np.array(case['frequencies_Hz'])/expected-1).tolist())


def classify(energies):
    families = ['flap', 'chord', 'torsion']
    counts = dict.fromkeys(families, 0)
    result = []
    for e in energies:
        family = families[int(np.argmax(e))]
        counts[family] += 1
        result.append(f'{family}_{counts[family]}')
    return result


def compute(spec):
    start = time.monotonic()
    source = configuration(spec)
    n = spec['panels']
    mesh = dict(default=n, beams={'1': dict(count=n, spacing='uniform')})
    gravity = [0., 0., -spec.get('gravity', 0.)]
    system, _ = make_system(parse_asw(source), panels=mesh, gravity=gravity)
    a, m = linearize(system, step=spec.get('step', 1e-5))
    # The dense rank reduction flags ambiguous weak inertia in this thin wing.
    # Use the existing full-pencil search, retaining those inertias and the
    # original residual checks; do not relax its rank threshold.
    modes, metadata = eigensystem(a, m, time_scale=system.W, count=24,
                                  method='full_shift_invert', shift=spec.get('shift', [-.01, 0.]))
    positive = sorted((d for d in modes if d['eigenvalue'][1] > 1e-3),
                      key=lambda d: d['eigenvalue'][1])[:9]
    if len(positive) != 9:
        raise ValueError('Expected nine positive-frequency cantilever modes')
    roots = np.array([d['eigenvalue'] for d in positive])
    if max(abs(roots[:, 0])) > 1e-5:
        raise ValueError('Undamped structural reconstruction has unexplained growth/decay')
    residual = max(max(d['right_backward_error'], d['left_backward_error']) for d in positive)
    if residual > 1e-9:
        raise ValueError('Modal pencil residual exceeds tolerance')
    network = system.network
    # This vertical straight wing has c=+x, s=+z, n=-y in the jig.
    # These energies classify shapes only; the independent FE comparison above
    # supplies the physical reference, rather than this diagnostic extraction.
    _, data = properties(spec['wing'], spec.get('variant', 'tables'))
    EIcc, EInn, _, GJ = data['stiffness']
    energies, shapes = [], []
    for mode in positive:
        shape = mode['right'][:6*network.nn].reshape(network.nn, 6).copy()
        shape[:, :3] *= system.L
        span = network.rj[:, 2]
        gradients = np.diff(shape[:, 3:], axis=0)/np.diff(span)[:, None]
        energy = np.sum(abs(gradients)**2*np.diff(span)[:, None], axis=0)
        energies.append([EIcc*energy[0], EInn*energy[1], GJ*energy[2]])
        shapes.append(dict(real=shape.real.tolist(), imag=shape.imag.tolist()))
    energies = np.array(energies)
    base = system.base_report()
    return dict(spec=spec, source=source, actual_elements=network.ne,
                frequencies_Hz=(roots[:, 1]/(2*np.pi)).tolist(), roots_per_s=roots.tolist(),
                labels=classify(energies), energy_fractions=(energies/energies.sum(axis=1)[:, None]).tolist(),
                jig_span_m=network.rj[:, 2].tolist(), shapes=shapes,
                max_pencil_backward_error=residual,
                base_residual=base['modal_base']['continuous_residual'],
                mass_properties=base['mass_properties'],
                finite_dimension=metadata['finite_dimension'], elapsed_seconds=time.monotonic()-start)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels', nargs='+', type=int, default=[8, 16, 32])
    parser.add_argument('--wings', nargs='+', choices=['25', '75'], default=['25', '75'])
    parser.add_argument('--baseline-only', action='store_true')
    args = parser.parse_args()
    files = [Path(__file__), REFERENCE, *sorted((ROOT/'openswing').glob('*.py'))]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    provenance = dict(source_sha256=hashes, versions=dict(python=platform.python_version(),
                      numpy=np.__version__, scipy=scipy.__version__))
    key = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()
    cache = ROOT/'.reference/durrant-structure'/key
    cache.mkdir(parents=True, exist_ok=True)
    specs = []
    for wing in args.wings:
        for n in args.panels:
            specs.append(dict(wing=wing, panels=n))
        if not args.baseline_only:
            for extra in [dict(step=3e-6), dict(shift=[-.3, 100.]), dict(gravity=9.805),
                          dict(nea=.005), dict(variant='appendix_distributed')]:
                specs.append(dict(wing=wing, panels=16, **extra))
    cases = []
    for spec in specs:
        name = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        path = cache/f'{name}.json'
        if not path.exists():
            result = compute(spec)
            path.write_text(json.dumps(result, allow_nan=False)+'\n')
        result = json.loads(path.read_text())
        cases.append(result)
        print(spec, result['frequencies_Hz'], flush=True)
    references = {wing: [continuum(dict(wing=wing), n) for n in (48, 96, 192)] for wing in args.wings}
    still_air = {wing: continuum(dict(wing=wing, air_density=1.225), 192) for wing in args.wings}
    checks = dict(analytic_torsion=reference_check(), mesh={}, still_air_refinement={})
    for wing in args.wings:
        air96 = continuum(dict(wing=wing, air_density=1.225), 96)
        air_error = abs(np.array(still_air[wing]['frequencies_Hz'])/air96['frequencies_Hz']-1)
        if max(air_error) > .001:
            raise ValueError('Still-air sensitivity reference is insufficiently resolved')
        checks['still_air_refinement'][wing] = dict(coarse_frequencies_Hz=air96['frequencies_Hz'],
                                                  relative_change=air_error.tolist())
        independent = references[wing]
        refinement = abs(np.array(independent[-1]['frequencies_Hz'])/independent[-2]['frequencies_Hz']-1)
        if max(refinement) > .001:
            raise ValueError('Independent continuum reference is insufficiently resolved')
        baseline = sorted((c for c in cases if c['spec']['wing'] == wing and set(c['spec']) == {'wing', 'panels'}), key=lambda c: c['spec']['panels'])
        for c in baseline:
            c['continuum_comparison'] = compare_shapes(c, independent[-1])
        if [c['spec']['panels'] for c in baseline] == [8, 16, 32]:
            errors = np.array([abs(np.array(c['continuum_comparison']['relative_frequency_error'])) for c in baseline])
            if not np.all(errors[1:] < .4*errors[:-1]):
                raise ValueError('Structural frequencies do not converge toward the independent model')
            if min(baseline[-1]['continuum_comparison']['modal_assurance']) < .99:
                raise ValueError('Refined mode shapes disagree with the independent model')
            checks['mesh'][wing] = dict(relative_errors=errors.tolist(), reference_refinement=refinement.tolist())
        base16 = next((c for c in baseline if c['spec']['panels'] == 16), None)
        if base16 is not None:
            for c in cases:
                if c['spec']['wing'] != wing or c['spec']['panels'] != 16:
                    continue
                c['relative_change_from_baseline16'] = (np.array(c['frequencies_Hz'])/base16['frequencies_Hz']-1).tolist()
                if 'step' in c['spec'] or 'shift' in c['spec']:
                    if max(abs(np.array(c['relative_change_from_baseline16']))) > 2e-7:
                        raise ValueError('Root search or tangent-step sensitivity exceeds tolerance')
    output = dict(description='Unloaded vacuum structural table reconstruction, not exact ASWING or experimental validation.',
                  **provenance, reference=json.loads(REFERENCE.read_text()), cases=cases,
                  continuum=references, still_air_continuum=still_air, checks=checks,
                  complete_planned_grid=(args.panels == [8, 16, 32] and args.wings == ['25', '75'] and not args.baseline_only),
                  classification='Labels are inferred from dominant uncoupled strain energy; mixed modes are not identified with thesis labels by frequency rank alone.')
    target = ROOT/'docs/validation/durrant-structure.json'
    target.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(f'Wrote {target.relative_to(ROOT)}', flush=True)


if __name__ == '__main__':
    main()
