"""Authenticate and compare the complete prospective ST-4 mechanics scope."""
import argparse
from decimal import Decimal
import numpy as np
import verify_sa14_defaults as common
import isae_st4_mechanics as source


def assurance(coarse,fine):
    grid=np.linspace(0,1.2192,257);vectors=[]
    for packet in (coarse,fine):
        shapes=[]
        for shape in packet['shapes']:
            sampled=np.column_stack([np.interp(grid,packet['stations'],shape[:,k].real)+1j*np.interp(grid,packet['stations'],shape[:,k].imag) for k in range(6)])
            weights=np.ones(len(grid));weights[[0,-1]]=.5
            shapes.append((sampled*np.sqrt(weights[:,None])).ravel())
        vectors.append(np.asarray(shapes))
    a,b=vectors
    return abs(a.conjugate()@b.T)**2/(np.sum(abs(a)**2,axis=1)[:,None]*np.sum(abs(b)**2,axis=1)[None,:])


def summarize(out):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);reports={};receipts=[]
    for i,job in enumerate(plan['jobs']):
        folder=out/f'job-{i:02d}';r=common.read(folder/'report.json');e=common.read(out/f'execution-{i:02d}.json')
        assert r['job']==job and r['plan_sha256']==common.sha(out/'plan.json') and e['index']==i and e['returncode']==0
        for p,h in r['artifacts'].items():assert common.sha(folder/p)==h
        assert max(r['checks'].values())<1e-7 and r['independent_transfer_relative']<1e-7
        assert all(a[s]<plan['pencil_gate'] for a in r['pencil_audits'] for s in ('left','right'))
        with np.load(folder/'shapes.npz') as z:shape={k:z[k] for k in z.files}
        reports.setdefault(job['model'],{})[job['panels']]=(r,shape);receipts.append(e)
    models={}
    for name,grids in reports.items():
        coarse,cs=grids[64];fine,fs=grids[128];mac=assurance(cs,fs);labels={}
        for label in source.LABELS:
            i=coarse['classification']['indices'][label];j=fine['classification']['indices'][label]
            a,b=coarse['frequencies_Hz'][i],fine['frequencies_Hz'][j]
            change=abs(a/b-1);shape_mac=float(mac[i,j]);identified=coarse['classification']['valid'] and fine['classification']['valid']
            matched=int(np.argmax(mac[i]))==j and int(np.argmax(mac[:,j]))==i
            labels[label]=dict(coarse_Hz=a,fine_Hz=b,mesh_change_percent=100*change,shape_MAC=shape_mac,
                classification_valid=identified,mutual_shape_match=matched,
                mesh_pass=bool(change<=plan['mesh_relative'] and shape_mac>=plan['shape_MAC'] and matched and identified),
                coarse_torsion_fraction=coarse['classification']['torsion_fractions'][i],fine_torsion_fraction=fine['classification']['torsion_fractions'][j])
        models[name]=dict(labels=labels,shape_MAC_matrix=mac.tolist(),literal_model=plan['models'][name]['path'])
    def compare(model,label,expected,absolute):
        row=dict(model=model,label=label,expected=expected,predicted=None,passed=False,available=expected is not None and model in models)
        if model in models:
            observed=models[model]['labels'][label];row.update(observed,predicted=observed['fine_Hz'])
            if expected is not None:
                gate=max(absolute,plan['reference_relative']*abs(expected));errors=[abs(observed[k]-expected) for k in ('coarse_Hz','fine_Hz')]
                row.update(errors=errors,gate=gate,error_percent=100*errors[1]/abs(expected) if expected else None,
                    passed=bool(max(errors)<=gate and observed['mesh_pass']))
        return row
    paper=[]
    for target in plan['paper']:
        paper.append(dict(**target,comparison=compare(target['model'],target['label'],target['expected'],target['original_absolute_tolerance'])))
    aggregates={}
    for filename,targets in plan['aggregate_targets'].items():
        rows=[]
        for target in targets:
            label=target['name'].split(':')[1].removesuffix('_Asw')
            if label not in source.LABELS:continue
            name='WING' if target['weight_label']=='0' else target['weight_label'].lower()+'_b'+str(int(Decimal(target['position_token'])))
            row=dict(**target,comparison=compare(name,label,target['expected'],target['tolerance']))
            if name not in models:row['unavailable_reason']='No original model at this exact named span position; no neighboring input substituted.'
            elif target['expected'] is None:row['unavailable_reason']='Source cell is empty or NC.'
            rows.append(row)
        aggregates[filename]=dict(required=len(rows),available=sum(r['comparison']['available'] for r in rows),passed=sum(r['comparison']['passed'] for r in rows),rows=rows)
    direct=[]
    for name,targets in plan['direct_exports'].items():
        coarse,_=reports[name][64];fine,_=reports[name][128]
        for i,target in enumerate(targets):
            a=coarse['positive_frequencies_Hz'][i]*2*np.pi;b=fine['positive_frequencies_Hz'][i]*2*np.pi;expected=target['eigenvalue'][1]
            change=abs(a/b-1);gate=max(target['half_printed_units'][1],.05*expected)
            direct.append(dict(model=name,ordinal=i+1,expected_rad_s=expected,predicted_rad_s=b,error_percent=100*abs(b/expected-1),
                mesh_change_percent=100*change,passed=bool(max(abs(a-expected),abs(b-expected))<=gate and change<=plan['mesh_relative'])))
    all_reports=[r for grids in reports.values() for r,_ in grids.values()];audits=[a for r in all_reports for a in r['pencil_audits']]
    result=dict(observed_utc=common.utc(),required=72,passed=sum(r['comparison']['passed'] for r in paper),paper=paper,
        models=models,aggregate_diagnostics=aggregates,direct_diagnostics=dict(required=len(direct),passed=sum(r['passed'] for r in direct),rows=direct),
        physical_states=len(all_reports),matrix_checks=2*len(audits),maximum_pencil_residual=max(a[s] for a in audits for s in ('left','right')),
        maximum_mass_pairing_error=max(a['mass_pairing'] for a in audits),maximum_neutral_relative=max(a['neutral_relative'] for a in audits),
        maximum_independent_discrete_relative=max(r['independent_transfer_relative'] for r in all_reports),
        maximum_physical_residual=max(max(r['checks'].values()) for r in all_reports),
        solver_seconds=sum(r['solver_seconds'] for r in all_reports),supervised_seconds=sum(r['seconds'] for r in receipts),peak_rss_kib=max(r['peak_rss_kib'] for r in all_reports),
        plan_sha256=common.sha(out/'plan.json'),production_changed=False,full_family_validated=False,
        qualification='All72 published paper cells retained under declared mappings and vacuum/unloaded setup. '
        'Conflicting paper/workbook/CSV and native-export scopes stay separate. No complete-spectrum or native eigenvector-identity claim.')
    common.authenticate(plan['pins']);common.write(out/'summary.json',result)
    print({k:v for k,v in result.items() if k not in ('paper','models','aggregate_diagnostics','direct_diagnostics')})
    print('Failed paper cells:',[(r['model'],r['label'],r['expected'],r['comparison']['predicted'],r['comparison'].get('error_percent'),r['comparison'].get('mesh_pass')) for r in paper if not r['comparison']['passed']])
    print('Separate summaries:',{k:{f:v[f] for f in ('required','available','passed')} for k,v in aggregates.items()})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=common.Path);a=p.parse_args();common.bounded();summarize(a.output)
