"""Numerical checks, unaltered experimental errors, source audit and figures."""
from pathlib import Path
import argparse, hashlib, json, re, sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]; DEST = ROOT/'docs/validation'
sys.path.insert(0, str(ROOT/'scripts'))


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def parse_archived_span_table(text):
    """Read the ST-3 snapshot table, retaining its printed scaling and root.

    Only the moment/force columns have printed scale exponents: Mc' is
    raw*10**-2, while Ms' and Fn are unscaled. Reject a different layout or
    malformed row instead of silently dropping data from the comparison.
    """
    columns = ['t', 'y', 'z-z0', 'tw-tw0', "Mc'/10", "Ms'/10", 'Fn/10', 'cl', 'a_flap']
    lines = text.splitlines()
    headers = [i for i, line in enumerate(lines) if line.split() == columns]
    if len(headers) != 1:
        raise ValueError('Expected exactly one ST-3 span-table header.')
    header = headers[0]
    preceding = next((line.split() for line in reversed(lines[:header]) if line.strip()), [])
    if preceding != ['-2', '0', '0']:
        raise ValueError('Unexpected ST-3 moment/force scale exponents.')
    following = [(i+1, line.split()) for i, line in enumerate(lines[header+1:], header+1) if line.strip()]
    if not following or len(following[0][1]) != len(columns) or any(set(token) != {'-'} for token in following[0][1]):
        raise ValueError('Expected the ST-3 span-table separator.')
    rows = []
    for number, tokens in following[1:]:
        if len(tokens) != len(columns):
            raise ValueError(f'Line {number}: expected nine ST-3 span-table values.')
        try:
            values = [float(token) for token in tokens]
        except ValueError as error:
            raise ValueError(f'Line {number}: invalid ST-3 span-table number.') from error
        if not np.isfinite(values).all():
            raise ValueError(f'Line {number}: nonfinite ST-3 span-table value.')
        rows.append(values)
    if not rows:
        raise ValueError('The ST-3 span table has no numeric rows.')
    table = np.asarray(rows)
    if np.any(np.diff(table[:, 0]) < 0):
        raise ValueError('ST-3 span-table stations must be nondecreasing.')
    return table


