"""Replay actual component forcing against source and continuum mechanics.

The loads are extracted from supplied aircraft solutions. This is an
independent mechanical response to known loads, not a new aircraft solution.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from daedalus_bounded_job import run
from check_daedalus_mount_continuum import STUDY, CAPTURE, FREQUENCIES

CASES = {
    'slow': ROOT/'artifacts/daedalus-load-sensitivity-20261113/slow-animation/arrays.npz',
    'dip': ROOT/'artifacts/daedalus-load-sensitivity-20261113/reference-dip/arrays.npz',
    'yaw_zero': ROOT/'artifacts/daedalus-transmission-zeros-20261114/yaw-verify/arrays.npz',
    'roll_zero': ROOT/'artifacts/daedalus-transmission-zeros-20261114/roll-verify/arrays.npz',
}


def work(folder, args):
    import numpy as np
    fixture = read(CAPTURE/'fixture.json'); capture = np.load(CAPTURE/'arrays.npz')
    L, F = fixture['L'], fixture['F']; scales = np.r_[[L]*3, [1.]*3]
    wscale = np.r_[[F]*3, [F*L]*3]; moment = np.array([1/2.5]*3+[1.]*3)
    discrete = {n: np.load(STUDY/f'discrete-{n}/arrays.npz') for n in (2, 4, 8)}
    continuum = {p: np.load(STUDY/f'continuum-{p}/arrays.npz') for p in (10, 12)}
    records = []; arrays = {}; maxclosure = 0.; maxcompatibility = 0.; maxstencil = 0.
    def record(v): return dict(real=v.real.tolist(), imag=v.imag.tolist())
    for name, s in FREQUENCIES:
        if name not in CASES: continue
        full = np.load(CASES[name])['state']; z = full[capture['columns']]
        native = capture['matrix']-s*s*capture['mass']
        action = native@z
        compatibility = float(max(abs(action[:12]))); assert compatibility < 2e-10
        maxcompatibility = max(maxcompatibility, compatibility)
        forcing = np.c_[action[12:18].reshape(2, 3)*F, action[18:24].reshape(2, 3)*F*L]
        cut = z[-6:]*scales
        actual = z[:12].reshape(2, 6)*scales
        actual = np.r_[actual, cut[None, :]]
        results = {}; refvalues = {}
        for precision, saved in continuum.items():
            states = np.concatenate([saved[name+'_motion'], saved[name+'_internal']], axis=1)
            # An applied point wrench -b at interior station j gives the
            # backward jump [0,-b]. Propagate it only to smaller stations;
            # correct the root-wrench input to preserve its prescribed value.
            jump = np.r_[np.zeros(6), -forcing[1]]
            coefficient = np.linalg.solve(states[1], jump)
            error = float(max(abs(states[1]@coefficient-jump)))
            assert error < 2e-8, error
            particular = np.zeros((3, 12), complex)
            particular[0] = states[0]@coefficient
            contribution = particular-np.einsum('nij,j->ni', states[:, :, :6], particular[0, 6:])
            response = np.einsum('nij,j->ni', states, np.r_[forcing[0], cut])+contribution
            assert max(abs(response[-1, :6]-cut)) < 2e-10
            assert max(abs(response[0, 6:]-forcing[0])) < 2e-8
            refvalues[precision] = response[:, :6]
            arrays[f'{name}_continuum_{precision}'] = response
        norm = np.linalg.norm(refvalues[12][0]*moment)
        tol = float(np.linalg.norm((refvalues[10][0]-refvalues[12][0])*moment)/norm)
        assert tol < 2e-7, tol; maxstencil = max(maxstencil, tol)
        for ne, saved in discrete.items():
            operator = saved['matrix']-s*s*saved['mass']; size = 12*ne
            rhs = -operator[:, size:]@(cut/scales)
            for j, t in enumerate(fixture['stations'][:-1]):
                node, = np.flatnonzero(saved['stations'] == t)
                rows = np.r_[6*ne+3*node+np.arange(3), 9*ne+3*node+np.arange(3)]
                rhs[rows] += forcing[j]/wscale
            a = operator[:, :size]; row = np.max(abs(a), axis=1); col = np.max(abs(a/row[:, None]), axis=0)
            scaled = a/row[:, None]/col; rcond = float(1/np.linalg.cond(scaled)); assert rcond > 1e-12
            answer = np.linalg.solve(scaled, rhs/row)/col
            residual = float(max(abs((a@answer-rhs)/row))); assert residual < 2e-10
            motion = np.r_[answer[:6*ne].reshape(ne, 6)*scales, cut[None, :]]
            if ne == 2:
                closure = float(np.max(abs(motion-actual))); assert closure < 2e-9
                maxclosure = max(maxclosure, closure)
            difference = motion[0]-refvalues[12][0]
            relative_motion = float(np.linalg.norm(difference*moment)/norm)
            relative_rotation = float(np.linalg.norm(difference[3:])/np.linalg.norm(refvalues[12][0, 3:]-cut[3:]))
            results[str(ne)] = dict(motion_error=relative_motion, relative_rotation_error=relative_rotation,
                wing_rotation_deg=record(motion[0, 3:]*180/np.pi),
                rotation_from_fairing_deg=record((motion[0, 3:]-cut[3:])*180/np.pi),
                max_rotation_error_deg=float(max(abs(difference[3:]))*180/np.pi),
                scaled_residual=residual, rcond=rcond)
            arrays[f'{name}_discrete_{ne}'] = motion
        records.append(dict(case=name, forcing=record(forcing), cut_motion=record(cut),
            reference_rotation_from_fairing_deg=record((refvalues[12][0, 3:]-cut[3:])*180/np.pi),
            continuum_tolerance_change=tol, comparisons=results))
    np.savez_compressed(folder/'arrays.npz', **arrays)
    result = dict(cases=records, coarse_full_state_closure=maxclosure,
        full_compatibility_residual=maxcompatibility, continuum_tolerance_change=maxstencil,
        qualification='Actual externally imposed component wrenches inferred from the supplied full solution and independently source-matched mechanical operator. Interior loads are retained. Dynamic nodal inertia is removed before the same forcing is applied to each continuum/discrete component. This conditional replay does not recouple the aircraft or predict a new Bode/transfer-zero location.')
    print(result, flush=True); return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--tag', required=True)
    args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/check_daedalus_mount_continuum.py', ROOT/'scripts/daedalus_mount_reference.py',
        ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/aswing-authoritative-sources.json', *CASES.values()]
    for tag in ['prepare-v2', 'discrete-2', 'discrete-4', 'discrete-8', 'continuum-10', 'continuum-12']:
        inputs += [STUDY/tag/name for name in ('arrays.npz', 'result.json', 'terminal.json')]
    inputs += [CAPTURE/'fixture.json']
    run(STUDY, args['tag'], inputs, work, args, __file__)


if __name__ == '__main__': main()
