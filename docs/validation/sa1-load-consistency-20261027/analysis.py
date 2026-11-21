"""SA1 saved coefficient/force consistency; stdlib only, no production imports."""
from pathlib import Path
from decimal import Decimal, localcontext
import ast
import hashlib
import itertools
import json
import math

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASELINE = ROOT / 'artifacts/isae/sa1-focused-baseline-20261027/report.json'
DETAIL = ROOT / 'artifacts/isae/sa1-basis-diagnostic-20261027'
ORACLE = ROOT / 'docs/validation/steady-aero-review-20261027/oracle.py'
AR, U, RHO, AREA = 5.9, 47.9, 1.2256, 5.9
CD0 = .00352562 + .00771413
QS = .5 * RHO * U**2 * AREA


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def token_interval(token):
    value = Decimal(token)
    radius = Decimal(5).scaleb(value.as_tuple().exponent - 1)
    return value - radius, value + radius


def outward(lo, hi):
    return [math.nextafter(lo, -math.inf), math.nextafter(hi, math.inf)]


def bounds(token):
    lo, hi = token_interval(token)
    return outward(float(lo), float(hi))


def interval_overlap(a, b):
    return max(a[0], b[0]) <= min(a[1], b[1])


def infer(values, alpha):
    angle = math.radians(alpha)
    cli_cm = (-4 * values['Cm'] - values['CDi'] * math.sin(angle)) / math.cos(angle)
    cli_e = math.sqrt(math.pi * AR * values['efficiency'] * values['CDi'])
    clp = values['CL'] - cli_cm
    cdp = values['CD'] - values['CDi']
    return dict(CLi_from_Cm=cli_cm, CLi_from_efficiency=cli_e,
                CLi_route_difference=cli_cm-cli_e, CLprofile=clp, CDprofile=cdp,
                profile_force_angle_degrees=math.degrees(math.atan2(clp, cdp)),
                profile_normal_to_wind_ratio=clp/cdp)


def inferred_intervals(tokens):
    b = {k: bounds(v) for k, v in tokens.items()}
    alo, ahi = map(math.radians, b['alpha'])
    # A sec(alpha)-D tan(alpha): stationary alpha=asin(D/A), if in interval.
    def range_cm(A, D):
        angles = [alo, ahi]
        if 0 <= D/A <= 1:
            stationary = math.asin(D/A)
            if alo <= stationary <= ahi:
                angles.append(stationary)
        return [(A-D*math.sin(a))/math.cos(a) for a in angles]
    cmlo = min(range_cm(-4*b['Cm'][1], b['CDi'][1]))
    cmhi = max(range_cm(-4*b['Cm'][0], b['CDi'][0]))
    cm_interval = outward(cmlo, cmhi)
    e_interval = outward(math.sqrt(math.pi*AR*b['efficiency'][0]*b['CDi'][0]),
                         math.sqrt(math.pi*AR*b['efficiency'][1]*b['CDi'][1]))
    # The implied moment is monotone in positive e and CDi. Its alpha extremum
    # is atan(CDi/CLi), included explicitly rather than assuming a corner rule.
    moments = []
    for d, e in itertools.product(b['CDi'], b['efficiency']):
        cli = math.sqrt(math.pi*AR*e*d)
        angles = [alo, ahi]
        stationary = math.atan2(d, cli)
        if alo <= stationary <= ahi:
            angles.append(stationary)
        moments.extend(-.25*(cli*math.cos(a)+d*math.sin(a)) for a in angles)
    implied_cm = outward(min(moments), max(moments))
    common = [max(cm_interval[0], e_interval[0]), min(cm_interval[1], e_interval[1])]
    assert common[0] <= common[1]
    return dict(CLi_from_Cm=cm_interval, CLi_from_efficiency=e_interval,
                CLi_interval_intersection=common,
                CLprofile=outward(b['CL'][0]-common[1], b['CL'][1]-common[0]),
                CDprofile=outward(b['CD'][0]-b['CDi'][1], b['CD'][1]-b['CDi'][0]),
                Cm_implied_by_efficiency=implied_cm,
                Cm_printed=b['Cm'],
                moment_efficiency_identity_rounding_compatible=interval_overlap(implied_cm, b['Cm']))


