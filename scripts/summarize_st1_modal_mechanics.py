"""Recheck ST-1 modal evidence, mesh shapes and sampled load-branch identities."""
from pathlib import Path
import math

import verify_st1_modal_mechanics as main

common=main.common
ROOT=main.ROOT
OUT=ROOT/'artifacts/isae/st1-modal-mechanics-20261109'
BRANCH=ROOT/'artifacts/isae/st1-modal-branches-20261109'


def run():
    common.bounded()
    import numpy as np
    from scipy.sparse import load_npz
    for folder in (OUT,BRANCH):common.authenticate(common.read(folder/'plan.json')['pins'])
    plan=common.read(OUT/'plan.json');audit=[]
    def packet(folder,case,expected_plan):
        receipt=common.read(folder/'report.json');assert receipt['plan_sha256']==common.sha(expected_plan)
        for name,digest in receipt['artifacts'].items():assert common.sha(folder/name)==digest
        raw=common.read(folder/'result.json');a=load_npz(folder/'A.npz');m=load_npz(folder/'M.npz')
        errors=[];fields={};classification={}
        q=np.array([n['rotation'] for n in raw['base']['nodes']]);t=np.array([n['t'] for n in raw['base']['nodes']])
        for mode in raw['modes']:
            lam=complex(*mode['eigenvalue'])
            for side in ('right','left'):
                v=np.array(mode[side]['real'])+1j*np.array(mode[side]['imag'])
                av,mv=(a@v,m@v) if side=='right' else (v.conjugate()@a,v.conjugate()@m)
                errors.append(float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv))))
            if lam.imag<=1e-6:continue
            def values(name):return np.array([n[name]['real'] for n in mode['output']['nodes']])+1j*np.array([n[name]['imag'] for n in mode['output']['nodes']])
            fields[mode['index']]=np.column_stack([np.einsum('nji,nj->ni',q,values('displacement')),
                                                 np.einsum('nji,nj->ni',q,values('rotation'))])
            classification[mode['index']]=main.shape_activity(mode,raw['base'],plan['cases'][case])
        assert max(errors)<1e-8 and list(classification.values())==receipt['classified']
        audit.append(dict(path=folder.relative_to(ROOT).as_posix(),modes=len(raw['modes']),
                          max_pencil_action_relative_error=max(errors),report_sha256=common.sha(folder/'report.json')))
        return dict(t=t,fields=fields,classified=classification,receipt=receipt)
    def vector(p,index,case,t=None):
        native=p['t'];t=native if t is None else t;field=p['fields'][index]
        field=np.column_stack([np.interp(t,native,field[:,j].real)+1j*np.interp(t,native,field[:,j].imag) for j in range(6)])
        c=plan['cases'][case];weights=np.zeros(len(t));weights[:-1]+=np.diff(t)/2;weights[1:]+=np.diff(t)/2
        inertias=np.array([c['mass']]*3+[c['icc'],c['icc']+c['inn'],c['inn']])
        v=(field*np.sqrt(weights[:,None]*inertias[None,:])).ravel();return v/np.linalg.norm(v)
    def choose(p):
        result={}
        for family,number in [('B',3),('T',1),('F',1)]:
            candidates=sorted((r for r in p['classified'].values() if r['family']==family),key=lambda r:r['frequency'])
            assert len(candidates)>=number
            for rank,r in enumerate(candidates[:number],1):
                assert r['internal_zeros']==rank-1
                result[str(rank)+family]=r
        return result
    native={
        'angle':[packet(OUT/'job-0','angle',OUT/'plan.json'),packet(OUT/'job-1','angle',OUT/'plan.json')],
        'coupled':[packet(OUT/'job-2','coupled',OUT/'plan.json'),packet(BRANCH/'job-3','coupled',BRANCH/'plan.json')],
    }
    rows=[];mesh=[]
    for case,(coarse,fine) in native.items():
        old,new=choose(coarse),choose(fine)
        for label,expected in plan['cases'][case]['targets'].items():
            c,f=old[label],new[label];error=abs(f['frequency']/expected-1);change=abs(c['frequency']/f['frequency']-1)
            cv=vector(coarse,c['mode_index'],case);fv=vector(fine,f['mode_index'],case,coarse['t'])
            mac=float(abs(np.vdot(cv,fv))**2);assert mac>.99 and change<.01
            passed=error<=.05 and abs(c['frequency']/expected-1)<=.05
            rows.append(dict(case=case,label=label,expected_Hz=expected,coarse_Hz=c['frequency'],fine_Hz=f['frequency'],
                             error_percent=100*error,passed=passed,mode_index=f['mode_index']))
            mesh.append(dict(case=case,label=label,change_percent=100*change,shape_MAC=mac))
    steps=[packet(BRANCH/f'job-{i}','coupled',BRANCH/'plan.json') for i in range(3)]+[native['coupled'][0]]
    gravity=[0.,2.4525,4.905,9.81];branches=[];correlations=[]
    for g,p in zip(gravity,steps,strict=True):
        selected=choose(p)
        branches.append(dict(gravity=g,F=selected['1F'],T=selected['1T']))
    for before,after in zip(steps[:-1],steps[1:]):
        old,new=choose(before),choose(after);matrix=[]
        for a in ('1F','1T'):
            v=vector(before,old[a]['mode_index'],'coupled');line=[]
            for b in ('1F','1T'):
                w=vector(after,new[b]['mode_index'],'coupled',before['t']);line.append(float(abs(np.vdot(v,w))**2))
            matrix.append(line)
        assert all(matrix[i][i]>matrix[i][1-i] for i in range(2))
        correlations.append(matrix)
    remaining=plan['pending'];passed=sum(r['passed'] for r in rows)
    summary=dict(observed_utc=common.utc(),required=22,passed=passed,computed=8,unavailable=14,
        rows=rows,mesh=mesh,branches=branches,branch_MAC=correlations,pending_cases=remaining,pencil_audits=audit,
        sampled_branch_interpretation='At zero/quarter/half/full gravity, the lower branch remains predominantly in-plane and the upper predominantly torsional. '
           'Adjacent shape MAC selects the same families without reference frequencies. This supports a report-label discrepancy but cannot establish native eigenvector identity.',
        coupled_native_frequency_candidate=choose(native['coupled'][1])['1F'],
        primary_archive_passes_added=0,production_physics_changed=False,full_ST1_validated=False)
    common.write(OUT/'summary.json',summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for family,label,color in [('F','In-plane branch','#3569ba'),('T','Torsional branch','#c74a35')]:
        axes[0].plot(np.array(gravity)/9.81,[r[family]['frequency'] for r in branches],'o-',label=label,color=color)
        axes[1].plot(np.array(gravity)/9.81,[100*r[family]['activity_fractions']['T'] for r in branches],'o-',label=label,color=color)
    axes[0].axhline(95,color='.45',ls='--',label='Report labelled 1T: 95 Hz')
    axes[0].set_ylabel('Frequency (Hz)');axes[1].set_ylabel('Torsional share of structural shape activity (%)')
    for ax in axes:ax.set_xlabel('Gravity / 9.81');ax.grid(alpha=.2)
    axes[0].legend(fontsize=8);fig.suptitle('ST-1 coupled blade: mixed mode identities under self-weight');fig.tight_layout()
    for ext in ('png','svg'):fig.savefig(OUT/f'branches.{ext}',dpi=150)
    print(dict(passed=passed,required=22,rows=rows,mesh=mesh,branch_MAC=correlations,
               checked_pencil_equations=2*sum(a['modes'] for a in audit),maximum_pencil_error=max(a['max_pencil_action_relative_error'] for a in audit)))


if __name__=='__main__':run()
