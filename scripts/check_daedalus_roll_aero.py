"""Aerodynamic-only refinement at the mesh-sensitive 1.5 Hz roll response.

Reuse accepted steady circulation, verify it on the unchanged loaded structure,
solve new harmonic circulation, and conservatively transfer complete loads.
Projection is a first variation, not a retrimmed/refined aircraft response.
"""
import argparse
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from check_daedalus_aero_resolution import STUDY as OLD, ACCEPTED, refined_mesh_motion
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-roll-aero-20261114'
SAMPLES = ROOT/'artifacts/daedalus-mesh-zeros-20261114'
FREQUENCY = 1.5


class Trial:
    def __init__(self, factor):
        import numpy as np
        import scipy.sparse as sp
        from check_daedalus_wing_paper import dynamic
        from openswing.frequency_response import HarmonicInput
        self.system = system = dynamic(); self.n = n = system.network; self.factor = factor
        self.zero = np.zeros(system.size); self.omega = 2*np.pi*FREQUENCY
        assert system.size==2044 and n.ng==82 and not n.loads
        with np.load(SAMPLES/'coarse-samples/arrays.npz') as saved:
            index = int(np.argmin(abs(saved['frequencies']-FREQUENCY)))
            assert abs(saved['frequencies'][index]-FREQUENCY)<1e-14
            self.z = saved['states'][index]; self.output = saved['outputs'][index]
        a, m = (sp.load_npz(SOURCE/'assembled-6.7'/name) for name in ('A.npz', 'M.npz'))
        maps = np.load(SOURCE/'assembled-6.7/maps.npz')
        self.full_residual = float(max(abs((1j*self.omega*m-a)@self.z-maps['B'][:,0])))
        assert self.full_residual < 2e-10
        self.zdot = 1j*self.omega*self.z
        self.forcing, _ = HarmonicInput(system, 'control.3', 0).at_frequency(self.omega)
        self.engine_nodes = [n.node(*row[2:4]) for row in n.engines]
        self.sensor_nodes = [n.node(*row[1:3]) for row in n.model.records.get('sensor', [])]
        state, _, options = system.physical_state(self.zero, self.zero, None)
        residual, self.native_base = n.residual(state.x, detail=True, **options)
        assert max(abs(residual)) < 1e-9
        self.initial_gamma = state.gamma.copy(); self.calls = 0

    def evaluate(self, gamma, gamma_dot=None, *, part=None, amplitude=0., capture=False):
        import numpy as np
        from openswing.aero import evaluate_aerodynamics
        from openswing.structured_static import IterationFields
        system, n = self.system, self.n
        if part is None: state, _, options = system.physical_state(self.zero, self.zero, None)
        else:
            component = (np.real, np.imag)[part]
            state, _, options = system.physical_state(amplitude*component(self.z), amplitude*component(self.zdot), self.forcing(part, amplitude))
        fine, motion = refined_mesh_motion(n, state, options, self.factor)
        condition, _, _ = n.operating.apply(state.x[n.operating_start:],
            condition_override=options['condition_override'], motion_override=options['motion_override'])
        fields = IterationFields() if capture else None
        if fields is not None: fields.capture_circulation = True
        point_positions = n.point_positions(state.r, state.Q)
        engine_positions = [state.r[j]+state.Q[j]@(row[4:7]-n.rj[j]) for row, j in zip(n.engines, self.engine_nodes)]
        sensor_positions = [state.r[j]+state.Q[j]@(row[3:6]-n.rj[j]) for row, j in zip(n.model.records.get('sensor', []), self.sensor_nodes)]
        aero = evaluate_aerodynamics(n.model, condition, fine, gamma, point_positions,
            engine_positions, state.Q[self.engine_nodes], local_motion=motion, circulation_rate=gamma_dot,
            _iteration_fields=fields, sensor_positions=sensor_positions)
        aero = dict(aero, circulation_residual=np.asarray(aero['circulation_residual']))
        self.calls += 1
        return aero, fields, fine, state, options, point_positions