def force_normalization(tokens):
    q = Decimal('.5')*Decimal('1.2256')*Decimal('47.9')**2*Decimal('5.9')
    out = dict(model_qS_decimal=str(q))
    for force, coeff in [('lift', 'CL'), ('drag', 'CD')]:
        f, c = token_interval(tokens[force]), token_interval(tokens[coeff])
        with localcontext() as context:
            context.prec = 50
            implied = [f[0]/c[1], f[1]/c[0]]
        out[force] = dict(implied_qS_decimal_interval=list(map(str, implied)),
                          model_qS_in_printed_intervals=implied[0] <= q <= implied[1])
    return out


baseline = json.loads(BASELINE.read_text())
jobs = baseline['jobs']
assert len(jobs) == 22
assert {j['settings']['panels'] for j in jobs} == {200, 400}
first = jobs[0]
table = ROOT/first['table_path']
source_lines = table.read_text().splitlines()
source_pins = {p['path']: p for p in first['sources']}
for relative, expected in source_pins.items():
    assert pin(ROOT/relative) == expected

rows = []
for index in range(11):
    selected = [j for j in jobs if j['row_index'] == index]
    assert len(selected) == 2
    reference = selected[0]['reference_row']
    assert all(j['reference_row'] == reference for j in selected)
    assert source_lines[reference['line_number']-1].split() == reference['tokens']
    tokens = {k:v['token'] for k,v in reference['fields'].items()}
    native = {k:float(v) for k,v in tokens.items()}
    native_derived = infer(native, native['alpha'])
    intervals = inferred_intervals(tokens)
    meshes = []
    for j in sorted(selected, key=lambda x:x['settings']['panels']):
        predicted = j['result']['result']['predicted']
        derived = infer(predicted, native['alpha'])
        dc = {k:predicted[k]-native[k] for k in ('CL','CD','CDi','Cm','efficiency')}
        dc.update({k:derived[k]-native_derived[k] for k in ('CLi_from_Cm','CLprofile','CDprofile')})
        assert abs(dc['CL']-dc['CLi_from_Cm']-dc['CLprofile']) < 1e-14
        assert abs(dc['CD']-dc['CDi']-dc['CDprofile']) < 1e-14
        meshes.append(dict(panels=j['settings']['panels'], job_id=j['id'],
            predicted=predicted, inferred=derived, difference_from_native_centers=dc,
            CLi_relative_difference=derived['CLi_from_Cm']/native_derived['CLi_from_Cm']-1,
            CDi_relative_difference=predicted['CDi']/native['CDi']-1,
            efficiency_relative_difference=predicted['efficiency']/native['efficiency']-1,
            profile_lift_fraction_of_total_CL_error=dc['CLprofile']/dc['CL'],
            profile_errors_with_native_rounding={k:outward(derived[k]-intervals[k][1], derived[k]-intervals[k][0])
                                                for k in ('CLprofile','CDprofile')},
            normalized_force_error={k:predicted[k]-predicted[c]*QS for k,c in [('lift','CL'),('drag','CD')]}))
    rows.append(dict(row_index=index, line_number=reference['line_number'],
        raw_line=source_lines[reference['line_number']-1], tokens=tokens, native=native,
        native_inferred=native_derived, native_inferred_intervals=intervals,
        normalization=force_normalization(tokens), meshes=meshes))

# Extract just the already audited independent scalar law. Executing the script
# itself would replay all saved states and overwrite its separate result file.
tree = ast.parse(ORACLE.read_text())
namespace = {'math':math}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=='wpair'],
                        type_ignores=[]), '<retained-scalar-oracle>', 'exec'), namespace)
