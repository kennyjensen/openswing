from pathlib import Path
from decimal import Decimal
import hashlib,json
ROOT=Path('/home/userland/aswing');OUT=Path('/tmp/openswing-null-point-objects-20261027')
def pin(p):
 p=Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def write(name,data):
 (OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
base=ROOT/'.reference/isae-validation';manifest=json.loads((base/'manifest.json').read_text());cache=base/manifest['revision']
inputs=[]
for name,record in manifest['files'].items():
 if not name.endswith('.asw') or not ('CASE - ST2 Pazy_Wing/' in name or '/AE-1-S ' in name):continue
 p=cache/name;info=pin(p);assert info['sha256']==record['sha256']
 weights=[];inside=False;scales=[Decimal(1)]*17;adds=[Decimal(0)]*17
 for line_number,line in enumerate(p.read_text().split('\n'),1):
  text=line.split('!')[0].strip()
  if text.lower()=='weight':inside=True;continue
  if text.lower()=='end':inside=False
  if not inside or not text or text[0] in '#%':continue
  if text[0] in '*+':
   dest=[Decimal(1 if text[0]=='*' else 0)]*17
   for i,v in enumerate(text[1:].split(),1):dest[i]=Decimal(v)
   if text[0]=='*':scales=dest
   else:adds=dest
   continue
  tokens=text.split();values=[Decimal(0)]*17
  for i,v in enumerate(tokens):values[i]=Decimal(v)*scales[i]+adds[i]
  weights.append(dict(line_number=line_number,tokens=tokens,scaled_exact=[str(v) for v in values],null=all(v==0 for v in values[5:17])))
 assert len(weights)==2 and all(Decimal(w['scaled_exact'][1])==Decimal('.558') for w in weights)
 inputs.append(dict(source=info,beam_domain=['.0001','.55'],weights=weights,
  disposition='null records retained; no physical attachment needed' if all(w['null'] for w in weights) else 'active invalid anchors remain rejected'))
write('original-inputs.json',inputs)
ranges={
 '.reference/aswing_doc.txt':[(174,196),(199,214),(437,466),(602,616)],
 '.reference/ASWING_Extended_User_Manual.txt':[(2595,2632)],
 '.reference/asw_theory.txt':[(891,962),(1720,1729)],
 '.reference/asw_uns_theory.txt':[(460,478)],
 '.reference/isae-validation/reports/Experimental_validation_of_ASWING_Part_4_Aeroelasticity_V4.txt':[(441,476)],
 'openswing/asw.py':[(325,367),(531,557),(560,615)],
 'openswing/operating.py':[(156,175),(251,265)],
 'openswing/local_motion.py':[(186,193)],
 'openswing/source_coupled.py':[(72,104)],
 'openswing/source_dynamics.py':[(180,195)],
 'openswing/dynamic_inertia.py':[(54,62)],
 'openswing/geometry_partials.py':[(87,99)],
 'openswing/geometry_stencil.py':[(78,86)],
 'openswing/circulation_tangent.py':[(247,250)],
}
excerpts=[]
for name,spans in ranges.items():
 p=ROOT/name;lines=p.read_text().split('\n')
 excerpts.append(dict(source=pin(p),line_number_convention='1-based LF lines',excerpts=[dict(first_line=a,last_line=b,lines=[dict(line_number=i+1,text=lines[i]) for i in range(a-1,b)]) for a,b in spans]))
write('source-excerpts.json',excerpts)
changed=['openswing/point_objects.py','openswing/discretization.py','openswing/geometry.py','openswing/network.py','openswing/inertia.py','openswing/aero.py','openswing/volume.py','openswing/wall_root.py','tests/test_null_point_objects.py']
write('after-pins.json',[pin(ROOT/n) for n in changed])
test=dict(command='.venv/bin/python -m pytest -q tests/test_null_point_objects.py tests/test_asw.py tests/test_inertia.py tests/test_dynamic_inertia.py tests/test_volume.py tests/test_source_coupled.py tests/test_source_dynamic_inertia.py tests/test_steady_mass_loads.py',
 cwd=str(ROOT),shell_login=False,exit_code=0,passed=152,failed=0,skipped=0,duration_seconds=38.63,
 terminal_chunk_id='23794a',session_id=11056,session_reaped=True,
 new_test_count=43,standalone_ae1_equilibrium_solves=0,
 scope='Existing suites include their own bounded synthetic solves. New literal AE1 check constructs 80-interval mesh and a 4-interval source-coupled network and evaluates a finite residual, not an equilibrium acceptance pass.',
 prior_run=dict(command='.venv/bin/python -m pytest -q tests/test_null_point_objects.py',passed=38,failed=2,exit_code=1,duration_seconds=9.79,terminal_chunk_id='e49fc8',session_id=23073,session_reaped=True,
 reason='Two test assertions expected anchor error before existing negative CDA/Vol validation. Corrected assertions preserve both rejection checks; no physical gate was relaxed.'))
write('test-receipt.json',test)
report=dict(status='IMPLEMENTED_FOCUSED_TESTS_PASSED_FROZEN',scope='Null Weight analysis elimination; originals remain unchanged; no ISAE acceptance claim.',
 finding='Exact-zero physical fields define a mathematically null point object. Eliminating its physical attachment, flow queries and inertial contribution is supported by the equations, without inferring legacy executable behavior.',
 predicate=dict(fields={'5':'Weight','6':'CDA','7':'Vol','8:11':'Hx,Hy,Hz','11:17':'Ixx,Iyy,Izz,Ixy,Ixz,Iyz'},
 rule='Finite shape-(17,) scaled row and every row[5:17] exactly zero; no tolerance and no decision from Weight alone.',
 geometry='t and Xo/Yo/Zo define a massless rigid pylon, not independent stiffness or degrees of freedom. They cannot create a load when every physical coefficient vanishes.',
 preservation='Original row objects, .source and lossless dumps remain intact. Analysis lists preserve row identity and order among active objects; raw arrays passed with active point data are rejected by length guards.',
 parameter_edits='The selector is recomputed from current rows, so changing a physical field before constructing a new analysis activates the object and restores ordinary anchor checks.'),
 mathematical_basis=[
 'Manual aswing_doc.txt439–453: point object on massless rigid pylon; omitted fields default to zero.174–196 defines scaling then addition.',
 'Steady Eq95–96, asw_theory.txt957–959: mass*(g-a)+drag; arm cross force, spin gyroscopic torque, tensor angular-acceleration and gyroscopic torque. All vanish for zero mass,CDA,H,I regardless of finite pose/motion.',
 'Steady Eq164,1720–1729: point source and doublet strengths are CDA and Vol; Vol must also be zero to eliminate aerodynamic feedback.',
 'Unsteady Eq46–47, asw_uns_theory.txt460–478: same nullity under beam rates/accelerations. Engine force/moment terms belong to separately declared Engine objects, which remain active and separately anchored (manual602–616).',
 'State, time, circulation, flap and engine-control derivatives of these fixed-zero contributions are zero. Derivatives with respect to the physical Weight coefficients themselves need not be zero; no such design-parameter derivative is discarded. Current operating controls update FlightCondition control/power maps, not Weight records.'
 ],
 implementation=dict(shared_view='openswing/point_objects.py: active_weight_items and active_weights; null_weight exact predicate.',
 consumers=['discretization requirements','geometry attachment rendering','StaticNetwork and its source/dynamic subclasses','InertiaModel','evaluate_aerodynamics point/clearance/force order','VolumeField source and exclusion order','wall_root point-mask order'],
 inherited_consumers=['point_positions','NetworkMotion.point','source-discrete/source-coupled/source-dynamic point transfer','moving_mass_loads','GeometryPartials','GeometryStencil','GeometryFields','circulation_tangent','local_rate_tangent'],
 indices='Internal point arrays use contiguous active ordering. Original record numbers remain in mesh requirement labels and signed-weight diagnostics; InertiaModel.source_point_indices maps internal indices to original rows.',
 unused_raw_reads='asw_edit serialization/provenance and parser beam-reference validation intentionally retain raw records. Aero/quiescent validation still checks all declared physical fields; null rows trivially pass these checks.',
 no_anchor_motion=True,no_original_deletion=True),
 original_scope=dict(models=len(inputs),null_models=sum(all(w['null'] for w in x['weights']) for x in inputs),
 null_objects=sum(w['null'] for x in inputs for w in x['weights']),active_models=sum(any(not w['null'] for w in x['weights']) for x in inputs),
 AE1='Two null .558 records beyond .55. Original sensors are valid at .55. Literal mesh/network construction and residual evaluation now pass.',
 ST2_modal='Both original modal models have two entirely null rows. SourceDynamicNetwork setup passes; no modal or gravity-equilibrium acceptance asserted.',
 ST2_static='All four static cached model copies carry nonzero weights and remain blocked by .558 beyond .55. No correction, extrapolation or clamp.'),
 qualifications=['The documentation does not explicitly promise that legacy ASWING accepts invalid null anchors; this is an equation-based current analysis simplification.',
 'No native ASWING executable was used. Historical mesh/settings and AE1/ST2 archived-output parity remain separate validation tasks.',
 'Null objects no longer insert arbitrary interior mesh nodes. Explicit requested load/station, sensor, engine, strut, joint and ground requirements remain effective.',
 'Existing saved equilibria still undergo their normal identity/node checks; no saved result is relabelled as a new pass.',
 'All applicable existing nonnegative/PSD/undefined-beam checks remain. Tiny signed nonzero physical fields are never treated as zero.'],
 tests=test,changed_files=[pin(ROOT/n) for n in changed],source_pins=[x['source'] for x in excerpts]+[x['source'] for x in inputs])
write('report.json',report)
(OUT/'report.md').write_text('''Implemented and frozen: exact-zero Weight objects are omitted from the analysis view while their original records and source text remain intact.

A Weight is null only if all twelve scaled physical fields are exactly zero: Weight, CDA, Vol, Hx/Hy/Hz and all six inertia entries. Geometry alone defines a massless rigid pylon. Steady Eqs.95–96 eliminate its loads; Eq164 eliminates its aerodynamic source/doublet; unsteady Eqs.46–47 retain the same invariance. This supports mathematical elimination, not a claim about legacy ASWING accepting an invalid anchor.

One shared active ordering now feeds mesh requirements, attachment geometry, network/source/dynamic consumers, inertia, aerodynamics, volume influence and wall-root handling. Derivative consumers inherit that same ordering. Raw point arrays with an incompatible count are rejected. Original record numbers remain in mesh labels and signed-weight diagnostics. Nonzero weights, CDA, volume, spin or inertia remain active; no anchor moves or tolerance-based zeroing occur.

| Original scope | Result |
|---|---|
| AE1 Pazy, two null weights at .558 | Unchanged source constructs an 80-interval mesh; source-coupled setup and finite residual pass. |
| ST2 undeformed/gravity modal models, four null weights | Both source-dynamic setups pass; no modal acceptance claimed. |
| Four ST2 static model copies, eight nonzero weights | Out-of-range .558 anchors still reject. |

152 focused tests passed in 38.63 seconds, including 43 new checks. Tests distinguish every physical field (positive and negative tiny nonzero values), scaled/defaulted fields, later activation by edits, active/null indexing, aerodynamic and inertial residuals, geometry/circulation derivatives, flap/engine controls, original-source preservation and separate sensor/engine/external-load anchors. Two initial test assertions were corrected to recognize existing negative-CDA/Vol validation preceding anchor validation. No physical acceptance threshold changed.

No new standalone equilibrium solve was needed. Existing regression suites include their synthetic solves. Historical AE1/ST2 comparison remains to be run against the fresh kernel. Exact sources, seven original model pins, code pins and terminal receipts are in the adjacent JSON files.
''')
assert all(pin(x['source']['path'])==x['source'] for x in inputs)
assert all(pin(p['path'])==p for p in report['changed_files'])
receipt=dict(status='completed',production_and_tests_frozen=True,original_input_pins_unchanged=True,
 artifacts=[pin(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='receipt.json'])
write('receipt.json',receipt)
print(json.dumps(dict(report=pin(OUT/'report.json'),receipt=pin(OUT/'receipt.json'),changed_files=report['changed_files']),indent=2))