def main():
    from isae_st3_static_reference import observables

    parser = argparse.ArgumentParser(); parser.add_argument('--test-log', type=Path, required=True)
    args = parser.parse_args()
    study = json.loads((DEST/'isae-st3-static.json').read_text())
    eps = json.loads((DEST/'isae-st3-static-eps.json').read_text())
    wasm = json.loads((DEST/'isae-st3-static-wasm.json').read_text())
    modules = {p.name: sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    assert modules == study['modules'] == eps['modules'] == wasm['modules']
    for record in [study, eps, wasm]:
        for name, digest in record['scripts'].items(): assert sha(ROOT/'scripts'/name) == digest
    assert wasm['study_sha256'] == sha(DEST/'isae-st3-static.json') and wasm['status'] == 'PASS'
    assert wasm['script_sha256'] == sha(ROOT/'scripts/test-isae-st3-static-wasm.mjs')
    tests = re.search(r'(\d+) passed in ([^\n]+)', args.test_log.read_text())
    assert tests and int(tests[1]) == 22 and 'failed' not in args.test_log.read_text()
    cache = ROOT/'.reference/isae-validation'/study['revision']
    for path, pin in study['sources'].items(): assert sha(cache/path) == pin['sha256']
    rows = {r['key']: r for r in study['runs']}
    assert len(rows) == 395 and all(r['status'] == 'computed' for r in rows.values())
    references = study['independent_references']
    assert len(references) == 181 and all(r['status'] == 'computed' for r in references.values())
    assert all(p['error'] == 'Point weights must be nonnegative.' for p in study['literal_input_probes'])
    max_residual = max(r['result']['result']['residual'] for r in rows.values())
    force_balance = max(max(abs(np.array(r['result']['result']['force_balance']))) for r in rows.values())
    moment_balance = max(max(abs(np.array(r['result']['result']['moment_balance']))) for r in rows.values())
    assert max_residual < 1e-8 and force_balance < 1e-7 and moment_balance < 1e-7
    reference_errors = []
    for r in rows.values():
        if r['identity']['specification']['panels'] != 64: continue
        ref = references[r['reference_key']]['result']; actual = r['result']['observables']
        reference_errors.append(dict(key=r['key'], **{key: actual[key]-ref['observables'][key] for key in ['h_m', 'theta_dunn_deg']}))
    max_ref_h = max(abs(r['h_m']) for r in reference_errors)
    max_ref_t = max(abs(r['theta_dunn_deg']) for r in reference_errors)
    assert max_ref_h < 5e-5 and max_ref_t < .002
    comparisons = []; mesh_differences = []
    for d in study['datasets']:
        if d['category'] != 'experiment_digitization': continue
        key = 'h_m' if d['quantity'] == 'Z' else 'theta_dunn_deg'
        values = np.array(d['values']); predicted = np.array([rows[k[1]]['result']['observables'][key] for k in d['native_keys']])
        coarse = np.array([rows[k[0]]['result']['observables'][key] for k in d['native_keys']])
        delta = predicted-values[:, 0]
        ref = np.array([references[rows[k[1]]['reference_key']]['result']['observables'][key] for k in d['native_keys']])
        mesh_differences.append(dict(path=d['path'], quantity=key, maximum=float(max(abs(predicted-coarse)))))
        comparisons.append(dict(path=d['path'], name=d['name'], kind=d['kind'], quantity=d['quantity'],
                                units='m' if key == 'h_m' else 'deg', count=len(delta),
                                loads=values[:, 1].tolist(), measured=values[:, 0].tolist(), predicted=predicted.tolist(),
                                independent=ref.tolist(), errors=delta.tolist(), rmse=float(np.sqrt(np.mean(delta**2))),
                                maximum_absolute_error=float(max(abs(delta))),
                                rmse_over_maximum_measured_magnitude=float(np.sqrt(np.mean(delta**2))/max(abs(values[:, 0]))),
                                chord_angle_alternative=[rows[k[1]]['result']['observables']['chord_vertical_dunn_deg'] for k in d['native_keys']]))
    assert sum(c['count'] for c in comparisons) == 160
    mesh = []
    grouped = {}
    for row in rows.values():
        spec = row['identity']['specification']; key = (spec['name'], spec['force_N'], spec['couple_Nm'])
        grouped.setdefault(key, {})[spec['panels']] = row
    symmetry = []
    for key, meshes in grouped.items():
        if set(meshes) != {8, 16, 32, 64}: continue
        item = dict(name=key[0], force_N=key[1], couple_Nm=key[2], quantities={})
        for quantity in ['h_m', 'theta_dunn_deg']:
            values = [meshes[n]['result']['observables'][quantity] for n in [8, 16, 32, 64]]
            changes = np.diff(values)
            orders = [float(np.log2(abs(changes[i]/changes[i+1]))) if min(abs(changes[i:i+2])) > 1e-10 else None for i in [0, 1]]
            item['quantities'][quantity] = dict(values=values, changes=changes.tolist(), observed_orders=orders)
        mesh.append(item)
        reverse = grouped[(key[0], -key[1], -key[2])][64]['result']['observables']
        symmetry.append({q: meshes[64]['result']['observables'][q]+reverse[q] for q in ['h_m', 'theta_dunn_deg']})
    assert len(mesh) == 18 and max(abs(v) for r in symmetry for v in r.values()) < 2e-8

    # Archived last full ASWING output: the final negative-coupling moment case.
    path = next(p for p in study['sources'] if p.endswith('/temp.txt'))
    table = parse_archived_span_table((cache/path).read_text())
    assert len(table) == 45 and table[0, 0] == .0001 and table[-1, 0] == .558
    archived = next(r for r in study['archived_final_weights'] if r['name'] == 'm15_0')
    row = rows[archived['native_key']]; native = row['result']['result']; tip = native['nodes'][-1]
    nodal = np.array([[n['t'], n['position'][1], n['position'][2], observables(np.array(n['position']), np.array(n['rotation']))['twist_asw_deg']] for n in native['nodes']])
    interpolated = np.c_[np.interp(table[:, 0], nodal[:, 0], nodal[:, 1]), np.interp(table[:, 0], nodal[:, 0], nodal[:, 2]), np.interp(table[:, 0], nodal[:, 0], nodal[:, 3])]
    output = dict(path=path, native_key=archived['native_key'], rows=len(table),
                  printed_columns=['t', 'y', 'z-z0', 'tw-tw0', 'Mc_scaled', 'Ms_scaled', 'Fn_scaled', 'cl', 'a_flap'],
                  raw_values=table.tolist(), native_interpolated_y_z_twist=interpolated.tolist(),
                  maximum_span_difference=dict(zip(['y_m', 'z_m', 'twist_deg'], np.max(abs(interpolated-table[:, 1:4]), axis=0).tolist())),
                  printed_tip_y_z_twist=table[-1, 1:4].tolist(), native_tip_y_z_twist=[tip['position'][1], tip['position'][2], row['result']['observables']['twist_asw_deg']],
                  printed_applied_moment=[-.02067, .6940, 0.], native_applied_moment=native['applied_moment'],
                  limitation='Printed stations and responses are rounded; span interpolation is a comparison, not exact discrete ASWING parity.')
    eps_summary = []
    for fig in eps['figures']:
        matched = [r for r in eps['comparisons'] if r['figure'] == fig['path'] and r['status'] == 'compared']
        eps_summary.append(dict(path=fig['path'], compared_vertices=len(matched),
                                maximum_absolute_difference=max(abs(r['difference']) for r in matched),
                                units='m' if fig['quantity'] == 'Z' else 'deg'))
    primary = dict(title='Dunn, Nonlinear stall flutter of wings with bending-torsion coupling (1992)',
                   url='https://dspace.mit.edu/entities/publication/55aa429a-7a4a-4908-87e6-7ecc1ece5ae5',
                   pdf_sha256='4a2f76f6d51b5562a9a7ab7390c71adea8c792235eb4266bef38205d335d8e0d',
                   pages=dict(setup_pdf=[107, 108, 109], static_results_pdf=[115, 116, 117, 118, 119, 120, 121]),
                   facts=['Vertical clamped specimen; pulley/thread/weight tip loads and opposite chord-edge forces for torque.',
                          'Static measurements use pointer positions; the plotted displacement unit is cm and torque unit is Nm.',
                          'Archived CSV displacements are in m; both signed load branches and their offsets are retained.',
                          'The primary experiment has self-weight; the horizontal ISAE input zeros all distributed mass.',
                          'No full uncertainty budget or exact pulley geometry is available; no measurement uncertainty is invented.'],
                   redistribution='Primary PDF, extracted text and rendered pages excluded from distributions.')
    audit = dict(primary=primary, archived_torque_factor=study['archived_torque_factor'],
                 torque_derivation='change_mass writes +M and -M into Mg rows multiplied by 9.81; points are separated by 0.14 m, giving M_actual=9.81*0.14*M_plotted before rotation.',
                 caveat='The rotating force couple is a dead-force pair; its body-axis torque changes with wing rotation.',
                 original_postprocessing=['All central experimental points overwritten with zero.', 'Positive/negative branches folded by absolute value; half-range bars are branch differences, not a statistical uncertainty.',
                                          'Force twist plotted with ASWING sign, opposite the signed Dunn CSV convention.', 'Coupled moment displacement plotted as +body z; signed Dunn displacement is -body z.',
                                          'T(F) and Z(M) saved EPS limits differ from final Analysis.m commands; actual vector ticks were used.',
                                          'Uncoupled force-twist analysis filename has lowercase _num.csv; Analysis.m requests uppercase _NUM.csv.'],
                 static_reconstruction='For a negative weight w at lever r, use positive |w| at -r plus a central force 2*(0,0,-w). Force and moment are identical for every rotation Q. This equivalence does not extend to inertia or dynamics.',
                 property_warning='Static properties are taken from the static files, not the different modal files. All three internal Name fields are identical; paths and hashes identify layups.',
                 scripts_executed=False, sources=study['sources'],
                 ui_limit='Current bridge constructs a positive-speed FlightCondition for mounted solves. This study uses condition=None in the production Python API; no vacuum-static UI workflow or literal signed-weight support is claimed.')
    checks = dict(status='PASS_NUMERICAL_CHECKS_WITH_EXPERIMENTAL_DISCREPANCIES', modules=modules,
                  native_solves=len(rows), independent_load_cases=len(references), experimental_samples=160,
                  maximum_residual=max_residual, maximum_force_balance_N=force_balance, maximum_moment_balance_Nm=moment_balance,
                  finest_reference_error=dict(displacement_m=max_ref_h, twist_deg=max_ref_t),
                  reference_errors=reference_errors, mesh_refinement=mesh, measurement_mesh_changes=mesh_differences,
                  load_reversal_errors=symmetry, experiment_comparisons=comparisons, archived_eps_summary=eps_summary,
                  archived_full_output=output, wasm_cases=len(wasm['cases']),
                  wasm_maximum_position_difference_m=max(r['maximum_differences']['position'] for r in wasm['cases']),
                  wasm_maximum_rotation_difference=max(r['maximum_differences']['rotation'] for r in wasm['cases']),
                  tests=dict(passed=int(tests[1]), time=tests[2], log_sha256=sha(args.test_log), test_sha256=sha(ROOT/'tests/test_isae_st3_static_reference.py')),
                  evidence_sha256={n+'.json': sha(DEST/(n+'.json')) for n in ['isae-st3-static', 'isae-st3-static-eps', 'isae-st3-static-wasm']},
                  script_sha256=sha(Path(__file__)), full_suite_validated=False, goal_complete=False)
    (DEST/'isae-st3-static-sources.json').write_text(json.dumps(audit, indent=2)+'\n')
    (DEST/'isae-st3-static-checks.json').write_text(json.dumps(checks, indent=2)+'\n')
    report(study, checks, eps_summary)
    plot(study, checks)
    print(json.dumps({k: checks[k] for k in ['status', 'native_solves', 'independent_load_cases', 'maximum_residual', 'maximum_force_balance_N', 'maximum_moment_balance_Nm', 'finest_reference_error', 'wasm_cases', 'tests']}, indent=2))


def report(study, c, archived):
    lines = ['# ISAE ST-3 static validation', '',
        '**Partial validation: numerical checks pass; experimental agreement does not.** Three composite cantilevers are compared under signed tip forces and tip force couples. The production kernel is unchanged. Earlier [modal comparisons](isae-st3.md) and the [dense solver repair](dense-staircase.md) remain separate evidence.', '',
        '## Main findings', '',
        f"All **{c['native_solves']} native solves** converge, including every one of the **160 raw experimental samples** at two meshes. At 64 requested intervals, the maximum difference from an independently implemented continuous nonlinear Kirchhoff rod is **{c['finest_reference_error']['displacement_m']*1000:.4f} mm** in tip displacement and **{c['finest_reference_error']['twist_deg']:.6f}°** in twist. These are discretization checks, not experimental errors.", '',
        'The archived MATLAB scripts pass plotted torque values directly as kilograms in opposite Weight rows, with a 9.81 multiplier and 0.14 m arm separation. Their undeformed applied torque is therefore **1.3734 × the labeled torque**. The reconstructed archived setup and the correctly scaled nominal experimental force couple are kept separate; the original input and measured data are not edited.', '',
        'OpenSwing closely reproduces the archived ASWING curves at the archived loads. Correcting the torque removes a setup error but leaves substantial disagreement with experiment. No stiffness, geometry, load offset or tolerance is fitted to measured responses.', '',
        '## Experimental discrepancies', '',
        'The table uses each CSV sample at its original signed load, including the digitized origin. Displacements are reported in mm and twist in degrees. Positive and negative branches are not folded or averaged. The angle reported is material Euler twist; the alternative vertical chord angle is retained in the checks because the exact pointer reduction is not fully specified.', '',
        '| Laminate | Loading | Response | Samples | RMSE | Maximum absolute error |', '|---|---|---|---:|---:|---:|']
    for r in c['experiment_comparisons']:
        scale = 1000 if r['quantity'] == 'Z' else 1
        units = 'mm' if scale == 1000 else 'deg'
        lines.append(f"| {r['name']} | {'Force' if r['kind']=='F' else 'Force couple'} | {'Displacement' if scale==1000 else 'Twist'} ({units}) | {r['count']} | {r['rmse']*scale:.3f} | {r['maximum_absolute_error']*scale:.3f} |")
    lines += ['', '![Signed force and torque comparisons](isae-st3-static-comparison.png)', '',
        'The independent rod uses the archived beam properties. Agreement with it verifies those beam equations, not whether those equations/properties represent the low-aspect-ratio composite specimens. The primary experiment used vertically clamped specimens and pulley loads; ISAE rotated the model horizontally and removed its distributed mass. Fairing/warping effects, fixture/load details, specimen differences, pointer reduction and measurement uncertainty remain unresolved.', '',
        '## Archived ASWING comparison', '',
        'Red ASWING polylines are decoded directly from the plain EPS vectors, using the saved tick positions and tick labels visually checked in ISAE Part 3 Figure 25. No PostScript or upstream MATLAB/shell code is executed. Clipped endpoints without a corresponding script sample are excluded and recorded. Five-significant-digit mass conversion is consistent with all three saved final input rows; the exact MATLAB version and intermediate input files are unavailable.', '',
        '| Archived curve | Compared vertices | Maximum difference |', '|---|---:|---:|']
    for r in archived:
        scale = 1000 if r['units'] == 'm' else 1
        lines.append(f"| {Path(r['path']).name} | {r['compared_vertices']} | {r['maximum_absolute_difference']*scale:.4f} {'mm' if scale==1000 else 'deg'} |")
    o = c['archived_full_output']
    lines += ['', f"The final archived full output is consistent with the negative-coupling file at its saved weight values. Its printed tip `(y,z,twist)` is `{o['printed_tip_y_z_twist']}`; OpenSwing gives `({o['native_tip_y_z_twist'][0]:.8f} m, {o['native_tip_y_z_twist'][1]:.8f} m, {o['native_tip_y_z_twist'][2]:.6f} deg)`. All {o['rows']} printed span rows are retained and compared. Printed station/response rounding and unknown archived discretization prevent a claim of exact ASWING discrete parity.", '',
        '## Numerical and portability checks', '',
        f"Meshes of 8, 16, 32 and 64 intervals test refinement and load reversal. The independent rod solves force/moment balance by DOP853 integration and shooting, with no OpenSwing physics imports. **22 tests pass**, including small-load coupled compliance, the exact uncoupled dead-couple equation `theta=(M L/GJ) cos(theta)`, integration refinement and arbitrary-rotation load equivalence. Maximum equilibrium residual is {c['maximum_residual']:.3g}; force and moment imbalance are {c['maximum_force_balance_N']:.3g} N and {c['maximum_moment_balance_Nm']:.3g} Nm.", '',
        f"**Eight actual Pyodide cases pass**, comparing every nodal position/rotation, applied loads, reactions and residuals. Maximum native/WASM position difference is {c['wasm_maximum_position_difference_m']:.3g} m; the rotation-matrix difference is {c['wasm_maximum_rotation_difference']:.3g}. All three literal signed-weight rejections are also reproduced.", '',
        '## Product limits and remaining work', '',
        'All three literal static files parse but their negative Weight rows are rejected during network setup. For this study only, a negative weight at lever r is represented by a positive weight at -r plus a compensating central force. This gives exactly the same static force and moment for every wing rotation. Its mass/inertia is different: the derived files must not be used for modal or time analysis.', '',
        'The runs call the production structured static solver with `condition=None`. The current browser bridge requires a positive-speed aerodynamic condition and does not expose this vacuum static workflow. Pyodide portability does not establish a browser UI workflow. Literal signed static-load compatibility and a vacuum-static UI remain to be implemented.', '',
        'ST-3 remains partial. Resolve the physical/source discrepancies and uncertainty before assigning experimental acceptance. Across the entire ISAE suite, ten of 41 families have partial quantitative comparisons and 31 still lack them. The full ASWING feature goal remains incomplete.', '',
        '## Sources and reproduction', '',
        '[Primary Dunn thesis](https://dspace.mit.edu/entities/publication/55aa429a-7a4a-4908-87e6-7ecc1ece5ae5), static setup/results on printed pages 81–95; [pinned ISAE repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/f62943df20e9e4d7d9f50e070477b22426b5f865). The primary PDF, extracted text and screenshots are excluded from redistribution.', '',
        'Run the fetch scripts first, then:', '', '```sh',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-isae-st3-static.py',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/extract-isae-st3-static.py',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_isae_st3_static_reference.py > /tmp/st3-static-tests.log',
        'node scripts/test-isae-st3-static-wasm.mjs',
        '.venv/bin/python scripts/summarize-isae-st3-static.py --test-log /tmp/st3-static-tests.log', '```', '',
        'Evidence: [native runs](isae-st3-static.json), [checks and errors](isae-st3-static-checks.json), [source audit](isae-st3-static-sources.json), [archived vectors and replays](isae-st3-static-eps.json), [WASM](isae-st3-static-wasm.json). Source/input/module hashes identify every run; caches resume only identical runs. Raw evidence is in `isae-st3-static-20261014-raw.zip`.', '']
    (DEST/'isae-st3-static.md').write_text('\n'.join(lines))


def plot(study, checks):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(4, 3, figsize=(12, 13))
    names = ['0_3_90', 'p15_0', 'm15_0']
    for c, name in enumerate(names):
        for row, (kind, quantity) in enumerate([('F', 'Z'), ('F', 'THETA'), ('M', 'Z'), ('M', 'THETA')]):
            ax = axes[row, c]; r = next(r for r in checks['experiment_comparisons'] if (r['name'], r['kind'], r['quantity']) == (name, kind, quantity))
            order = np.argsort(r['loads']); loads = np.array(r['loads'])[order]; scale = 1000 if quantity == 'Z' else 1
            ax.scatter(r['loads'], np.array(r['measured'])*scale, color='#222222', s=23, label='Raw experiment', zorder=4)
            ax.plot(loads, np.array(r['predicted'])[order]*scale, color='#0072B2', label='OpenSwing, 64 intervals')
            ax.plot(loads, np.array(r['independent'])[order]*scale, color='#E69F00', ls='--', label='Independent nonlinear rod')
            d = next(d for d in study['datasets'] if (d['name'], d['kind'], d['quantity'], d['category']) == (name, kind, quantity, 'Dunn_analysis_digitization'))
            raw = np.array(d['values']); ix = np.argsort(raw[:, 1])
            ax.plot(raw[ix, 1], raw[ix, 0]*scale, color='#009E73', ls=':', label='Dunn analysis digitization')
            ax.axhline(0., color='gray', lw=.5); ax.axvline(0., color='gray', lw=.5); ax.grid(alpha=.2)
            ax.set_xlabel('Signed tip force (N)' if kind == 'F' else 'Signed nominal force couple (Nm)')
            ax.set_ylabel('Tip displacement (mm)' if quantity == 'Z' else 'Tip material twist (deg)')
            if row == 0: ax.set_title(name)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .955), ncol=2, frameon=False)
    fig.suptitle('ST-3: raw signed measurements versus the archived beam at nominal loads\nNumerical agreement does not imply experimental validation', fontsize=13, y=.99)
    fig.tight_layout(rect=(0, 0, 1, .915))
    for ext in ['svg', 'png']: fig.savefig(DEST/('isae-st3-static-comparison.'+ext), dpi=150)
    plt.close(fig)


if __name__ == '__main__': main()
