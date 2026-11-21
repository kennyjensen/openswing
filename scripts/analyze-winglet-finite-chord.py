"""Audit finite-chord results; compare prescribed chordwise spreading separately.

No aerodynamic solves. New field evaluations hold the saved lifting-line
section circulation fixed and distribute its bound strength uniformly over
the chord rows. This is a mechanism check, not a thin-airfoil loading model.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def components_cross(a,b):
    return np.column_stack([a[:,1]*b[:,2]-a[:,2]*b[:,1],
                            a[:,2]*b[:,0]-a[:,0]*b[:,2],
                            a[:,0]*b[:,1]-a[:,1]*b[:,0]])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--analysis-output', type=Path, required=True)
    args = parser.parse_args()
    folder, output = args.study, args.analysis_output
    if output.exists():
        parser.error('Use a fresh analysis output directory; preserve earlier observations.')
    verification = json.loads((folder/'verification.json').read_text())
    plan = json.loads((folder/'plan.json').read_text())
    rows = json.loads((folder/'results.json').read_text())
    assert all(sha(folder/name) == pin for name,pin in verification['artifacts'].items())
    assert all(sha(ROOT/name) == pin for name,pin in plan['unchanged_pins'].items())
    assert [dict(chord_rows=r['chord_rows'],main_span_intervals=r['main_span_intervals'])
            for r in rows] == plan['requests']
    baseline_path = ROOT/plan['baseline_dir']/'results.json'
    assert sha(baseline_path) == plan['baseline_result_sha256']
    baseline = {r['request']['main_intervals']:r['result'] for r in json.loads(baseline_path.read_text())
                if r['request']['sampling'] == 'arithmetic-control'}
    sys.path.insert(0,str((folder/'reference').resolve()))
    import loads
    import vlm
    for module in (loads,vlm):
        assert sha(Path(module.__file__)) == plan['reference_kernel_pins'][module.__name__]
    output.mkdir(parents=True)
    (output/'analysis-driver-used.py').write_bytes(Path(__file__).read_bytes())
    write(output/'plan.json',dict(utc=utc(),source_results_sha256=sha(folder/'results.json'),
        analysis_driver_sha256=sha(Path(__file__)),scientific_solves=0,prescribed_field_states=len(rows),
        prescription='Use saved one-row LL Gamma(s) on each grid. Ring Gamma for chord row i is '
            '(i+1)/Nc times that value, so all bound increments are Gamma(s)/Nc and total '
            'circulation and trailing-wake strength remain unchanged. This is a deliberate '
            'uniform spreading control, not a claimed physical chord distribution.',
        field_samples='Same x=0 quarter-chord probes as solved controls; exact own front-edge '
            'exclusion for Nc=1, no exclusion for Nc=2,4. No core.',
        caveat='Prescribed states do not satisfy the finite-chord boundary equations; residuals are retained.'))
    audits, fields = [], {}
    for row in rows:
        path = folder/row['artifact']['path']
        assert sha(path) == row['artifact']['sha256']
        with np.load(path) as store:
            data = {key:store[key] for key in store.files}
        n, nc = row['main_span_intervals'], row['chord_rows']
        assert len(data['gamma']) == n*7//5*nc == row['total_panels']
        scalar_residual = np.array([math.fsum(float(a)*float(g) for a,g in zip(m,data['gamma']))-rhs
                                   for m,rhs in zip(data['matrix'],data['rhs'])])
        assert np.max(abs(scalar_residual)) < 1e-12
        assert abs(row['CL']-row['loads']['full']['force'][2]/.06125) < 1e-13
        forces = 1.225*data['edge_strengths'][:,None]*components_cross(
            data['edge_velocity'],data['ends']-data['starts'])
        moments = components_cross(data['edge_midpoints'],forces)
        np.testing.assert_allclose(forces,data['edge_forces'],atol=3e-13,rtol=3e-12)
        np.testing.assert_allclose(moments,data['edge_moments'],atol=3e-13,rtol=3e-12)
        assert np.all(data['mask_all_spanwise'] ^ data['mask_chordwise'])
        for name,ledger in row['loads'].items():
            mask = np.ones(len(forces),dtype=bool) if name == 'full' else data['mask_'+name]
            np.testing.assert_allclose(forces[mask].sum(axis=0),ledger['force'],atol=3e-13,rtol=3e-12)
            np.testing.assert_allclose(moments[mask].sum(axis=0),ledger['moment'],atol=3e-13,rtol=3e-12)
        # Independently assemble signed endpoint flux from stored physical
        # coordinates. Every ring column must close, including wake rays.
        flux = {}
        def add(point, coefficients):
            key=tuple(point)
            if key not in flux: flux[key]=np.zeros(len(data['gamma']))
            flux[key]+=coefficients
        for a,b,coeff in zip(data['starts'],data['ends'],data['edge_coefficients']):
            add(a,-coeff);add(b,coeff)
        for point,coeff in zip(data['ray_starts'],data['ray_coefficients']):
            add(point,-coeff)
        assert all(np.all(v==0.) for v in flux.values())
        # Independent one-row bridge checks from the archived physical fields.
        if nc == 1:
            ref = baseline[n]
            for key,saved in [('gamma',[s['circulation'] for s in ref['strips']]),
                              ('quarter_chord_velocity',[s['relative_velocity'] for s in ref['strips']])]:
                np.testing.assert_allclose(data[key],saved,atol=2e-12,rtol=2e-11)
            np.testing.assert_allclose(forces[data['mask_front']].sum(axis=0),ref['force'],atol=2e-12,rtol=2e-11)
            np.testing.assert_allclose(moments[data['mask_front']].sum(axis=0),ref['moment'],atol=2e-12,rtol=2e-11)
        # New prescribed-field control, no linear system solve.
        prescribed = []
        for beam in (1,2,3):
            sectional = np.array([s['circulation'] for s in baseline[n]['strips'] if s['beam']==beam])
            prescribed.extend(((np.arange(nc)+1)[:,None]/nc*sectional).ravel())
        prescribed = np.asarray(prescribed)
        sectional=np.array([s['circulation'] for s in baseline[n]['strips']])
        expected_rays=np.r_[-sectional[0],sectional[:-1]-sectional[1:],sectional[-1]]
        np.testing.assert_allclose(np.sort(data['ray_coefficients']@prescribed),
                                   np.sort(expected_rays),atol=2e-15,rtol=2e-13)
        graph = {key:data[key] for key in ('starts','ends','edge_coefficients','ray_starts','ray_coefficients')}
        graph['topology'] = dict(corners=data['corners'],wake_direction=np.array([1.,0.,0.]))
        own = None
        if nc == 1:
            # Map exact midpoint coordinates, with uniqueness asserted.
            own = []
            for point in data['quarter_chord_probes']:
                match = np.flatnonzero(np.all(data['edge_midpoints'] == point,axis=1))
                assert len(match)==1
                own.append(match[0])
            own = np.asarray(own)
        value = loads.velocity(data['quarter_chord_probes'],graph,prescribed,own_edges=own)+[1.,0.,0.]
        defect = data['matrix']@prescribed-data['rhs']
        if nc == 1:
            np.testing.assert_allclose(value,data['quarter_chord_velocity'],atol=2e-12,rtol=2e-11)
        field_path = output/(row['case']+'-prescribed.npz')
        np.savez_compressed(field_path,gamma=prescribed,velocity=value,boundary_residual=defect)
        audits.append(dict(case=row['case'],chord_rows=nc,main_span_intervals=n,
            maximum_independent_scalar_residual=float(np.max(abs(scalar_residual))),
            maximum_independent_force_error=float(np.max(abs(forces-data['edge_forces']))),
            CL=row['CL'],CD=row['CD'],quarter_peak=row['quarter_chord_maximum_speed'],
            actual_edge_peak=row['edge_maximum_speed'],
            prescribed_quarter_peak=float(np.max(np.linalg.norm(value,axis=1))),
            prescribed_boundary_defect=float(np.max(abs(defect))),
            prescribed_file=dict(path=field_path.name,sha256=sha(field_path)),
            chordwise_CL=row['loads']['chordwise']['force'][2]/.06125))
        fields[row['case']] = dict(stations=data['material_stations'],solved=data['quarter_chord_velocity'],
                                  prescribed=value)
    plt.rcParams.update({'font.size':9,'axes.grid':True,'grid.alpha':.23})
    fig,axes = plt.subplots(2,2,figsize=(10.4,7.1),constrained_layout=True)
    colors={1:'#0072B2',2:'#D55E00',4:'#009E73'}
    for row in rows:
        nc,n=row['chord_rows'],row['main_span_intervals']; f=fields[row['case']]
        mask=f['stations']>0.;style='-' if n==100 else '--'
        label=f'{nc} chord row(s), N={n}'
        axes[0,0].plot(f['stations'][mask],f['solved'][mask,0],style,color=colors[nc],label=label)
        axes[0,1].plot(f['stations'][mask],f['prescribed'][mask,0],style,color=colors[nc])
    for ax in axes[0]:
        ax.axvline(.5,color='.4',linewidth=1,alpha=.5)
        ax.set_xlim(.4,.6);ax.set_xlabel('Material distance s [m], corner at 0.5')
        ax.set_ylabel(r'Quarter-chord streamwise velocity $u_x/U_\infty$')
    axes[0,0].set_title('Solved circulation: increasing chord resolution')
    axes[0,1].set_title('Same LL circulation, uniformly spread over chord')
    axes[0,0].legend(fontsize=7)
    for nc in colors:
        a=sorted([r for r in audits if r['chord_rows']==nc],key=lambda r:r['main_span_intervals'])
        ns=[r['main_span_intervals'] for r in a]
        axes[1,0].plot(ns,[r['quarter_peak'] for r in a],'o-',color=colors[nc],label=f'{nc} rows: quarter chord')
        axes[1,0].plot(ns,[r['actual_edge_peak'] for r in a],'s--',color=colors[nc],label=f'{nc} rows: vortex edges')
        axes[1,1].plot(ns,[r['CL'] for r in a],'o-',color=colors[nc],label=f'{nc} chord row(s)')
    axes[1,0].set_xlabel('Main-wing span intervals N');axes[1,0].set_ylabel('Maximum speed / freestream')
    axes[1,0].set_title('Actual edge peaks still grow')
    axes[1,0].legend(fontsize=7)
    axes[1,1].set_xlabel('Main-wing span intervals N');axes[1,1].set_ylabel('Full canonical-edge CL')
    axes[1,1].set_title('Force definition includes chordwise edges')
    axes[1,1].legend(fontsize=8)
    fig.suptitle('Sharp unswept winglet: independent finite-chord diagnostic\n'
                 'No core; no production change or ASWING validation claim',fontsize=12)
    for extension in ('png','svg'):
        fig.savefig(output/('finite-chord-comparison.'+extension),dpi=170)
    plt.close(fig)
    summary=dict(utc=utc(),audits=audits,scientific_solves=0,prescribed_field_states=len(rows),
        source_and_scope_pins_verified=True,raw_artifact_pins_verified=True,
        maximum_independent_boundary_residual=max(r['maximum_independent_scalar_residual'] for r in audits),
        elapsed_solve_and_record_seconds=sum(r['seconds'] for r in rows),
        observations=['One-row front-edge Gamma/fields/loads match the saved LL control to roundoff.',
            'Added chord rows lower quarter-chord speed; actual vortex-edge maxima still rise with span refinement.',
            'Uniform prescribed spreading keeps section circulation and the trailing-wake strength fixed; it is not a solved state.',
            'Full edge loads include chordwise-edge forces absent from the LL bound-line ledger.',
            'No native ASWING result, continuum convergence or physically justified production repair established.'],
        files={p.name:sha(p) for p in output.iterdir() if p.is_file()})
    assert all(sha(ROOT/name) == pin for name,pin in plan['unchanged_pins'].items())
    write(output/'analysis.json',summary)
    print(json.dumps({k:summary[k] for k in ('maximum_independent_boundary_residual','elapsed_solve_and_record_seconds')},indent=2))
    for r in audits:
        print(r['case'],'solved quarter',r['quarter_peak'],'edge',r['actual_edge_peak'],
              'prescribed quarter',r['prescribed_quarter_peak'],'unsatisfied BC',r['prescribed_boundary_defect'])


if __name__=='__main__':
    main()
