"""Separate circulation and geometry in the checked wing roll derivative."""
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT, read, pin
from daedalus_bounded_job import run
from check_daedalus_wing_velocity import STUDY, SEEDS, LABELS

SOURCES = [STUDY/'level-flight', STUDY/'pitch-balanced-v2']


def report(folder, args):
    import numpy as np
    from openswing.asw import parse_asw
    for source in SOURCES:
        terminal = read(source/'terminal.json')
        assert terminal['returncode'] == 0 and terminal['process_reaped'] and terminal['inputs_unchanged']
        for name, digest in read(source/'plan.json')['inputs_sha256'].items():
            path = Path(name)
            # The first run retains its pre-zero-thrust-adapter driver.
            if path.name == 'check_daedalus_wing_velocity.py':
                path = source/'runner.py'
            assert pin(path) == digest, path
    data = [dict(np.load(source/'arrays.npz')) for source in SOURCES]
    model = parse_asw((ROOT/'examples/dae.asw').read_text(), beam_interpolation='drela-segspl-v1')
    densities = [read(seed)['launch']['condition']['density'] for seed in SEEDS]
    assert densities[0] == densities[1]
    rho = model.constants[1] if densities[0] is None else densities[0]
    def ordinary_roll(gamma, d):
        row = np.zeros(d['local_velocity'].size)
        for j in range(3):
            df = (rho*gamma*d['length'])[:, None]*np.cross(-np.eye(3)[j], d['span'])
            roll = np.cross(d['lift_arm'], df)[:, 0]
            for nodes, weight in [(d['endpoints'][:, 0], 1-d['fractions']), (d['endpoints'][:, 1], d['fractions'])]:
                np.add.at(row, 3*nodes+j, weight*roll)
        return row
    for d in data:
        np.testing.assert_allclose(ordinary_roll(d['circulation'], d), d['physical_wrench_derivatives'][0, 3], atol=2e-14, rtol=1e-13)
    old, new = data
    np.testing.assert_array_equal(old['endpoints'], new['endpoints'])
    np.testing.assert_array_equal(old['fractions'], new['fractions'])
    dg = new['circulation']-old['circulation']
    mean = (new['circulation']+old['circulation'])/2
    circulation = (ordinary_roll(dg, old)+ordinary_roll(dg, new))/2
    geometry = ordinary_roll(mean, new)-ordinary_roll(mean, old)
    delta_components = new['physical_wrench_derivatives'][:, 3]-old['physical_wrench_derivatives'][:, 3]
    np.testing.assert_allclose(circulation+geometry, delta_components[0], rtol=1e-12, atol=2e-14)
    components = {'ordinary lift: circulation change':circulation,
                  'ordinary lift: geometry change':geometry,
                  **{label: row for label,row in zip(LABELS[1:],delta_components[1:])}}
    total = delta_components.sum(axis=0)
    directions = []
    encode = lambda z:dict(real=float(z.real), imag=float(z.imag), magnitude=float(abs(z)))
    for source, d in zip(SOURCES, data):
        expected = total@d['local_velocity']
        values = {label:row@d['local_velocity'] for label,row in components.items()}
        projections = {label:float(100*np.real(z*np.conj(expected))/abs(expected)**2) for label,z in values.items()}
        np.testing.assert_allclose(sum(projections.values()), 100, rtol=1e-12)
        directions.append(dict(velocity_response=source.name, total_change_lb_ft_per_F3=encode(expected),
            contributions={label:dict(**encode(z), signed_projection_percent=projections[label]) for label,z in values.items()}))
    integrals = [float(np.sum(d['circulation']*d['length'])) for d in data]
    return dict(comparisons=[read(source/'result.json') for source in SOURCES],
        directions=directions, circulation_integrals_ft3_s=integrals,
        integrated_circulation_change_percent=100*(integrals[1]/integrals[0]-1),
        qualification='Symmetric exact product identity: delta(Gamma G)=delta(Gamma)*mean(G)+mean(Gamma)*delta(G). Geometry includes length, span axis and moment arm. Projections concern a change of one wing-velocity roll-load term at fixed saved velocity; they are not error percentages, whole-aircraft moment fractions, or native setup recovery.')


if __name__ == '__main__':
    inputs = [ROOT/'scripts/check_daedalus_wing_velocity.py', ROOT/'examples/dae.asw', *SEEDS]
    for source in SOURCES:
        inputs.extend(source/name for name in ('arrays.npz', 'result.json', 'terminal.json', 'plan.json', 'runner.py'))
    run(STUDY, 'report', inputs, report, {}, __file__)
