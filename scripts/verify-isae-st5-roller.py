"""Compare all four original ST5 Link_Joint snapshots, one bounded grid at a time.

The originals specify KJtype=2 (rotation matched, translation free), not a
pinned joint. Reuse the reviewed full-row structural recovery and preserve
every original value. No solver equation, input, load or tolerance is fitted.
"""
import argparse
from copy import deepcopy
from decimal import Decimal
import difflib
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
ARCHIVE = ROOT/'.reference/isae-validation'/REVISION
RELATIVE = Path('3 - Structure/CASE - ST5 Joined Wing')
CASES = ('20lb_80_20', '20lb_90_10', '30lb_80_20', '30lb_90_10')
POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-section-v1')
GATES = dict(residual=1e-8, force_and_moment_balance=1e-7,
             clamps_and_rigid_joints=1e-10, fine_structural_mesh_relative=1e-3)


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def stable(pins):
    for p in pins:
        assert pin(p['path']) == p, 'Changed evidence: '+p['path']


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def joint_rows(text):
    block = re.search(r'(?ms)^Joint\s*\n(.*?)^\s*End\s*$', text).group(1)
    return [list(map(float, line.split('!', 1)[0].split())) for line in block.splitlines()
            if line.strip() and not line.lstrip().startswith(('#', '%', '!'))]


def nonjoint_tokens(text):
    text = re.sub(r'(?ms)^Joint\s*\n.*?^\s*End\s*$', '', text)
    return [line.split('!', 1)[0].split() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith(('#', '%', '!'))]


