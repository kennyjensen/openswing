"""Compare independently converged nested Flare20 meshes, without fitting.

The existing 0.1% root-moment gate is one spatial check, not all-field or
native-ASWING validation. Partial continuations cannot enter this comparison.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(Path(path).read_text())


def pin(path):
    path=Path(path).resolve();data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,required=True)
    p.add_argument('--fine-assessment',type=Path,required=True)
    p.add_argument('--coarse-assessment',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();study=args.study.resolve();plan=read(study/'study-plan.json')
    assert not args.output.exists(),'Preserve earlier assessments.'
    for record in [plan[k] for k in ('source','driver','request_baseline','coarse_result','coarse_verification','kernel_manifest','gate_source')]:
        assert pin(record['path'])==record,record['path']
    assert pin(study/'helper-at-execution.py')['sha256']==plan['helper']['sha256']
    def completed(path):
        audit=read(path)
        assert audit['status']=='COMPLETE_COLD_EQUILIBRIUM' and audit['complete']
        assert audit['final_load_fraction']==1. and audit['jobs']
        result_path=path.parent/audit['jobs'][-1]['job']/'result.json'
        assert pin(result_path)['sha256']==audit['jobs'][-1]['result_sha256']
        result=read(result_path);assert result['converged'] and result['residual']<=1e-12
        assert result['continuation_status']=='complete'
        assert audit['jobs'][-1]['rebuilt_residual']<=1e-12
        return audit,result,result_path
    ca,coarse,cp=completed(args.coarse_assessment.resolve())
    fa,fine,fp=completed(args.fine_assessment.resolve())
    assert len(fine['nodes'])>len(coarse['nodes'])
    # Every physical request field must agree; only discretization and job
    # bookkeeping may differ. The immutable plan already binds the source.
    cr,fr=read(cp.parent/'request.json'),read(fp.parent/'request.json')
    assert {k:v for k,v in cr.items() if k not in ('panels','continuation')}=={
        k:v for k,v in fr.items() if k not in ('panels','continuation')}
    match=[level for level in plan['levels'] if read(level['mesh']['path'])==fr['panels']]
    assert len(match)==1 and len(fine['nodes'])==match[0]['expected_nodes']
    assert pin(match[0]['mesh']['path'])==match[0]['mesh']
    for key in ('model_sha256','beam_interpolation','structural_operator','deformed_interval_measure','mesh_recipe'):
        assert coarse['equilibrium_state']['identity'][key]==fine['equilibrium_state']['identity'][key]
    def root(result):
        sensor=next(row for row in result['sensors'] if row['index']==1)
        assert (sensor['beam'],sensor['t'],sensor['load_trace'])==(1,0.,'left')
        return sensor['moment_local'][0]
    def difference(a,b):
        return dict(coarse=a,fine=b,absolute=abs(b-a),
                    relative=None if b==0 else abs(b-a)/abs(b))
    moment=difference(root(coarse),root(fine));assert moment['relative'] is not None
    gate=read(plan['gate_source']['path'])['gates']['mesh']
    assert gate==plan['mesh_gate']==.001
    moment.update(limit=gate,passed=moment['relative']<=gate,units='N m')
    hinges=[]
    for a,b in zip(coarse['hinges'],fine['hinges']):
        assert a['joint']==b['joint'] and a['axis_jig']==b['axis_jig']
        hinges.append(dict(joint=a['joint'],angle_deg=difference(a['angle_deg'],b['angle_deg'])))
    assert len(hinges)==len(coarse['hinges'])==len(fine['hinges'])==2
    fine_nodes={(n['beam'],n['t']):n for n in fine['nodes']}
    assert len(fine_nodes)==len(fine['nodes'])
    node_differences=[]
    for a in coarse['nodes']:
        key=(a['beam'],a['t']);assert key in fine_nodes
        b=fine_nodes[key];assert a['jig_position']==b['jig_position']
        displacement=math.sqrt(sum((x-y)**2 for x,y in zip(a['position'],b['position'])))
        chord=math.sqrt(sum((a['rotation'][i][j]-b['rotation'][i][j])**2 for i in range(3) for j in range(3)))
        angle=2*math.asin(min(1.,chord/(2*math.sqrt(2.))))
        node_differences.append(dict(beam=a['beam'],t=a['t'],displacement_change_m=displacement,rotation_change_rad=angle))
    result=dict(status='SPATIAL_COMPARISON_COMPUTED',coarse_nodes=len(coarse['nodes']),fine_nodes=len(fine['nodes']),
        root_moment=moment,hinges=hinges,coefficients={k:difference(coarse[k],fine[k]) for k in ('CL','CY','CDi','CDp','Cl','Cm','Cn')},
        shared_node_count=len(node_differences),shared_nodes=node_differences,
        maximum_displacement_change_m=max(n['displacement_change_m'] for n in node_differences),
        maximum_rotation_change_rad=max(n['rotation_change_rad'] for n in node_differences),
        inputs=[pin(p) for p in (study/'study-plan.json',args.coarse_assessment,args.fine_assessment,cp,fp,Path(__file__))],
        native_values_added=0,new_native_passes=0,all_field_mesh_accuracy_established=False,
        qualification='A converged equilibrium pair and one root-moment spatial gate; no time response, all-field accuracy or native ASWING agreement is implied.')
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('shared_nodes','inputs')}))


if __name__=='__main__':main()
