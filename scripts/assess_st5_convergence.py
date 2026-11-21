"""Independent saved-state and native-output audit of current ST-5 refinement."""
import argparse
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
STRUCTURAL=[*range(1,13),19,20]


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_pins(pins):
    for p in pins:
        path=Path(p['path'])
        assert path.stat().st_size==p['bytes'] and sha(path)==p['sha256'],path


def qualify(required,native_matches,states,mesh):
    """A partial or failed refinement never shrinks the native denominator."""
    assert 0<=native_matches<=required
    complete=sorted(states)==[0,1,2,3,4]
    physical=complete and all(states[i] is True for i in range(5))
    converged=(len(mesh)==14 and all(v is True for v in mesh.values()))
    return dict(required=required,passed=native_matches if physical and converged else 0,
                raw_native_matches=native_matches,physical_complete=physical,
                mesh_complete=converged,qualified=physical and converged)


def audit_case(out,entry,scope):
    import numpy as np
    folder=out/entry['case'];study=read(folder/'study.json')
    check_pins(study['pins'])
    old_plan=ROOT/entry['reference_plan'];assert sha(old_plan)==entry['reference_plan_sha256']
    original=read(old_plan);old=old_plan.parent
    target_path=Path(original['target']);target=read(target_path)
    assert sha(target_path)==original['target_sha256']
    source=ROOT/original['source'];assert sha(source)==original['source_sha256']
    check_pins(target['source_pins'])
    reference=next(Path(p['path']) for p in target['source_pins'] if p['path'].endswith('.txt') and 'isae-validation' in p['path'])
    lines=reference.read_text().splitlines();reference_rows=[(b,r) for b in target['beams'] for r in b['rows']]
    assert len(reference_rows)==entry['rows'] and 14*len(reference_rows)==entry['required']
    assert original['kernel_pins']=={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    # Exact verifier relation: the extension changes JSON whitespace only.
    expected=(old/'verifier.py').read_text().replace('json.dumps(value, indent=2, allow_nan=False)',
                                                   "json.dumps(value, separators=(',', ':'), allow_nan=False)")
    assert (folder/'verifier.py').read_text()==expected
    levels=[];states={};deformations={};inputs=[]
    for level in range(5):
        run=(old if level<2 else folder)/f'run-{level}'
        receipt_path=run/'execution.json'
        if not receipt_path.exists():continue
        receipt=read(receipt_path)
        if receipt.get('exit_code')!=0 or not receipt.get('reaped') or receipt.get('timed_out'):
            states[level]=False;continue
        check_pins(receipt['outputs']);inputs.append(dict(path=str(receipt_path),sha256=sha(receipt_path)))
        plan=read(run/'plan.json');mesh=plan['meshes'][0];assert mesh['level']==level
        result=read(run/f'level{level}/result.json');comparison=read(run/f'level{level}/comparison.json')
        assert len(comparison['rows'])==entry['rows']
        assert result['converged'] and result['structural_only'] and not result['strips']
        assert result['structural_operator']=='drela-steady-section-v1'
        assert result['equilibrium_state']['identity']['model_sha256']==original['source_sha256']
        assert result['structural_elements']==sum(mesh['intervals_by_beam'].values())
        fields=np.load(run/f'level{level}/fresh-fields.npz')
        fresh=float(np.max(abs(fields['residual'])))
        assert fresh==comparison['checks']['fresh_residual']
        assert fields['r'].shape==(result['structural_nodes'],3)
        for row in comparison['rows']:
            assert np.array_equal(fields['r'][row['node']],row['position'])
        fields.close()
        limits=scope['physical_gates'];checks=comparison['checks']
        physical=(fresh<=limits['fresh_and_stored_residual'] and result['residual']<=limits['fresh_and_stored_residual']
                  and max(map(abs,result['force_balance']))<=limits['force_and_moment_balance']
                  and max(map(abs,result['moment_balance']))<=limits['force_and_moment_balance']
                  and max(v for k,v in checks.items() if k in ('clamps','joint_position','joint_rotation'))<=limits['clamp_and_applicable_joint_gap'])
        assert bool(physical)==comparison['numerical_gates_pass']
        states[level]=bool(physical);matches=0;failures=[];deformation=[]
        errors={j:[] for j in STRUCTURAL}
        for (block,ref),row in zip(reference_rows,comparison['rows']):
            tokens=lines[ref['source_line']-1].split();assert tokens==ref['raw_tokens']
            assert (row['beam'],row['source_line'])==(block['beam'],ref['source_line'])
            values=[float(t)*s for t,s in zip(tokens,block['physical_multipliers'])]
            half=[float(Decimal(10)**Decimal(Decimal(t).as_tuple().exponent))/2*s for t,s in zip(tokens,block['physical_multipliers'])]
            assert row['expected']==values and row['half_last_place']==half
            for j in STRUCTURAL:
                error=abs(row['values'][j]-values[j]);passed=error<=scope['relative_allowance']*abs(values[j])+half[j]
                matches+=passed
                if values[j]:errors[j].append(100*error/abs(values[j]))
                if not passed:failures.append(dict(beam=block['beam'],source_line=ref['source_line'],column=target['columns'][j]['name'],
                    reference=values[j],actual=row['values'][j],absolute_error=error,relative_percent=100*error/abs(values[j]) if values[j] else None))
            jig=row['jig_frame']
            jig_phi=math.degrees(math.atan2(jig[2][1],jig[1][1]))
            jig_psi=-math.degrees(math.asin(max(-1.,min(1.,jig[0][1]))))
            v=row['values']
            reconstructed=[v[1],v[2]-row['jig_position'][1],v[3],v[4]-jig_phi,v[5],v[6]-jig_psi,*v[7:13],v[19],v[20]]
            assert all(math.isclose(x,y,rel_tol=2e-12,abs_tol=2e-12) for x,y in zip(reconstructed,row['structural_deformation']))
            deformation.append(row['structural_deformation'])
        deformations[level]=deformation
        timing=read(run/'timing.json') if level>=2 else None
        levels.append(dict(level=level,intervals=mesh['intervals_by_beam'],physical=physical,
            raw_native_matches=matches,required=entry['required'],failures=failures,
            median_nonzero_error_percent={target['columns'][j]['name']:statistics.median(errors[j]) if errors[j] else None for j in STRUCTURAL},
            checks=checks,timing=timing,solve_seconds=comparison['seconds']))
    changes=[]
    for coarse,fine in zip(range(4),range(1,5)):
        if coarse not in deformations or fine not in deformations:continue
        a,b=deformations[coarse],deformations[fine];fields={}
        for k,j in enumerate(STRUCTURAL):
            change=max(abs(x[k]-y[k]) for x,y in zip(a,b));envelope=max(abs(y[k]) for y in b)
            ratio=change/envelope if envelope else (0. if change==0 else None)
            fields[target['columns'][j]['name']]=dict(relative_change=ratio,passes=ratio is not None and ratio<=scope['convergence']['relative_limit'])
        changes.append(dict(coarse=coarse,fine=fine,fields=fields))
    final=next((c['fields'] for c in changes if [c['coarse'],c['fine']]==scope['convergence']['final_pair']),{})
    if final:
        saved=read(folder/'run-4/summary.json')['mesh_changes'][-1]['measures']
        for key,value in final.items():
            assert saved[key]['relative_change']==value['relative_change'] and saved[key]['passes']==value['passes']
    baseline=next(r for r in levels if r['level']==0)
    verdict=qualify(entry['required'],baseline['raw_native_matches'],states,{k:v['passes'] for k,v in final.items()})
    return dict(case=entry['case'],**verdict,levels=levels,mesh_changes=changes,
                mesh_passed=sum(v['passes'] for v in final.values()),mesh_required=14,receipts=inputs,
                study_sha256=sha(folder/'study.json'),target_sha256=sha(target_path),source_sha256=sha(source))


def audit(out,case=None):
    scope_path=ROOT/'docs/validation/isae-st5-mechanics-scope.json';scope=read(scope_path)
    entries=[r for r in scope['cases'] if case is None or r['case']==case]
    assert entries
    for entry in entries:
        dest=out/entry['case']/'assessment.json';assert not dest.exists()
        result=audit_case(out,entry,scope)
        result.update(observed_utc=datetime.now(timezone.utc).isoformat(),scope_sha256=sha(scope_path),assessment_script_sha256=sha(Path(__file__)))
        dest.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        print(json.dumps({k:result[k] for k in ('case','passed','required','qualified','mesh_passed','mesh_required')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--case')
    a=p.parse_args();audit(a.output.resolve(),a.case)