def target_for(case, helper, columns, manifest):
    base = ARCHIVE/RELATIVE/'Link_Joint'
    name = 'JW_1_'+case
    sources = [base/(name+suffix) for suffix in ('.asw', '.sh', '.txt')]
    rigid = ARCHIVE/RELATIVE/'Rigid_Joint'/(name+'.asw')
    pins = []
    for path in [*sources, rigid]:
        p = pin(path); expected = manifest['files'][str(path.relative_to(ARCHIVE))]
        assert all(p[k] == expected[k] for k in ('bytes', 'sha256')), str(path)
        pins.append(p)
    model, driver, output = sources
    assert nonjoint_tokens(model.read_text()) == nonjoint_tokens(rigid.read_text())
    assert joint_rows(model.read_text()) == [[1., 2., 2.001, 2.001, 2.], [1., 2., -2.001, -2.001, 2.]]
    assert joint_rows(rigid.read_text()) == [[1., 2., 2.001, 2.001], [1., 2., -2.001, -2.001]]
    commands = driver.read_text().splitlines()
    assert commands[0].endswith(name+' <<EOF') and 'Aswing_R_5_92' in commands[0]
    assert [s.strip() for s in commands[1:] if s.strip()] == [
        'oper', 'x', 'k', 'v', '1 4 6 9 10 11 13 14 15 16 17 18 19 20 21 23 24 25 26',
        'w', name+'.txt', 'O', 'EOF']
    blocks = helper.observations(output)
    assert [b['row_count'] for b in blocks] == [44, 36]
    tables = helper.tables(model)
    header = output.read_text().splitlines()[:28]
    labels = ('Velocity', 'Alpha', 'Beta', 'Heading', 'Elev.', 'Bank', 'sum Fx', 'sum Fy', 'sum Fz',
              'sum Mx', 'sum My', 'sum Mz', 'Weight', 'Ux', 'Uy', 'Uz', 'Wx', 'Wy', 'Wz',
              'Udotx', 'Udoty', 'Udotz', 'Wdotx', 'Wdoty', 'Wdotz')
    globals_ = {}
    for label in labels:
        token = re.search(r'(?<!\w)'+re.escape(label)+r'\s*:\s*([-+\d.Ee]+)', '\n'.join(header)).group(1)
        value = Decimal(token)
        globals_[label] = dict(token=token, value=float(value), half=float(Decimal(5).scaleb(value.as_tuple().exponent-1)))
    for label in labels:
        if not label.startswith('sum ') and label != 'Weight':
            assert globals_[label]['value'] == 0, ('Nonzero archived motion/flow', label)
    diagnostics = []
    def check(name, ok, **details):
        diagnostics.append(dict(name=name, passed=bool(ok), **details))
    roots = {b['beam']: [r for r in b['rows'] if r['printed_t'] == 0] for b in blocks}
    alternatives = {}
    for convention in ('raw', 'historical_matlab', 'physical'):
        force, moment = [0.]*3, [0.]*3
        for beam in (1, 2):
            neg, pos = [r[convention] for r in roots[beam]]
            f = helper.sub(helper.mv(helper.frame(pos[4:7]), pos[10:13]), helper.mv(helper.frame(neg[4:7]), neg[10:13]))
            m = helper.sub(helper.mv(helper.frame(pos[4:7]), pos[7:10]), helper.mv(helper.frame(neg[4:7]), neg[7:10]))
            arm = helper.cross([helper.value(tables, beam, k, 0) for k in ('x', 'y', 'z')], f)
            force = [a+b for a,b in zip(force,f)]
            moment = [a+b+c for a,b,c in zip(moment,m,arm)]
        alternatives[convention] = dict(force=force, moment_about_origin=moment)
    for label, value in [('sum Fz', alternatives['physical']['force'][2]), ('sum My', alternatives['physical']['moment_about_origin'][1])]:
        ref = globals_[label]
        check('selective_root_balance_'+label, abs(value-ref['value']) <= ref['half'],
              decoded=value, reference=ref)
    for block in blocks:
        for row in block['rows']:
            if row['anchor_reason'] and 'rigid joint' in row['anchor_reason']:
                row['anchor_reason'] = row['anchor_reason'].replace('rigid joint', 'type-2 roller joint')
        assert all(math.isfinite(x) for row in block['rows'] for x in row['physical'])
        assert all(row['physical'][j] == 0 for row in block['rows'] for j in helper.CONDITIONAL)
        assert all(v == 0 for v in block['rows'][-1]['physical'][21:])
        for prop, col in (('chord',21), ('Cm',23)):
            check(f'beam{block["beam"]}_root_{prop}', roots[block['beam']][0]['physical'][col] == helper.value(tables,block['beam'],prop,0))
    rear = blocks[1]
    d = [helper.value(tables,2,k,2.001)-helper.value(tables,2,k,0) for k in ('x','y','z')]
    phi, psi = math.degrees(math.atan2(d[2],d[1])), math.degrees(math.atan2(-d[0],math.hypot(d[1],d[2])))
    check('rear_clamp_phi_scale', abs(roots[2][1]['physical'][4]-phi)<6e-6)
    check('rear_clamp_psi_scale', abs(roots[2][1]['physical'][6]-psi)<9e-6)
    for row in rear['rows']:
        bounds = helper.shell_interval(tables,row,rear['physical_multipliers'])
        for col, interval in zip((19,20),bounds):
            half = rear['printed_half_unit_by_column'][col]
            check(f'rear_row{row["row"]}_{helper.NAMES[col]}_printing_overlap',
                  interval[0]-half <= row['physical'][col] <= interval[1]+half,
                  value=row['physical'][col], propagated_interval=interval, half=half)
    return dict(schema='st5-original-roller-output-v1', case=case, source_pins=pins,
        acceptance='All archived ASWING output fields, with unchanged printed precision; experiments optional.',
        columns=columns, beams=blocks, header_lines=header, header_values=globals_, driver_lines=commands,
        joint_rows=joint_rows(model.read_text()), only_numerical_change_from_rigid='KJtype: omitted(0) to 2',
        source_decoder_diagnostics=diagnostics, root_balance_alternatives=alternatives,
        uncertainties=[
            'The literal type2 is a rotation-only roller according to the public guide. The historical 5.92 binary is unavailable; its behavior is not inferred from the directory name.',
            'No original NODE arrays or startup settings are available. Printed centers plus exact known anchors are prospective grids, not recovered historical nodes.',
            'Selective per-column scaling has root-balance/geometry/shell evidence, not original exporter source. Failed arithmetic diagnostics remain recorded without changing targets.',
            'All80 rows and27 outputs are retained:14 structural,10 conditional zero,2 input echo,1 unresolved f_reac diagnostic per row.',
            'Chord/Cm endpoint-value averaging is inherited as an explicitly conditional display hypothesis; f_reac scalar signed-weight law remains unverified.',
            'Signed distributed weights are literal static loads; no filename-based load normalization or negative-mass dynamics is used.',
            'Source beam policies are explicit. The source equilibrium and free translation are checked independently; a small residual does not establish archived agreement.'])