def shape(folder, args):
    import numpy as np
    from openswing.circulation_tangent import FlowDerivative, surface_derivatives
    trial = Trial(args['factor']); n = trial.n
    source = OLD/ACCEPTED[[1,2,4].index(args['factor'])]
    terminal = read(source/'terminal.json')
    assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
    with np.load(source/'arrays.npz') as saved:
        gamma = saved['gamma'].copy(); old_jac = saved['jacobian']; old_lag = saved['lag_diagonal']
    base, fields, meshes, *_ = trial.evaluate(gamma, capture=True)
    base_error = float(max(abs(base['circulation_residual']))); assert base_error < 1e-10
    data = fields.circulation_aero
    flow = FlowDerivative(SimpleNamespace(gamma_scale=1., ng=len(gamma), size=len(gamma)), fields, data)
    _, _, jac = surface_derivatives(data, flow, residual_only=True)
    speed = np.asarray([s['normal_speed'] for s in base['strips'] if s['lifting']])
    lag = -2/(np.pi*speed*data['condition'].speed)
    jac_replay = float(np.max(abs(jac-old_jac))); lag_replay = float(max(abs(lag-old_lag)))
    assert jac_replay < 2e-12 and lag_replay < 2e-15, (jac_replay, lag_replay)
    probe = np.sin(np.arange(len(gamma))+.3); h = 1e-4
    plus = trial.evaluate(gamma+h*probe)[0]['circulation_residual']
    minus = trial.evaluate(gamma-h*probe)[0]['circulation_residual']
    jac_probe = float(max(abs((plus-minus)/(2*h)-jac@probe)))
    plus = trial.evaluate(gamma, h*probe)[0]['circulation_residual']
    minus = trial.evaluate(gamma, -h*probe)[0]['circulation_residual']
    lag_probe = float(max(abs((plus-minus)/(2*h)-lag*probe)))
    assert max(jac_probe, lag_probe) < 2e-8
    if args['stage']=='shape_base':
        np.savez_compressed(folder/'arrays.npz', gamma=gamma, jacobian=jac,
            lag_diagonal=lag, full_state=trial.z)
        return dict(factor=args['factor'], panels=len(gamma), frequency_hz=FREQUENCY,
            aerodynamic_evaluations=trial.calls, reused_full_state_residual=trial.full_residual,
            steady_circulation_residual=base_error, saved_jacobian_error=jac_replay,
            saved_lag_error=lag_replay, jacobian_probe_error=jac_probe, lag_probe_error=lag_probe)
    shapes = []
    for width in (1e-3, 5e-4):
        value = np.zeros(len(gamma), complex)
        for part in (0, 1):
            for offset, weight in [(-2,1), (-1,-8), (1,8), (2,-1)]:
                sample = trial.evaluate(gamma, part=part, amplitude=offset*width)[0]['circulation_residual']
                value += (1 if part==0 else 1j)*weight*sample/(12*width)
        shapes.append(value)
    width_error = float(max(abs(shapes[0]-shapes[1]))); assert width_error < 2e-8
    operator = jac+1j*trial.omega*np.diag(lag)
    response = np.linalg.solve(operator, -shapes[-1])
    residual = float(max(abs(operator@response+shapes[-1]))); assert residual < 1e-10
    coarse_error = None
    if args['factor']==1:
        expected = trial.z[n.gamma_start:n.operating_start]*n.gamma_scale
        coarse_error = float(max(abs(response-expected))/max(abs(expected))); assert coarse_error < 2e-6
        np.testing.assert_allclose(gamma, trial.initial_gamma, atol=2e-8, rtol=2e-10)
    np.savez_compressed(folder/'arrays.npz', gamma=gamma, gamma_response=response,
        jacobian=jac, lag_diagonal=lag, shape_rhs=shapes[-1], full_state=trial.z)
    return dict(factor=args['factor'], panels=len(gamma), frequency_hz=FREQUENCY,
        aerodynamic_evaluations=trial.calls, reused_full_state_residual=trial.full_residual,
        steady_circulation_residual=base_error, saved_jacobian_error=jac_replay, saved_lag_error=lag_replay,
        jacobian_probe_error=jac_probe, lag_probe_error=lag_probe,
        shape_stencil_error=width_error, harmonic_circulation_residual=residual,
        coarse_response_relative_error=coarse_error,
        qualification='New 1.5 Hz harmonic circulation at prescribed original structural motion. The accepted stationary circulation is reused and verified; no trim or new aircraft response is solved.')


