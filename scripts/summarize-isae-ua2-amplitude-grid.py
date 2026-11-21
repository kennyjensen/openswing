"""Aggregate the fully audited UA-2 amplitude/frequency grid without new solves."""
from hashlib import sha256
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-amplitude-grid-20261101'


def main():
    plan=json.loads((BASE/'plan.json').read_text());complete=json.loads((BASE/'batch-complete.json').read_text())
    assert complete['all_terminal'] and complete['new_production_segments']==154
    for name,digest in plan['source_sha256'].items():
        assert sha256((BASE/'frozen-code'/name).read_bytes()).hexdigest()==digest
        assert sha256((ROOT/name).read_bytes()).hexdigest()==digest
    for name,digest in plan['reused_case']['sha256'].items():
        assert sha256((ROOT/name).read_bytes()).hexdigest()==digest
    cases=plan['new_cases']+[dict(id='k095-a050',k=.95,amplitude_ratio=.5,reused=True)]
    rows=[];audited=0;seconds=[];checks=0;mesh_checks=0
    figure,axes=plt.subplots(2,2,figsize=(10,7),constrained_layout=True)
    for case in cases:
        reused=case.get('reused',False)
        folder=BASE/'reused-case-audit' if reused else BASE/case['id']
        records=[json.loads((folder/f'audit-n{n}.json').read_text()) for n in (20,40)]
        for n,data in zip((20,40),records):
            assert data['panels']==n and data['k']==case['k'] and data['amplitude_ratio']==case['amplitude_ratio']
            assert data['auditor_sha256']==sha256((ROOT/'scripts/audit-isae-ua2-nonlinear.py').read_bytes()).hexdigest()
            assert data['independent_spatial_reference'] and not data['native_ASWING_comparison']
            assert data['refinement_check_passed'];checks+=1;audited+=data['audited_unique_snapshots']
        fine=[d['records'][-1] for d in records];waves=[r['waveform'] for r in fine]
        np.testing.assert_allclose(waves[0]['times'],waves[1]['times'],atol=1e-12,rtol=0)
        mesh=float(np.max(abs(np.array(waves[0]['CL'])-waves[1]['CL']))/max(map(abs,waves[1]['CL'])))
        mesh_passed=mesh<plan['gates']['fine_mesh_lift_change_fraction'];mesh_checks+=int(mesh_passed)
        row=dict(k=case['k'],amplitude_ratio=case['amplitude_ratio'],reused_production=reused,
            mesh_lift_change_percent=100*mesh,mesh_check_passed=mesh_passed,meshes=[])
        for n,data in zip((20,40),records):
            coarse,fine=data['records']
            if not reused:
                for record in data['records']:seconds.extend(record['segment_seconds'])
            row['meshes'].append(dict(panels=n,passed=data['refinement_check_passed'],
                coarse_lift_error_percent=100*coarse['lift_waveform_error_fraction'],
                fine_lift_error_percent=100*fine['lift_waveform_error_fraction'],
                fine_circulation_error_percent=100*fine['circulation_waveform_error_fraction'],
                fine_per_strip_rate_error_percent=100*fine['per_strip_rate_waveform_error_fraction'],
                fine_first_step_relative_rate_error_percent=100*fine['first_step_relative_rate_error_fraction'],
                lift_error_ratio=data['lift_refinement_ratio'],
                maximum_residual=max(r['maximum_residual'] for r in data['records']),
                maximum_checkpoint_join_jump=max(r['maximum_checkpoint_join_jump'] for r in data['records']),
                maximum_reference_method_difference_fraction=max(data['reference_method_difference_fractions'].values()),
                audit_path=str((folder/f'audit-n{n}.json').relative_to(ROOT)),
                audit_sha256=sha256((folder/f'audit-n{n}.json').read_bytes()).hexdigest()))
        rows.append(row)
    assert len(rows)==8 and checks==16 and audited==5152
    assert len(seconds)==154
    rows.sort(key=lambda r:(r['k'],r['amplitude_ratio']))
    for column,k in enumerate((.475,.95)):
        subset=[r for r in rows if r['k']==k];amplitudes=[r['amplitude_ratio'] for r in subset]
        for index,n in enumerate((20,40)):
            axes[0,column].plot(amplitudes,[r['meshes'][index]['fine_lift_error_percent'] for r in subset],'o-',label=f'{n} strips')
            axes[1,column].plot(amplitudes,[r['meshes'][index]['fine_per_strip_rate_error_percent'] for r in subset],'o-',label=f'{n} strips')
        for axis in axes[:,column]:
            axis.axhline(.1,color='black',ls=':',lw=.8,label='Fine-grid gate')
            axis.set(xlabel='Peak-to-peak A/c',title=f'k={k:g}');axis.set_xticks(amplitudes)
            axis.grid(alpha=.25);axis.legend(fontsize=8)
        axes[0,column].set_ylabel('Lift waveform error (%)')
        axes[1,column].set_ylabel('Worst per-strip rate error (% of own peak)')
    summary=dict(date='2026-11-01',scope=plan['scope'],cases=rows,refinement_checks_passed=checks,
        refinement_checks_total=16,mesh_checks_passed=mesh_checks,mesh_checks_total=8,
        audited_unique_snapshots=audited,new_production_segments=154,reused_production_segments=22,
        new_continuous_trajectories=28,reused_continuous_trajectories=4,
        new_solver_seconds_range=[min(seconds),max(seconds)],new_total_solver_seconds=sum(seconds),
        production_files_unchanged=136,production_changed=False,app_defaults_changed=False,
        independent_spatial_reference=True,native_ASWING_comparison=False,
        summary_script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['Two working frequencies only; the other published frequencies remain.',
            'Zero mean incidence, attached flow, reconstructed straight rigid AR10 only.',
            'First-cycle verification; periodic 3D amplitude/phase and mean lift remain.',
            'Native model/driver provenance is unresolved; all 222 native UA-2 slots remain blocked.',
            'Explicit startup-refined time grids; app defaults and general error control unchanged.'])
    stem=ROOT/'docs/validation/isae-ua2-amplitude-grid-20261101'
    stem.with_suffix('.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    figure.suptitle('UA-2: independent nonlinear first-cycle checks, all four amplitudes')
    figure.savefig(stem.with_suffix('.svg'));figure.savefig(stem.with_suffix('.png'),dpi=150);plt.close(figure)
    table=['| k | A/c | Fine lift error, 20 / 40 strips | Fine per-strip rate error, 20 / 40 strips | Mesh lift change |',
           '|---:|---:|---:|---:|---:|']
    for row in rows:
        a,b=row['meshes']
        table.append(f'| {row["k"]:g} | {row["amplitude_ratio"]:g} | {a["fine_lift_error_percent"]:.5f}% / {b["fine_lift_error_percent"]:.5f}% | '
            f'{a["fine_per_strip_rate_error_percent"]:.5f}% / {b["fine_per_strip_rate_error_percent"]:.5f}% | {row["mesh_lift_change_percent"]:.5f}% |')
    all_meshes=[m for row in rows for m in row['meshes']]
    coarse=[m['coarse_lift_error_percent'] for m in all_meshes]
    first=[m['fine_first_step_relative_rate_error_percent'] for m in all_meshes]
    gamma=[m['fine_circulation_error_percent'] for m in all_meshes]
    ref_difference=max(m['maximum_reference_method_difference_fraction'] for m in all_meshes)
    report=f'''# UA-2: finite-amplitude first-cycle grid

Updated 2026-11-01. **{checks}/16 time-refinement checks and {mesh_checks}/8 mesh checks pass**
across A/c=0.05, 0.1, 0.3 and 0.5 at k=0.475 and 0.95. Both 20/40-strip meshes
use nominal 80/160 time grids. The audit covers **{audited:,} unique snapshots**
from 32 continuous trajectories. These independently verify the reconstructed
straight-wing equations and time integration; native ASWING comparison remains
blocked and full UA-2 validation is unfinished.

{chr(10).join(table)}

Fine lift errors are maximum absolute errors divided by the cycle's reference
peak. Rate errors use each strip's own reference peak before maximizing over
strips and times. Every strip and accepted time is retained. The mesh column
compares production lift histories between 20 and 40 strips at the fine time grid.
This measures stability over two meshes; the spatial continuum limit remains
unverified.

The unchanged gates require fine lift/rate waveform errors below 0.1%, first-step
relative rate errors below 1%, and a lift-error reduction ratio below 0.35 when
halving the maximum timestep. Mesh lift changes must be below 0.2%. Coarse lift
errors are {min(coarse):.4f}–{max(coarse):.4f}% and remain explicit failures of the
fine-grid accuracy requirement. Fine first-step rate errors are
{min(first):.4f}–{max(first):.4f}%; fine circulation waveform errors are
{min(gamma):.4f}–{max(gamma):.4f}% of their reference peaks. These numerical gates
do not inherit the provisional SA 3% policy.

![Finite-amplitude grid results](isae-ua2-amplitude-grid-20261101.svg)

The [independent straight-wing reference](isae-straight-wing-heave-reference.md)
integrates the bound vortices and both trailing legs separately from production
code, then applies Drela's nonlinear circulation-lag and instantaneous load
equations. It retains the induced bound-point speed and rotates influences with
the live wind. DOP853 and Radau check each reference independently; their largest
difference over the grid is {ref_difference:.3g} of the relevant reference peak,
below the unchanged 1e-8 reference-agreement gate. No fitted 0.85/0.90 factors
enter the equations.

The [completed largest-amplitude pilot](isae-ua2-nonlinear-20261101.md) is reused
for A/c=0.5, k=0.95. Its original producer sources, reports and trajectories are
preserved. A saved-only audit rechecks those histories with the generalized
auditor and verifies unchanged production hashes; it performs no new production
solve. The other seven combinations add 154 serial segments and 28 trajectories.
Each numerical job remains capped at 45 seconds with one BLAS thread. New solver
segments take {min(seconds):.2f}–{max(seconds):.2f} seconds, totaling {sum(seconds):.2f} seconds.
All production jobs finish without retries, timeouts or rejected steps; all
checkpoint joins preserve forces, circulation and circulation rate.

The grids retain `dt_max/256` at startup and growth at most 1.125, resulting in
120/200 accepted steps per cycle for nominal 80/160 resolution. Segments contain
at most 32 steps and preserve the original forcing table and BDF predecessor.
This explicit grid choice does not change app defaults. All 136 production
files remain unchanged. Only validation parameter handling, auditing and
reporting expand in this batch.

Evidence: [machine summary](isae-ua2-amplitude-grid-20261101.json),
[plans, execution receipts, complete trajectories, references and frozen sources](../../artifacts/isae/ua2-amplitude-grid-20261101),
[serial grid runner](../../scripts/run-isae-ua2-amplitude-grid.py), and
[generalized trajectory auditor](../../scripts/audit-isae-ua2-nonlinear.py).

Remaining work includes other published frequencies, periodic 3D amplitude/phase
and mean lift, and nonzero mean incidence. The model is a declared straight,
rigid AR10 reconstruction with Mach zero and stall disabled. Native model/driver
provenance is unresolved, so all 222 native UA-2 comparison slots remain blocked.
Browser/WASM verification, broader model coverage and the full project goal
remain unfinished.
'''
    stem.with_suffix('.md').write_text(report)
    print(json.dumps(summary,indent=2),flush=True)
    if checks!=16 or mesh_checks!=8:raise SystemExit(1)


if __name__=='__main__':main()