def generated(source, target, helper):
    text, patches, _ = helper.generate(source,target)
    old = text
    def replace(label, before, after):
        nonlocal text
        assert text.count(before) == 1, label
        text = text.replace(before,after)
        patches.append(dict(label=label,before=before,after=after))
    start = text.index('        clamp, joint_position, joint_rotation = [], [], []')
    end = text.index('        gates = plan[\'numerical_gates\']',start)
    replacement = '''        clamp, joint_rotation, free_translation = [], [], []
        for c in network.constraints:
            i, j = c['a'], c['b']
            if j is None:
                assert c['type'] == 0
                clamp += [float(np.max(abs(data['r'][i]-network.rj[i]))), float(np.max(abs(data['Q'][i]-np.eye(3))))]
            else:
                assert c['type'] == 2
                joint_rotation.append(float(np.max(abs(data['Q'][i]-data['Q'][j]))))
                free_translation.append((data['r'][j]-data['r'][i]-data['Q'][i]@(network.rj[j]-network.rj[i])).tolist())
        rollers = [r for r in data['reactions'] if r['kind'] == 'joint']
        assert len(rollers) == len(joint_rotation) == 2
        assert all(r['type'] == 2 for r in rollers)
        free_force = max(abs(v) for r in rollers for key in ('force','other_force') for v in r[key])
        couple_balance = max(abs(a+b) for r in rollers for a,b in zip(r['moment'],r['other_moment']))
        write(out/'joint-mechanics.json', dict(type=2, definition='rotation matched, translation free',
            free_translation=free_translation, reactions=rollers, force_max=free_force,
            couple_balance=couple_balance, rotation_max=max(joint_rotation)))
        assert free_force == 0. and couple_balance == 0.
        checks = dict(fresh_residual=float(np.max(abs(residual))), stored_residual=result['residual'],
            force_balance=float(np.max(abs(np.asarray(result['force_balance'])))),
            moment_balance=float(np.max(abs(np.asarray(result['moment_balance'])))),
            clamps=max(clamp), joint_rotation=max(joint_rotation))
'''
    replace('documented roller constraints and free reactions', text[start:end],replacement)
    replace('rotation-only gate', "('clamps', 'joint_position', 'joint_rotation')", "('clamps', 'joint_rotation')")
    replace('one-grid accounting', 'unresolved_display_entries=80, cold_solves=3, fresh_residuals=3,',
            'unresolved_display_entries=80, cold_solves=1, fresh_residuals=1,')
    replace('separate saved-only mesh assessment', "all_fine_mesh_gates_pass=all(v['passes'] for v in changes[-1]['measures'].values()),",
            "all_fine_mesh_gates_pass=None,")
    compile(text,'<st5-roller-verifier>','exec')
    diff = ''.join(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='reviewed-full-row-verifier',tofile='roller-one-grid-verifier'))
    return text,patches,diff