def accepted(tag):
    terminal = read(STUDY/tag/'terminal.json')
    assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
    return read(STUDY/tag/'result.json')


def shape_part(folder, args):
    import numpy as np
    trial = Trial(args['factor']); part = args['part']; assert part in (0,1)
    source = args['source'] or f"shape-{args['factor']}-base"
    base = accepted(source)
    with np.load(STUDY/source/'arrays.npz') as saved:
        gamma = saved['gamma']; np.testing.assert_array_equal(trial.z, saved['full_state'])
    shapes = []
    widths=(1e-3,5e-4) if args['width'] is None else (args['width'],)
    for width in widths:
        value = np.zeros(len(gamma))
        for offset, weight in [(-2,1),(-1,-8),(1,8),(2,-1)]:
            value += weight*trial.evaluate(gamma,part=part,amplitude=offset*width)[0]['circulation_residual']/(12*width)
        shapes.append(value)
    error = float(max(abs(shapes[0]-shapes[1]))) if len(shapes)==2 else None
    assert error is None or error<2e-8
    np.savez_compressed(folder/'arrays.npz', shapes=shapes, full_state=trial.z)
    return dict(factor=args['factor'], panels=base['panels'], frequency_hz=FREQUENCY,
        part=part, widths=list(widths), aerodynamic_evaluations=trial.calls, shape_stencil_error=error)


def shape_join(folder, args):
    import numpy as np
    factor = args['factor']; assert factor==4
    base = f'shape-{factor}-base'; result = dict(accepted(base))
    with np.load(STUDY/base/'arrays.npz') as saved:
        arrays = dict(saved)
    shapes = np.zeros((2,result['panels']),complex)
    for index,(label,width) in enumerate((('wide',1e-3),('fine',5e-4))):
        for part,name in enumerate(('real','imag')):
            tag = f'shape-{factor}-{name}-{label}'; r = accepted(tag)
            assert r['part']==part and r['frequency_hz']==FREQUENCY and r['factor']==factor and r['widths']==[width]
            with np.load(STUDY/tag/'arrays.npz') as saved:
                np.testing.assert_array_equal(saved['full_state'],arrays['full_state'])
                shapes[index] += (1 if part==0 else 1j)*saved['shapes'][0]
            result['aerodynamic_evaluations'] += r['aerodynamic_evaluations']
    error = float(max(abs(shapes[0]-shapes[1]))); assert error<2e-8
    operator = arrays['jacobian']+2j*np.pi*FREQUENCY*np.diag(arrays['lag_diagonal'])
    response = np.linalg.solve(operator,-shapes[-1])
    residual = float(max(abs(operator@response+shapes[-1]))); assert residual<1e-10
    np.savez_compressed(folder/'arrays.npz', **arrays, gamma_response=response, shape_rhs=shapes[-1])
    result.update(shape_stencil_error=error,harmonic_circulation_residual=residual,
        coarse_response_relative_error=None,
        qualification='Same harmonic-circulation calculation split into a base check and real/imaginary stencil jobs to keep the unchanged per-job resource caps.')
    return result


