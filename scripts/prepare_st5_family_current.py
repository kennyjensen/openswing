"""Prepare every distinct archived ST-5 static snapshot for bounded serial replay.

Uses the existing decoders and full-row recovery. No source file or target is
rewritten. The two grids are sensitivity comparisons of the same observations.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import verify_st5_current as common

ROOT, read, write, pin = common.ROOT, common.read, common.write, common.pin
suite = common.load_module(ROOT/'scripts/isae_suite_structure.py', 'st5_existing_catalog')


def prepare(out):
    assert not out.exists(), 'Preserve prior preparations and attempts.'
    prior = ROOT/'artifacts/isae/st5-current-20261109/rigid-20lb-80-20'
    prior_study = read(prior/'study.json')
    common.unchanged(prior_study['pins']); common.unchanged(prior_study['source_pins'])
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    references = []
    for item in catalog['files']:
        if item['id'] in ('isae-part-3','drela-steady'):
            for field,digest in [('local_pdf','sha256'),('local_text','text_sha256')]:
                path = ROOT/item[field]
                assert pin(path)['sha256'] == item[digest]
                references.append(path)
    out.mkdir(parents=True)
    cases = []
    for case in (c for c in suite.CASES if c.startswith('st5')):
        if case == 'st5-20lb_80_20':
            for level in (0,1):
                receipt = read(prior/f'run-{level}/execution.json')
                assert receipt['exit_code']==0 and receipt['reaped'] and not receipt['timed_out']
                common.unchanged(receipt['outputs'])
            cases.append(dict(case=case, directory=str(prior), reused_current_states=2,
                              rows=80, structural_targets=1120))
            continue
        folder = out/case
        folder.mkdir()
        target,dependencies,origin = suite._target(ROOT,case)
        common.unchanged(target['source_pins']); common.unchanged(dependencies)
        target_path = folder/'target.json'
        write(target_path,target)
        source = suite._source(ROOT,case).resolve()
        assert pin(source)['sha256'] == target['source_pins'][0]['sha256']
        if case in suite.ROLLER_CASES:
            helper = common.load_module(ROOT/'scripts/verify-isae-st5-roller.py','st5_roller_setup')
            text,patches,_ = helper.generated(source,target_path,common.helper)
        elif case in suite.FORWARD_CASES:
            helper = common.load_module(ROOT/'scripts/verify-isae-st5-forward.py','st5_forward_setup')
            text,patches = helper.generated(source,target_path)
        else:
            text,patches,_ = common.helper.generate(source,target_path)
        def replace(old,new):
            nonlocal text
            assert text.count(old)==1, (case,old)
            text=text.replace(old,new)
            patches.append(dict(before=old,after=new))
        replace('    records = []',
                "    records = [json.loads(Path(p).read_text()) for p in plan['retained_comparisons']]")
        gate="all_fine_mesh_gates_pass=all(v['passes'] for v in changes[-1]['measures'].values()),"
        replace(gate if gate in text else 'all_fine_mesh_gates_pass=None,',
                "all_fine_mesh_gates_pass=(all(v['passes'] for v in changes[-1]['measures'].values()) if changes else None),")
        text=text.replace('cold_solves=3, fresh_residuals=3,','cold_solves=1, fresh_residuals=1,')
        text=text.replace('cold_solves=len(records), fresh_residuals=len(records),','cold_solves=1, fresh_residuals=1,')
        compile(text,'<st5-current-family>','exec')
        (folder/'verifier.py').write_text(text)
        write(folder/'patches.json',patches)
        common.load_module(folder/'verifier.py','st5_prepare_'+case.replace('-','_')).prepare(folder)
        plan=read(folder/'plan.json')
        plans=[]
        for mesh in plan['meshes'][:2]:
            level=mesh['level']; child=folder/f'run-{level}';child.mkdir()
            single=deepcopy(plan)
            single.update(meshes=[mesh],retained_comparisons=[
                str(folder/f'run-{j}/level{j}/comparison.json') for j in range(level)])
            write(child/'plan.json',single);plans.append(child/'plan.json')
        paths=[Path(__file__),Path(common.__file__),Path(suite.__file__),
               ROOT/'docs/validation/aswing-authoritative-sources.json',*references,
               source,target_path,folder/'verifier.py',folder/'patches.json',folder/'plan.json',*plans,
               *[ROOT/'scripts'/n for n in ('verify-isae-st5-load-cases.py',
                   'verify-isae-st5-archived-output.py','verify-isae-st5-roller.py',
                   'verify-isae-st5-forward.py','extract-isae-st5-load-cases.py','assess-isae-st5-roller.py')],
               *[Path(p['path']) for p in dependencies],*sorted((ROOT/'openswing').glob('*.py'))]
        write(folder/'study.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),case=case,
            pins=[pin(p) for p in sorted(set(paths))],source_pins=target['source_pins'],
            target_origin=origin,limits=prior_study['limits'],comparison=prior_study['comparison'],
            source_decoder_failures=[v for v in target.get('source_decoder_diagnostics',target.get('checks',[]))
                                     if not v.get('passed',False)],
            scope='All archived rows and outputs retained. Structural predictions, prescribed zeros, echoes and unresolved display remain separate.'))
        rows=sum(b['row_count'] for b in target['beams'])
        cases.append(dict(case=case,directory=str(folder),reused_current_states=0,
                          rows=rows,structural_targets=14*rows))
    assert len(cases)==16
    write(out/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=cases,
        distinct_structural_targets=sum(c['structural_targets'] for c in cases),
        grids_per_target=2,new_serial_states=30,reused_current_states=2,
        acceptance='5% relative plus original half-last-place; unchanged physical and 0.1% mesh checks.',
        family_validated=False,primary_passes_added=0,
        qualification='Literal original rigid, elliptical, forward-only and type2 roller archives; not the modified in-plane link paper curve.'))
    print('Prepared all 16 cases; 30 new single-grid jobs, 2 authenticated current states reused.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    prepare(parser.parse_args().output.resolve())