def prepare(stage):
    assert not stage.exists(), 'Do not overwrite a prepared study.'
    stage.mkdir(parents=True)
    manifest_path = ROOT/'.reference/isae-validation/manifest.json'
    manifest = read(manifest_path)
    assert manifest['revision'] == REVISION
    decoder = load(ROOT/'scripts/extract-isae-st5-load-cases.py','_roller_decoder')
    generator = load(ROOT/'scripts/verify-isae-st5-load-cases.py','_roller_generator')
    units = read(ROOT/'docs/validation/isae-st5-reference-target.json')['columns']
    columns = [dict(index0=i,name=n,physical_unit=units[i]['physical_unit']) for i,n in enumerate(decoder.NAMES)]
    paths = [Path(__file__),manifest_path,ROOT/'scripts/extract-isae-st5-load-cases.py',
        ROOT/'scripts/verify-isae-st5-load-cases.py',ROOT/'scripts/verify-isae-st5-archived-output.py',
        ROOT/'docs/validation/isae-st5-reference-target.json',ROOT/'.reference/aswing_doc.txt']
    paths += sorted((ROOT/'openswing').glob('*.py'))
    cases = {}
    for case in CASES:
        folder = stage/case; folder.mkdir()
        target = target_for(case,decoder,columns,manifest)
        write(folder/'target.json',target)
        source = Path(target['source_pins'][0]['path'])
        text,patches,diff = generated(source,folder/'target.json',generator)
        (folder/'verifier.py').write_text(text)
        write(folder/'patches.json',patches)
        (folder/'verifier.diff').write_text(diff)
        nodes = {str(b['beam']): sorted({r['printed_t'] if r['exact_anchor_t'] is None else r['exact_anchor_t'] for r in b['rows']}) for b in target['beams']}
        meshes = []
        for level in range(3):
            counts = {k:len(v)-1 for k,v in nodes.items()}
            meshes.append(dict(level=level,intervals_by_beam=counts,
                panels=dict(default=max(counts.values()),beams={k:dict(nodes=v) for k,v in nodes.items()})))
            nodes = {k:sorted(v+[(a+b)/2 for a,b in zip(v[:-1],v[1:])]) for k,v in nodes.items()}
        assert [sum(m['intervals_by_beam'].values()) for m in meshes] == [70,140,280]
        plan = dict(acceptance=target['acceptance'],source_sha256=sha(source),target_sha256=sha(folder/'target.json'),
            script_sha256=sha(folder/'verifier.py'),kernel_pins={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))},
            request=dict(action='solve',mode='structural'),numerical_gates=GATES,limitations=target['uncertainties'],
            numerics=POLICY,meshes=meshes,cold_solves=3,fresh_residuals=3)
        write(folder/'plan.json',plan)
        paths += [Path(p['path']) for p in target['source_pins']]
        paths += [folder/name for name in ('target.json','verifier.py','plan.json','patches.json','verifier.diff')]
        cases[case] = dict(meshes=[m['intervals_by_beam'] for m in meshes],
            decoder_checks_total=len(target['source_decoder_diagnostics']),
            decoder_checks_passed=sum(c['passed'] for c in target['source_decoder_diagnostics']),
            failed_decoder_checks=[c for c in target['source_decoder_diagnostics'] if not c['passed']])
    plan = dict(status='PREPARED',cases=cases,pins=[pin(p) for p in sorted(set(paths))],
        cold_solves=12,fresh_residuals=12,concurrency=1,blas_threads=1,child_timeout_seconds=180,
        child_address_space_bytes=512*1024**2,production_solver_changes=False,
        requested_slots=4*3*80*27,mesh_gate=.001,scope='All4original Link_Joint load snapshots; each3nested grids. No original model edited.')
    write(stage/'plan.json',plan)
    print(json.dumps({k:v for k,v in plan.items() if k!='pins'},indent=2))


def run(stage,case,level):
    study = read(stage/'plan.json'); stable(study['pins'])
    folder = stage/case; out = folder/f'run-level{level}'
    assert not out.exists(), 'Prior attempts are immutable.'
    if level:
        previous = read(folder/f'run-level{level-1}/execution.json')
        assert previous['exit_code'] == 0 and previous['physical_checks_pass']
        stable(previous['outputs'])
    out.mkdir()
    plan = deepcopy(read(folder/'plan.json'))
    plan['meshes'] = [plan['meshes'][level]]
    plan.update(cold_solves=1,fresh_residuals=1)
    write(out/'plan.json',plan)
    def limit():
        n=study['child_address_space_bytes']; resource.setrlimit(resource.RLIMIT_AS,(n,n))
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',**{k:'1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
    start=time.monotonic(); timed_out=False
    with (out/'run.log').open('w') as log:
        child=subprocess.Popen([sys.executable,str(folder/'verifier.py'),'run','--stage',str(out)],cwd=ROOT,env=env,
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limit)
        write(out/'process.json',dict(pid=child.pid,started_unix=time.time()))
        try: code=child.wait(timeout=study['child_timeout_seconds'])
        except subprocess.TimeoutExpired:
            timed_out=True; os.killpg(child.pid,signal.SIGTERM)
            try: code=child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL); code=child.wait()
    stable(study['pins'])
    passed=code==0 and read(out/'summary.json')['all_numerical_gates_pass']
    receipt=dict(case=case,level=level,exit_code=code,timed_out=timed_out,process_reaped=True,
        physical_checks_pass=passed,elapsed_seconds=time.monotonic()-start,
        peak_child_rss_KiB=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        outputs=[pin(p) for p in sorted(out.rglob('*')) if p.is_file()])
    write(out/'execution.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='outputs'}),flush=True)
    assert passed, 'Retained failure: stop before further refinement.'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--stage',type=Path,required=True)
    parser.add_argument('--case',choices=CASES)
    parser.add_argument('--level',type=int,choices=(0,1,2))
    args=parser.parse_args()
    if args.action=='prepare': prepare(args.stage.resolve())
    else:
        assert args.case is not None and args.level is not None
        run(args.stage.resolve(),args.case,args.level)