def loads(folder, args):
    import numpy as np
    from check_daedalus_load_sensitivity import groups
    trial = Trial(args['factor']); system, n = trial.system, trial.n
    source = STUDY/(args['source'] or f"shape-{args['factor']}"); record = read(source/'result.json')
    terminal = read(source/'terminal.json'); assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
    with np.load(source/'arrays.npz') as saved:
        gamma, response = saved['gamma'], saved['gamma_response']
        np.testing.assert_array_equal(trial.z, saved['full_state'])
    keys = [f'beam{mesh.beam.index}' for mesh in n.meshes]+['points_shoulders_engines']
    closure = 0.; native_error = 0.; native_evaluations = 0
    def sample(part=None, amplitude=0.):
        nonlocal closure, native_error, native_evaluations
        component = np.real if part is None else (np.real, np.imag)[part]
        circulation = gamma if part is None else gamma+amplitude*component(response)
        rate = np.zeros_like(gamma) if part is None else amplitude*component(1j*trial.omega*response)
        aero, _, fine, state, options, points = trial.evaluate(circulation, rate, part=part, amplitude=amplitude)
        coarse = n.deformed_meshes(state.r, state.Q, n.geometry(state.r, state.Q))
        values = []; wrenches = []
        def add(force, moment):
            wrench = np.r_[force.sum(axis=0), (moment+np.cross(state.r-n.model.reference[1], force)).sum(axis=0)]
            value = np.zeros(system.size)
            value[6*n.ne:6*n.ne+3*n.nn] = force.ravel()/n.F
            value[6*n.ne+3*n.nn:6*(n.ne+n.nn)] = moment.ravel()/(n.F*n.L)
            value[n.operating_start:n.size] = wrench/np.r_[np.full(3,n.F), np.full(3,n.F*n.L)]
            values.append(value); wrenches.append(wrench)
        for parent, child in zip(coarse, fine):
            strips = [s for s in aero['strips'] if s['beam']==parent.beam.index]
            force = np.array([s['force'] for s in strips]); moment = np.array([s['moment'] for s in strips])
            count = len(parent.tm); q = args['factor'] if parent.beam.lifting else 1
            assert len(force)==count*q
            f = force.reshape(count,q,3).sum(axis=1)
            arm = child.rm.reshape(count,q,3)-parent.rm[:,None,:]
            c = (moment.reshape(count,q,3)+np.cross(arm, force.reshape(count,q,3))).sum(axis=1)
            nf = np.zeros_like(state.r); nm = np.zeros_like(nf)
            for ids, ff, mm in n.steady_lifting_wrenches(parent, f, c):
                np.add.at(nf, ids, ff); np.add.at(nm, ids, mm)
            add(nf, nm)
            expected = np.r_[force.sum(axis=0), (moment+np.cross(child.rm-n.model.reference[1], force)).sum(axis=0)]
            np.testing.assert_allclose(wrenches[-1], expected, atol=2e-10, rtol=2e-11)
            closure = max(closure, float(max(abs(wrenches[-1]-expected))))
        nf = np.zeros_like(state.r); nm = np.zeros_like(nf)
        def point(node, position, force, moment):
            nf[node] += force; nm[node] += moment+np.cross(np.asarray(position)-state.r[node], force)
        for row, position, force in zip(n.weights, points, aero['point_forces']):
            point(n.node(*row[:2]), position, np.asarray(force), np.zeros(3))
        for entry in aero['body_shoulders']:
            point(n.node(entry['beam'],entry['t']), entry['position'], np.asarray(entry['force']), np.zeros(3))
        for entry in aero['engines']:
            point(n.node(entry['beam'],entry['t']), entry['position'], np.asarray(entry['force']), np.asarray(entry['moment']))
        add(nf, nm); values = np.column_stack(values); wrenches = np.column_stack(wrenches)
        expected = np.r_[aero['force'], aero['moment']]
        np.testing.assert_allclose(wrenches.sum(axis=1), expected, atol=2e-10, rtol=2e-11)
        closure = max(closure, float(max(abs(wrenches.sum(axis=1)-expected))))
        if args['factor']==1:
            x = state.x.copy(); x[n.gamma_start:n.operating_start] = circulation/n.gamma_scale
            _, data = n.residual(x, detail=True, **dict(options, circulation_rate=rate))
            reference, _, _ = groups(system, data); native_evaluations += 1
            expected = sum(v for k,v in reference.items() if k!='real_mass_gravity_applied' and not k.endswith(':stall'))
            error = float(max(abs(values.sum(axis=1)-expected))); native_error = max(native_error, error)
            assert error < 2e-10, error
        return values, wrenches, np.asarray(aero['circulation_residual'])
    base_values, base_wrenches, base_residual = sample()
    assert max(abs(base_residual)) < 1e-10
    stencils = []
    widths=(1e-3,5e-4) if args['width'] is None else (args['width'],)
    for width in widths:
        loads = np.zeros_like(base_values, complex); wrench = np.zeros_like(base_wrenches, complex)
        circulation = np.zeros_like(gamma, complex)
        for part in ((0,1) if args['part'] is None else (args['part'],)):
            for offset, weight in [(-2,1),(-1,-8),(1,8),(2,-1)]:
                v, w, r = sample(part, width*offset)
                multiplier = (1 if part==0 else 1j)*weight/(12*width)
                loads += multiplier*v; wrench += multiplier*w; circulation += multiplier*r
        stencils.append((loads,wrench,circulation))
    load_error = float(np.max(abs(stencils[0][0]-stencils[1][0]))) if len(stencils)==2 else None
    wrench_error = float(np.max(abs(stencils[0][1]-stencils[1][1]))) if len(stencils)==2 else None
    circulation_error = float(max(abs(stencils[-1][2])))
    assert (load_error is None or load_error<2e-8) and (wrench_error is None or wrench_error<2e-6) and circulation_error<2e-8, (load_error,wrench_error,circulation_error)
    np.savez_compressed(folder/'arrays.npz', loads=stencils[-1][0], wrenches=stencils[-1][1],
        state=trial.z, base_loads=base_values, base_wrenches=base_wrenches, stencil_difference=stencils[-1][0]-stencils[0][0],
        wrench_stencil_difference=stencils[-1][1]-stencils[0][1], circulation_direction=stencils[-1][2])
    return dict(factor=args['factor'], panels=record['panels'], frequency_hz=FREQUENCY, groups=keys,
        part=args['part'], widths=list(widths),
        aero_evaluations=trial.calls, native_network_comparisons=native_evaluations,
        native_transfer_error=native_error, transfer_wrench_closure=closure,
        load_stencil_error=load_error, wrench_stencil_error=wrench_error, circulation_directional_error=circulation_error,
        qualification='Complete fine-grid aerodynamic loads transferred to unchanged structural equations with moving arms. Fine harmonic circulation is solved; structural motion is prescribed, not recoupled.')