wpair = namespace['wpair']
detail = []
for path in sorted(DETAIL.glob('row*.json')):
    saved = json.loads(path.read_text()); result = saved['result']; job = saved['job']
    alpha = math.radians(job['condition']['alpha']); e = [math.cos(alpha),0,math.sin(alpha)]
    ell = [-math.sin(alpha),0,math.cos(alpha)]
    strips = result['strips']; nodes = [n['t'] for n in result['mesh_discretization']['beams'][0]['nodes']]
    gamma = [s['circulation'] for s in strips]
    basic_cd=[]; basic_cl=[]; stall_cd=[]; stall_cl=[]; raw_cd=[]; raw_cl=[]
    tangencies=[]; cl_values=[]; projection_ratios=[]
    for strip in strips:
        y=strip['position'][1]; ds=strip['length']; velocity=strip['relative_velocity']
        r=math.fsum(a*b for a,b in zip(velocity,ell))/U
        ratio=math.hypot(1,r)
        wcp=math.fsum(g*wpair(y,a,b,6.2832/(4*math.pi)) for g,a,b in zip(gamma,nodes,nodes[1:]))
        t=math.sin(alpha)+wcp/U*math.cos(alpha)
        cb=CD0*ratio*ds/AREA; cs=4*t*t/ratio*ds/AREA
        basic_cd.append(cb); basic_cl.append(cb*r); stall_cd.append(cs); stall_cl.append(cs*r)
        flift=[-RHO*strip['circulation']*velocity[2]*ds,0,RHO*strip['circulation']*velocity[0]*ds]
        fp=[f-l for f,l in zip(strip['force'],flift)]
        raw_cd.append(math.fsum(f*x for f,x in zip(fp,e))/QS)
        raw_cl.append(math.fsum(f*x for f,x in zip(fp,ell))/QS)
        tangencies.append(t);cl_values.append(strip['cl']);projection_ratios.append(r)
    sums={k:math.fsum(v) for k,v in [('basic_CDprofile',basic_cd),('basic_CLprofile',basic_cl),
            ('separation_CDprofile',stall_cd),('separation_CLprofile',stall_cl),
            ('raw_CDprofile',raw_cd),('raw_CLprofile',raw_cl)]}
    coefficients={k:result[k] for k in ('CL','CD','CLi','CDi','CDi_near','CDp','Cm','efficiency')}
    derived=infer(coefficients, job['condition']['alpha'])
    detail.append(dict(source=pin(path),job_id=job['id'],panels=job['panels'],
        alpha=job['condition']['alpha'],circulation_modes=job['condition']['circulation_modes'],
        coefficients=coefficients,decomposition=sums,
        identities=dict(CLi_moment_error=derived['CLi_from_Cm']-result['CLi'],
            CLi_efficiency_error=derived['CLi_from_efficiency']-result['CLi'],
            near_far_drag_error=result['CDi_near']-result['CDi'],
            profile_CD_formula_error=sums['basic_CDprofile']+sums['separation_CDprofile']-sums['raw_CDprofile'],
            profile_CL_formula_error=sums['basic_CLprofile']+sums['separation_CLprofile']-sums['raw_CLprofile'],
            profile_CD_global_error=sums['raw_CDprofile']-result['CDp'],
            profile_CL_global_error=sums['raw_CLprofile']-(result['CL']-result['CLi'])),
        minimum_section_cl=min(cl_values),maximum_section_cl=max(cl_values),
        minimum_normalized_cp_tangency=min(tangencies),maximum_normalized_cp_tangency=max(tangencies),
        minimum_wind_normal_velocity_ratio=min(projection_ratios),maximum_wind_normal_velocity_ratio=max(projection_ratios)))

