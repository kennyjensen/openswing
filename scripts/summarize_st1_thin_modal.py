"""Review the thin ST-1 modes, including the documented first-torsion sign change."""
from pathlib import Path

import verify_st1_modal_mechanics as modal

common=modal.common
ROOT=common.ROOT
OUT=ROOT/'artifacts/isae/st1-thin-modal-reconstruction-20261109'


def run():
    common.bounded()
    import numpy as np
    from scipy.sparse import load_npz
    plan=common.read(OUT/'plan.json');common.authenticate(plan['pins'])
    source=ROOT/'reference/st1-minguet-1989/minguet-1989-thesis.txt'
    assert 'small negative portion' in source.read_text()
    review=dict(observed_utc=common.utc(),plan_sha256=common.sha(OUT/'plan.json'),
        script_sha256=common.sha(Path(__file__)),source_sha256=common.sha(source),
        change='For this strongly bent/coupled blade, select the lowest torsion-dominant mode without requiring zero twist sign changes. '
               'Retain the >55% activity criterion, bending/in-plane identification, mesh and pencil gates. '
               'No reference frequency enters mode selection.',
        basis='Minguet thesis pp127-128 explicitly describes a small negative part near the root in the first torsion mode of this bent specimen.',
        timing='Post-solve correction to an over-restrictive identification rule; original per-job selections and results remain intact.',
        targets='All ten literal report targets unchanged; down 3B=218 remains a mismatch. No target correction or tolerance change.')
    common.write(OUT/'identification-review.json',review)
    packets=[];audits=[]
    for i,job in enumerate(plan['jobs']):
        folder=OUT/f'job-{i}';receipt=common.read(folder/'report.json')
        assert receipt['plan_sha256']==common.sha(OUT/'plan.json') and receipt['job']==job
        for name,digest in receipt['artifacts'].items():assert common.sha(folder/name)==digest
        raw=common.read(folder/'result.json');a=load_npz(folder/'A.npz');m=load_npz(folder/'M.npz')
        base=raw['base'];c=plan['cases'][job['case']]
        q=np.array([n['rotation'] for n in base['nodes']]);t=np.array([n['t'] for n in base['nodes']])
        errors=[];fields={};classified=[]
        for mode in raw['modes']:
            lam=complex(*mode['eigenvalue'])
            for side in ('right','left'):
                v=np.array(mode[side]['real'])+1j*np.array(mode[side]['imag'])
                av,mv=(a@v,m@v) if side=='right' else (v.conjugate()@a,v.conjugate()@m)
                error=float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv)))
                assert error<1e-8;errors.append(error)
            if lam.imag<=1e-6:continue
            classified.append(modal.shape_activity(mode,base,c))
            parts=[]
            for name in ('displacement','rotation'):
                v=np.array([n[name]['real'] for n in mode['output']['nodes']])+1j*np.array([n[name]['imag'] for n in mode['output']['nodes']])
                parts.append(np.einsum('nji,nj->ni',q,v))
            fields[mode['index']]=np.column_stack(parts)
        assert classified==receipt['classified']
        selected={}
        for family,count in [('B',3),('T',1),('F',1)]:
            candidates=sorted((r for r in classified if r['family']==family),key=lambda r:r['frequency'])
            assert len(candidates)>=count
            for rank,r in enumerate(candidates[:count],1):
                if family!='T':assert r['internal_zeros']==rank-1
                selected[f'{rank}{family}']=r
        packets.append(dict(t=t,fields=fields,selected=selected,tip=receipt['tip_position']))
        audits.append(dict(job=job,equations=len(errors),max_action_error=max(errors),seconds=receipt['seconds'],
            peak_rss_kib=receipt['peak_rss_kib'],report_sha256=common.sha(folder/'report.json')))
        del raw
    rows=[];torsion_shapes=[]
    for case,coarse,fine in [('thin-up',packets[0],packets[1]),('thin-down',packets[2],packets[3])]:
        c=plan['cases'][case];t=coarse['t'];w=np.zeros(len(t))
        w[:-1]+=np.diff(t)/2;w[1:]+=np.diff(t)/2
        inertia=np.array([c['mass']]*3+[c['icc'],c['icc']+c['inn'],c['inn']])
        for label,expected in c['targets'].items():
            old,new=coarse['selected'][label],fine['selected'][label]
            f=fine['fields'][new['mode_index']]
            interp=np.column_stack([np.interp(t,fine['t'],f[:,j].real)+1j*np.interp(t,fine['t'],f[:,j].imag) for j in range(6)])
            u=(coarse['fields'][old['mode_index']]*np.sqrt(w[:,None]*inertia)).ravel()
            v=(interp*np.sqrt(w[:,None]*inertia)).ravel()
            mac=float(abs(np.vdot(u,v))**2/(np.vdot(u,u).real*np.vdot(v,v).real))
            change=abs(old['frequency']/new['frequency']-1)
            assert mac>.99 and change<.01
            error=abs(new['frequency']/expected-1)
            rows.append(dict(case=case,label=label,expected_Hz=expected,coarse_Hz=old['frequency'],fine_Hz=new['frequency'],
                error_percent=100*error,passed=error<=.05 and abs(old['frequency']/expected-1)<=.05,
                mesh_change_percent=100*change,shape_MAC=mac,activity_fractions=new['activity_fractions'],
                internal_zeros=new['internal_zeros'],mode_index=new['mode_index']))
        if case=='thin-up':
            for label,p in [('N40',coarse),('N80',fine)]:
                r=p['selected']['1T'];f=p['fields'][r['mode_index']][:,4]
                pivot=f[np.argmax(abs(f))];shape=(f*pivot.conjugate()/abs(pivot)).real
                shape/=max(abs(shape));assert min(shape)<-1e-3 and max(shape)>1e-3
                torsion_shapes.append(dict(mesh=label,span_from_clamp=((.28-p['t'])/.56).tolist(),normalized_twist=shape.tolist()))
    symmetry=[]
    for index,n in [(0,40),(1,80)]:
        up,down=packets[index],packets[index+2]
        pos_error=float(np.max(abs(np.array(up['tip'])*[-1,1,1]-down['tip'])))
        changes={label:abs(up['selected'][label]['frequency']/down['selected'][label]['frequency']-1) for label in up['selected']}
        assert pos_error<1e-10 and max(changes.values())<1e-8
        symmetry.append(dict(nominal=n,tip_mirror_error_m=pos_error,frequency_relative_differences=changes))
    passed=sum(r['passed'] for r in rows)
    common.write(OUT/'summary.json',dict(observed_utc=common.utc(),required=10,passed=passed,rows=rows,
        identification_review_sha256=common.sha(OUT/'identification-review.json'),pencil_audits=audits,
        orientation_symmetry=symmetry,torsion_shapes=torsion_shapes,
        nominal80_tip_sag_m=-packets[1]['tip'][2],report_tip_sag_m=.210,
        tip_sag_relative_error=abs(-packets[1]['tip'][2]/.210-1),
        original_strict_selection_passed=7,reviewed_selection_passed=passed,
        remaining_conflict='Thin-down 3B: literal Table3 218 Hz; postprocessor and up row 21.8 Hz. Literal cell retained.',
        primary_modal_before=11,primary_modal_after=11+passed,primary_modal_required=22,
        primary_archive_passes_added=0,production_physics_changed=False))
    print(dict(passed=passed,required=10,rows=rows,orientation_symmetry=symmetry,
        maximum_pencil_error=max(r['max_action_error'] for r in audits),maximum_mesh_change_percent=max(r['mesh_change_percent'] for r in rows),
        minimum_shape_MAC=min(r['shape_MAC'] for r in rows)),flush=True)


if __name__=='__main__':run()