def loads_join(folder,args):
    import numpy as np
    factor=args['factor']; assert factor==4
    records=[]; arrays=[]
    for label,width in (('wide',1e-3),('fine',5e-4)):
        for part,name in enumerate(('real','imag')):
            tag=f'loads-{factor}-{name}-{label}'; r=accepted(tag)
            assert r['part']==part and r['frequency_hz']==FREQUENCY and r['factor']==factor and r['widths']==[width]
            records.append(r)
            with np.load(STUDY/tag/'arrays.npz') as saved: arrays.append(dict(saved))
    for name in ('state','base_loads','base_wrenches'):
        for item in arrays[1:]: np.testing.assert_array_equal(arrays[0][name],item[name])
    merged={name:arrays[0][name] for name in ('state','base_loads','base_wrenches')}
    for name in ('loads','wrenches','circulation_direction'):
        merged[name]=arrays[2][name]+arrays[3][name]
    for source,destination in (('loads','stencil_difference'),('wrenches','wrench_stencil_difference')):
        merged[destination]=merged[source]-arrays[0][source]-arrays[1][source]
    le=float(np.max(abs(merged['stencil_difference'])))
    we=float(np.max(abs(merged['wrench_stencil_difference'])))
    ce=float(np.max(abs(merged['circulation_direction'])))
    assert le<2e-8 and we<2e-6 and ce<2e-8,(le,we,ce)
    np.savez_compressed(folder/'arrays.npz',**merged)
    result=dict(records[0],part=None,widths=[1e-3,5e-4],load_stencil_error=le,wrench_stencil_error=we,circulation_directional_error=ce)
    for name in ('aero_evaluations','native_network_comparisons'): result[name]=sum(r[name] for r in records)
    for name in ('native_transfer_error','transfer_wrench_closure'): result[name]=max(r[name] for r in records)
    return result