assert len(detail)==6
assert all(r['native_inferred_intervals']['moment_efficiency_identity_rounding_compatible'] for r in rows)
assert all(r['normalization'][f]['model_qS_in_printed_intervals'] for r in rows for f in ('lift','drag'))
assert max(abs(v) for d in detail for v in d['identities'].values()) < 2e-12
output=dict(format='SA1_SAVED_LOAD_CONSISTENCY',version=1,
    scope=dict(native_rows=11,native_scalars=77,baseline_mesh_jobs=22,baseline_mesh_slots=154,
               detailed_saved_states=6,new_solves=0,production_imports=0,production_changes=0),
    source_pins=list(source_pins.values()),evidence_pins=[pin(BASELINE),pin(ORACLE),
        pin(ROOT/'.reference/asw_theory.txt'),pin(Path(__file__))],
    definitions=dict(CLi_from_Cm='(-4*Cm-CDi*sin(alpha))/cos(alpha)',
        CLi_from_efficiency='sqrt(pi*(Bref^2/Sref)*efficiency*CDi)',
        CLprofile='CL-CLi',CDprofile='CD-CDi',
        basic_CDprofile='sum((Cdf+Cdp)*sqrt(1+r_j^2)*ds_j/S)',
        separation_CDprofile='sum(4*t_j^2/sqrt(1+r_j^2)*ds_j/S)',
        profile_CL='Multiply each basic/separation CD summand by r_j.',
        r_j='V_hv dot lift_axis / U',t_j='V_cp dot physical_normal / U'),
    source_equations=[dict(path='.reference/asw_theory.txt',pages='16-17',equations='67,69,70,72',lines=[770,812]),
                      dict(path='.reference/asw_theory.txt',page=49,equations='207-211',lines=[2474,2495])],
    rows=rows,detailed_states=detail,
    checks=dict(all_original_lines_tokens_preserved=True,
        all_source_pins_match=True,all_11_moment_efficiency_identities_rounding_compatible=True,
        all_11_lift_and_drag_normalizations_rounding_compatible=True,
        maximum_six_state_identity_error=max(abs(v) for d in detail for v in d['identities'].values())),
    findings=[
        'All 11 original native moment/efficiency/induced-drag identities are compatible with their combined printed intervals. Their centered reconstructed CLi values need not be identical.',
        'All 11 original lift/CL and drag/CD pairs admit the exact unchanged model qS=8295.48524320 within the printed intervals. A single reference-area/density normalization error is not supported.',
        'At 400 intervals the CLi error is about +0.0577 percent at low incidence, crosses sign between 8.1351 and 10.103 degrees, and reaches -2.6545 percent at 18.091 degrees. The stall-region mismatch is not the same constant factor as the low-incidence bias.',
        'Inferred profile lift is compatible with native rounding through 12.1 degrees; from 14.097 degrees it is significantly more negative. At 18.091 degrees its center error accounts for only 0.3905 percent of the total CL error.',
        'Profile CD is significantly high from 10.103 degrees. At 18.091 degrees its +0.0036169711 error offsets the -0.0031484179 induced-drag error, leaving only +0.00046855318 total-CD error. Total drag alone hides these opposing component errors.',
        'The six retained full states verify the inferred CLi, near/far drag identity and direct Eq70 profile decomposition to 1.8e-15. At 18.091 degrees/400 intervals the basic profile CD is 0.0112697139 and separation contribution is 0.0213188572; no archived separate contributions are available.',
        'Efficiency error changes from about +0.1154 percent to -0.5840 percent across the curve. Uniform Gamma scaling leaves CLi^2/CDi invariant and cannot reconcile this difference; this diagnostic does not prescribe any scaling.',
        'The data identify the circulation-lift integral as the dominant high-incidence lift discrepancy. They cannot distinguish a historical Gamma-distribution difference from a force-integration or transfer difference, and do not prove a stall-law implementation defect.'
    ],
    qualifications=[
        'These inferred components are diagnostics, not new archived acceptance targets.',
        'Native inference assumes the documented straight planar wing identities, zero section Cm and reference at beam origin. Six detailed current states verify the same identities directly.',
        'Native intervals retain half-last-printed-place uncertainty, including alpha, CDi, efficiency and Cm; displayed center differences are not exact archive identities.',
        'CLi interval intersection is a conservative necessary range, not a recovered historical circulation distribution.',
        'Six detailed reference_checks are deliberately unused. Raw fields and strips supply all diagnostic quantities; diagnostic Lift/Drag naming has no effect here.',
        'No archive strip velocities, local tangency, Gamma or separated drag components exist in these seven-column targets. Their historical distributions and stall defaults cannot be recovered uniquely.',
        'A coefficient-error trend can distinguish a constant multiplier from nonlinear behavior but cannot identify a source algorithm change or justify fitting parameters.'
    ])
