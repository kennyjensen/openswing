"""Independently recount original tokens and inspect saved ST5 roller mechanics.

No production imports, numerical solve, input repair or tolerance adjustment.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
CASES=('20lb_80_20','20lb_90_10','30lb_80_20','30lb_90_10')
GROUPS={'structural':list(range(1,13))+[19,20],
        'conditional_zero':list(range(13,19))+[22,24,26,27],
        'input_echo':[21,23], 'unresolved_f_reac':[25]}


def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stable(pins):
    for p in pins:
        assert Path(p['path']).stat().st_size==p['bytes'] and sha(p['path'])==p['sha256'],p['path']


def matvec(m,v): return [sum(a*b for a,b in zip(row,v)) for row in m]


def errors(rows,j):
    values=[100*abs(r['values'][j]-r['expected'][j])/abs(r['expected'][j]) for r in rows if abs(r['expected'][j])>1e-8]
    return dict(nonzero_values=len(values),median_percent=statistics.median(values) if values else None,
                maximum_percent=max(values,default=None),maximum_absolute=max(abs(r['values'][j]-r['expected'][j]) for r in rows))


def assess(stage):
    study=read(stage/'plan.json'); stable(study['pins'])
    source_paths=[stage/'plan.json',Path(__file__)]
    records={}; totals={k:dict(matches=0,total=0) for k in GROUPS}
    restored_moment_ulps=[]
    for case in CASES:
        folder=stage/case; target=read(folder/'target.json')
        output=next(Path(p['path']) for p in target['source_pins'] if p['path'].endswith('.txt'))
        original_lines=output.read_text().splitlines()
        levels=[]; all_rows=[]
        for level in range(3):
            run=folder/f'run-level{level}'; receipt=read(run/'execution.json')
            assert receipt['exit_code']==0 and receipt['process_reaped'] and not receipt['timed_out'] and receipt['physical_checks_pass']
            stable(receipt['outputs']); source_paths.append(run/'execution.json')
            path=run/f'level{level}'; result=read(path/'result.json'); comparison=read(path/'comparison.json')
            joint=read(path/'joint-mechanics.json')
            assert result['converged'] and result['structural_only'] and not result['strips']
            assert result['structural_operator']=='drela-steady-section-v1'
            assert comparison['numerical_gates_pass']
            assert len(comparison['rows'])==80
            counts={key:dict(matches=0,total=0) for key in GROUPS}
            pos=0
            for block in target['beams']:
                for original in block['rows']:
                    row=comparison['rows'][pos]; pos+=1
                    tokens=original_lines[original['source_line']-1].split()
                    assert tokens==original['raw_tokens'] and len(tokens)==28
                    assert row['source_line']==original['source_line'] and row['beam']==block['beam']
                    expected=[float(t)*s for t,s in zip(tokens,block['physical_multipliers'])]
                    half=[float(Decimal(10)**Decimal(Decimal(t).as_tuple().exponent))/2*s for t,s in zip(tokens,block['physical_multipliers'])]
                    assert row['expected']==expected and row['half_last_place']==half
                    assert row['difference']==[a-b for a,b in zip(row['values'],expected)]
                    flags=[abs(a-b)<=h for a,b,h in zip(row['values'],expected,half)]
                    assert flags==row['inside_printed_interval']
                    for key,columns in GROUPS.items():
                        counts[key]['matches']+=sum(flags[j] for j in columns)
                        counts[key]['total']+=len(columns)
                    node=result['nodes'][row['node']]
                    assert node['beam']==row['beam'] and node['t']==row['t_evaluated']
                    assert node['position']==row['position'] and node['jig_position']==row['jig_position']
                    assert row['values'][1:4]==[node['position'][0]-node['jig_position'][0],node['position'][1],node['position'][2]-node['jig_position'][2]]
            assert counts['structural']['matches']==comparison['structural_matches']
            all_rows+=comparison['rows']
            rollers=[r for r in result['reactions'] if r['kind']=='joint']
            assert len(rollers)==len(joint['reactions'])==2
            for original,restored in zip(rollers,joint['reactions']):
                assert original.keys()==restored.keys()
                for key in original:
                    if key not in ('moment','other_moment'):
                        assert original[key]==restored[key]
                    else:
                        # Capture stores v*(F*L), restoration divides by F*L,
                        # and reporting evaluates (v*F)*L. Those dimensional
                        # operations need not return identical binary64 bits.
                        # Limit this audit allowance to four ULPs; physical and
                        # original archived-output gates remain unchanged.
                        for a,b in zip(original[key],restored[key]):
                            ulps=abs(a-b)/max(math.ulp(a),math.ulp(b))
                            assert ulps<=4
                            restored_moment_ulps.append(ulps)
            free=[]; maximum_rotation=0.
            for r in rollers:
                assert r['type']==2
                assert r['force']==[0.,0.,0.] and r['other_force']==[0.,0.,0.]
                assert all(a+b==0 for a,b in zip(r['moment'],r['other_moment']))
                a,b=[result['nodes'][r[k]] for k in ('node','other_node')]
                rotation=max(abs(u-v) for x,y in zip(a['rotation'],b['rotation']) for u,v in zip(x,y))
                maximum_rotation=max(rotation,maximum_rotation)
                assert rotation<=1e-10
                d0=[v-u for u,v in zip(a['jig_position'],b['jig_position'])]
                rotated=matvec(a['rotation'],d0)
                free.append([v-u-w for u,v,w in zip(a['position'],b['position'],rotated)])
            maximum_translation=max(abs(v) for row in free for v in row)
            assert maximum_translation>1e-4, 'This case must exercise free joint translation.'
            assert max(abs(u-v) for a,b in zip(free,joint['free_translation']) for u,v in zip(a,b))<1e-14
            max_force=max(abs(sum(r['force'][i] for r in result['reactions'] if r['kind']=='ground')+result['applied_force'][i]) for i in range(3))
            assert max_force<=1e-7
            for k in totals:
                for key in ('matches','total'): totals[k][key]+=counts[k][key]
            levels.append(dict(level=level,counts=counts,seconds=comparison['seconds'],
                max_free_translation_ft=maximum_translation,max_joint_rotation_difference=maximum_rotation,
                physical_checks=comparison['checks'],
                errors={target['columns'][j]['name']:errors(comparison['rows'],j) for j in GROUPS['structural']},
                rows=comparison['rows']))
        changes=[]
        for coarse,fine in zip(levels[:-1],levels[1:]):
            measures={}
            for i,j in enumerate(GROUPS['structural']):
                a=[r['structural_deformation'][i] for r in coarse['rows']]
                b=[r['structural_deformation'][i] for r in fine['rows']]
                change=max(abs(u-v) for u,v in zip(a,b)); envelope=max(map(abs,b))
                relative=change/envelope if envelope else (0. if change==0 else None)
                measures[target['columns'][j]['name']]=dict(change=change,envelope=envelope,relative=relative,
                    passed=relative is not None and relative<=.001)
            changes.append(dict(coarse=coarse['level'],fine=fine['level'],measures=measures,
                passed=sum(m['passed'] for m in measures.values()),total=len(measures)))
        records[case]=dict(levels=[{k:v for k,v in r.items() if k!='rows'} for r in levels],mesh_changes=changes,
            all_mesh_errors={target['columns'][j]['name']:errors(all_rows,j) for j in GROUPS['structural']},
            finest_full_structural_rows=sum(all(row['inside_printed_interval'][j] for j in GROUPS['structural']) for row in levels[-1]['rows']),
            tip_values=[dict(beam=row['beam'],t=row['t_evaluated'],z=row['values'][3],z_reference=row['expected'][3],
                twist=row['values'][5],twist_reference=row['expected'][5]) for row in levels[-1]['rows'] if row['t_evaluated']==(3.335 if row['beam']==1 else 2.001)],
            decoder_checks_passed=study['cases'][case]['decoder_checks_passed'],
            decoder_checks_total=study['cases'][case]['decoder_checks_total'])
    assert sum(v['total'] for v in totals.values())==study['requested_slots']==25920
    report=dict(status='COMPLETE_ORIGINAL_ROLLER_COMPARISON_DIFFERENCES_RETAINED',goal_complete=False,
        family_validated=False,production_solver_changes=False,cases=records,counts=totals,
        all_printed_scalar_matches=sum(v['matches'] for v in totals.values()),all_required_slots=25920,
        qualified_matches_excluding_unresolved=sum(v['matches'] for k,v in totals.items() if k!='unresolved_f_reac'),
        physical_solves_passed=12,fresh_restored_residuals_passed=12,retries=0,
        restored_moment_roundtrip=dict(values=len(restored_moment_ulps),maximum_ulps=max(restored_moment_ulps),
            allowance_ulps=4,scope='Dimensional reaction moments only; all other reaction metadata/forces exact. Physical and archived gates unchanged.'),
        initial_audit_failure='assessment-attempt1: exact dimensional-reaction equality failed by one ULP; preserved with source and diagnosis; no solve repeated.',
        scope='Four original type2 joint load cases, all80rows/27outputs on3grids; original rigid results unchanged.',
        count_qualification='Conditional zeros and input echoes are not independent physical predictions. f_reac remains an unvalidated diagnostic even where its printed value matches.',
        evidence=[dict(path=str(p),sha256=sha(p)) for p in source_paths])
    with (stage/'assessment.json').open('w') as f: json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','evidence')},indent=2))
    for case,record in records.items():
        print(case, 'fine mesh',record['mesh_changes'][-1]['passed'],'/14',
            'fine median errors', {k:record['levels'][-1]['errors'][k]['median_percent'] for k in ('z-z0','tw-tw0','Mc_prime')})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',type=Path,required=True)
    assess(p.parse_args().stage.resolve())