def project(folder, args):
    import numpy as np
    import check_daedalus_aero_feedback as prior
    prior.STUDY = STUDY; prior.CAPTURES = ['loads-1','loads-2','loads-4']
    result = prior.project(folder, SimpleNamespace())
    with np.load(SAMPLES/'fine-samples/arrays.npz') as saved:
        index = int(np.argmin(abs(saved['frequencies']-FREQUENCY)))
        assert abs(saved['frequencies'][index]-FREQUENCY)<1e-14
        refined = saved['outputs'][index]
    baseline = np.array(result['baseline_real'])+1j*np.array(result['baseline_imag'])
    observed = refined-baseline
    result['full_mesh_comparison'] = dict(refined_output_real=refined.real.tolist(), refined_output_imag=refined.imag.tolist(),
        observed_change_real=observed.real.tolist(), observed_change_imag=observed.imag.tolist())
    for row in result['comparisons']:
        change = np.array(row['change_real'])+1j*np.array(row['change_imag'])
        row['projection_on_observed_mesh_change_percent'] = (100*np.real(change*np.conj(observed))/abs(observed)**2).tolist()
        row['component_roll_magnitude_first_variation_percent'] = (100*np.real((np.array(row['component_output_real'])[1]+1j*np.array(row['component_output_imag'])[1])/baseline[1])).tolist()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['shape','shape_base','shape_part','shape_join','loads','loads_join','project']); parser.add_argument('--tag', required=True)
    parser.add_argument('--factor', type=int, choices=[1,2,4], default=1)
    parser.add_argument('--part',type=int,choices=[0,1])
    parser.add_argument('--width',type=float,choices=[1e-3,5e-4])
    parser.add_argument('--source'); args = vars(parser.parse_args())
    inputs = [ROOT/'scripts'/p for p in ('check_daedalus_aero_resolution.py','check_daedalus_aero_feedback.py',
        'check_daedalus_wing_paper.py','check_daedalus_source_operator.py')]
    inputs += [ROOT/'examples/dae.asw', ROOT/'examples/dae-cruise-physical-mesh-project.json', SOURCE/'trim-6.7-1/state.json',
        ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
        SAMPLES/'coarse-samples/arrays.npz', SAMPLES/'fine-samples/arrays.npz']
    inputs += [SOURCE/'assembled-6.7'/p for p in ('A.npz','M.npz','maps.npz')]+list((ROOT/'openswing').glob('*.py'))
    if args['stage'] in ('shape','shape_base'):
        source = OLD/ACCEPTED[[1,2,4].index(args['factor'])]
        inputs += [source/p for p in ('arrays.npz','result.json','terminal.json','plan.json')]
    elif args['stage']=='shape_part':
        inputs += [STUDY/(args['source'] or f"shape-{args['factor']}-base")/p for p in ('arrays.npz','result.json','terminal.json')]
    elif args['stage'] in ('shape_join','loads_join'):
        stem='shape' if args['stage']=='shape_join' else 'loads'
        names=tuple(f'{part}-{width}' for part in ('real','imag') for width in ('wide','fine'))
        if stem=='shape': names=('base',*names)
        inputs += [STUDY/f"{stem}-{args['factor']}-{name}"/p for name in names for p in ('arrays.npz','result.json','terminal.json')]
    elif args['stage']=='loads':
        inputs += [STUDY/(args['source'] or f"shape-{args['factor']}")/p for p in ('arrays.npz','result.json','terminal.json')]
    else:
        inputs += [STUDY/tag/p for tag in ('loads-1','loads-2','loads-4') for p in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,shape if args['stage']=='shape_base' else globals()[args['stage']],args,__file__)


if __name__=='__main__': main()