(HERE/'report.json').write_text(json.dumps(output,indent=2)+'\n')
md = '''# SA-1 coefficient and load consistency across the complete polar

All 11 native rows are internally compatible with the documented moment, induced-drag and span-efficiency identities once their printed intervals are propagated. The unchanged model normalization `qS=8295.48524320` also lies within every lift/CL and drag/CD pair's printed intervals. [The saved analysis](report.json) retains all original tokens, bounds, 22 current predictions and six detailed states; [the script](analysis.py) uses only retained data and the standard library.

For this straight planar wing with zero section Cm and the moment reference on its beam axis,
`CLi=(-4 Cm-CDi sin(alpha))/cos(alpha)` independently agrees with `sqrt(pi AR e CDi)` within native precision. The profile components then follow from `CLprofile=CL-CLi` and `CDprofile=CD-CDi`. These are inferred diagnostic quantities, not additional archived acceptance targets.

The table uses the 400-interval baseline. Component errors are current minus archived printed-center inference; the profile-lift compatibility column uses the full propagated native intervals.

| Alpha (deg) | CLi error (%) | CDi error (%) | Profile CL error | Profile CD error | Profile CL compatible with rounding? |
|---:|---:|---:|---:|---:|:---:|
'''
for row in rows:
    m=row['meshes'][1];d=m['difference_from_native_centers'];i=m['profile_errors_with_native_rounding']['CLprofile']
    md += f"| {row['native']['alpha']:g} | {100*m['CLi_relative_difference']:+.6f} | {100*m['CDi_relative_difference']:+.6f} | {d['CLprofile']:+.8g} | {d['CDprofile']:+.8g} | {'yes' if i[0]<=0<=i[1] else 'no'} |\n"
md += '''
The low-incidence lift bias and the stalled discrepancy have different shapes. CLi changes from about 0.0577% high to 2.6545% low. Profile lift remains compatible with native precision through 12.1 degrees, where CLi is already 0.7417% low. At 18.091 degrees, the total CL error of -0.028795796 consists of -0.028683352 circulation lift and -0.000112444 profile lift. The latter accounts for only 0.3905% of the total error. A profile-force projection adjustment cannot account for the dominant lift discrepancy.

Drag has substantial cancellation. At 18.091 degrees, the induced-drag error is -0.0031484179 and the profile-drag error is +0.0036169711, leaving a total-CD error of +0.00046855318. Total drag agreement alone would conceal this component mismatch. Current span-efficiency error changes from +0.1154% at low incidence to -0.5840% at 18.091 degrees. A uniform Gamma multiplier leaves efficiency invariant and cannot reconcile these values.

The six detailed saved states provide a direct additional check. With `r=V_hv dot lift_axis/U` and `t=V_cp dot normal/U`, Eq70 gives basic profile CD as `sum((Cdf+Cdp)*sqrt(1+r*r)*ds/S)` and separation CD as `sum(4*t*t/sqrt(1+r*r)*ds/S)`. Multiplying each summand by `r` gives its profile CL. The scalar horseshoe oracle supplies the control-point velocity independently. These sums and the moment/efficiency identities reproduce retained raw forces and coefficients within 1.8e-15. At 1.9971 degrees the separation contribution is negligible. At 18.091 degrees/400 intervals, basic profile CD is 0.0112697139 and separation CD is 0.0213188572. The archive does not retain a corresponding split.

This isolates the circulation-lift integral as the main high-incidence lift discrepancy, but does not recover historical Gamma. A historical circulation-distribution difference and a force-integration/transfer difference cannot be distinguished from these aggregate columns. The evidence neither identifies a historical stall parameter nor proves a production-law defect. No parameter was fitted, no frozen artifact was changed, and no new physical solve was performed. The six diagnostic reference-check packets were not used; their Lift/Drag naming issue does not affect this analysis.
'''
(HERE/'report.md').write_text(md)
for row in rows:
    m=row['meshes'][1];d=m['difference_from_native_centers']
    print(row['native']['alpha'],m['CLi_relative_difference'],d['CLprofile'],d['CDprofile'])
for d in detail:
    print(d['job_id'],d['decomposition'])
print('Saved',HERE/'report.json')
