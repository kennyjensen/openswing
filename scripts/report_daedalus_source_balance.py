"""Saved-data audit and plot of current aircraft force/moment balance."""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT,SOURCE,read,pin
from check_daedalus_source_balance import STUDY,compare
from daedalus_bounded_job import run


def report(folder,args):
    import ast
    import csv
    import re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    jobs=sorted(p for p in STUDY.iterdir() if (p/'terminal.json').exists())
    archive={pin(p/'runner.py'):p/'runner.py' for p in jobs}
    for p in STUDY.glob('*/rejected-reference.py'):archive[pin(p)]=p
    hash_checks=0;archived_matches=0;terminals=[]
    for p in jobs:
        terminal=read(p/'terminal.json');terminals.append(terminal)
        assert terminal['returncode']==(1 if p.name=='analyze-dip' else 0)
        assert terminal['process_reaped'] and terminal['inputs_unchanged'] and not terminal['timed_out']
        for path,digest in read(p/'plan.json')['inputs_sha256'].items():
            if pin(path)!=digest:
                assert Path(path).name in ('check_daedalus_source_balance.py','daedalus_source_balance_reference.py') and digest in archive,(path,digest)
                archived_matches+=1
            hash_checks+=1
    verified_sources=[]
    for entry in read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        if entry['id'] in ('drela-steady','drela-unsteady'):
            assert pin(ROOT/entry['local_pdf'])==entry['sha256']
            assert pin(ROOT/entry['local_text'])==entry['text_sha256']
            verified_sources.append(entry['id'])
    assert len(verified_sources)==2
    for name in ('daedalus_source_balance_reference.py','wing_inertia_reference.py'):
        tree=ast.parse((ROOT/'scripts'/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):assert all(not value.name.startswith('openswing') for value in node.names)
            if isinstance(node,ast.ImportFrom):assert not (node.module or '').startswith('openswing')
    for name in ('check_daedalus_source_balance.py',Path(__file__).name):ast.parse((ROOT/'scripts'/name).read_text())
    rows=[];comparisons={};cases={};plotdata={}
    for case,tag in [('slow','analyze-slow'),('dip','analyze-dip-v2')]:
        source=STUDY/tag;result=read(source/'result.json');data=np.load(source/'arrays.npz')
        native=np.load(STUDY/('capture-'+case)/'arrays.npz');base=np.load(STUDY/('capture-'+case)/'base-targets.npz')
        selected=data['selected_rows'];assert len(selected)==1426 and np.array_equal(selected,np.arange(618,2044))
        errors={}
        for width in ('wide','fine'):
            for value in ('force','moment'):errors[width+'_external_'+value]=compare(data['external_'+value],native[width+'_'+value])
            errors[width+'_selected_rows']=compare(data['expected_residual'][selected],native[width+'_residual'][selected],2e-8,2e-8)
        errors['matrix_action']=compare(data['expected_residual'][selected],native['matrix_action'][selected],2e-8,2e-8)
        errors['base_rows']=compare(data['expected_base_residual'][selected],base['residual'][selected],2e-8,2e-8)
        for value in ('force','moment'):errors['base_external_'+value]=compare(data['base_external_'+value],base[value])
        global_balance=data['aerodynamic_wrench']+data['real_inertia_wrench']
        errors['aero_sum']=compare(data['aero_group_wrenches'].sum(axis=0),data['aerodynamic_wrench'],2e-10,2e-10)
        errors['inertia_sum']=compare(data['mass_equation_wrenches'].sum(axis=(0,1)),data['real_inertia_wrench'],2e-10,2e-10)
        beam_total=data['aero_group_wrenches'].copy()
        beam_total[:5]+=data['mass_equation_wrenches'][:5].sum(axis=1)
        beam_total[5]+=data['mass_equation_wrenches'][5].sum(axis=0)
        errors['beam_group_sum']=compare(beam_total.sum(axis=0),global_balance,2e-10,2e-10)
        for scope,labels,values in [('aerodynamics',result['aero_groups'],data['aero_group_wrenches']),
                                  ('real_mass_gravity',result['mass_groups'],data['mass_equation_wrenches'].sum(axis=1)),
                                  ('local_mechanics',result['mechanical_groups'],data['mechanical_wrenches'])]:
            for label,value in zip(labels,values):
                for j,axis in enumerate(('Fx','Fy','Fz','Mx','My','Mz')):
                    rows.append([result['frequency_hz'],scope,label,axis,value[j].real,value[j].imag,'lb/F3' if j<3 else 'lb ft/F3'])
        comparisons[case]=errors
        cases[case]=dict(frequency_hz=result['frequency_hz'],max_harmonic_residual=float(max(abs(data['expected_residual'][selected]))),
            max_global_force_residual=float(max(abs(global_balance[:3]))),max_global_moment_residual=float(max(abs(global_balance[3:]))),
            yaw_moment_residual=float(abs(global_balance[5])),beam_labels=result['aero_groups'],
            total_yaw_moment_real=beam_total[:,5].real.tolist(),total_yaw_moment_imag=beam_total[:,5].imag.tolist())
        plotdata[case+'_yaw_by_group']=beam_total[:,5]
    with (folder/'wrenches.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['frequency_hz','scope','component','axis','real','imaginary','units']);writer.writerows(rows)
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    plt.rcParams.update({'figure.facecolor':'#111827','axes.facecolor':'#111827','text.color':'white',
        'axes.labelcolor':'white','xtick.color':'white','ytick.color':'white','axes.edgecolor':'#9ca3af','font.size':9})
    fig,axes=plt.subplots(1,2,figsize=(12,5.5),layout='constrained')
    labels=['Wing','Horizontal tail','Vertical tail','Tail boom','Fairing','Point objects','Engine']
    for ax,case in zip(axes,('slow','dip')):
        values=plotdata[case+'_yaw_by_group'];y=np.arange(len(labels));data=cases[case]
        ax.barh(y-.18,values.real,.36,color=palette[0],label='Real')
        ax.barh(y+.18,values.imag,.36,color=palette[1],label='Imaginary')
        ax.set_yticks(y,labels);ax.invert_yaxis();ax.axvline(0,color='white',alpha=.5,lw=.7)
        ax.set_xlabel('External yaw moment, including inertial reaction [lb ft/F3]')
        ax.set_title(f"{data['frequency_hz']:.6g} Hz; sum magnitude {data['yaw_moment_residual']:.2g}")
        ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True);ax.legend(facecolor='#111827',labelcolor='white')
    fig.suptitle('Independent current-aircraft yaw-moment balance\nSupplied harmonic response; aerodynamic, inertia and gravity terms combined by component')
    fig.savefig(folder/'yaw-balance.png',dpi=150);fig.savefig(folder/'yaw-balance.svg');plt.close(fig)
    np.savez_compressed(folder/'plot-data.npz',**plotdata)
    return dict(cases=cases,recomputed_comparisons=comparisons,checked_rows_per_frequency=1426,excluded_compatibility_rows=618,
        source_jobs=len(jobs),source_successes=sum(t['returncode']==0 for t in terminals),source_rejected=1,
        input_hashes_checked=hash_checks,archived_source_matches=archived_matches,primary_sources=verified_sources,
        max_source_cpu_seconds=max(t['cpu_seconds'] for t in terminals),max_source_wall_seconds=max(t['wall_seconds'] for t in terminals),
        max_source_rss_MiB=max(t['peak_rss_kib'] for t in terminals)/1024,isae_status_sha256=pin(ROOT/'docs/validation/ISAE_STATUS.md'),
        qualification='Independent balance along two supplied complex response states. Beam constitutive/compatibility rows are explicitly excluded. No production correction, native-reference pass or changed Bode prediction follows.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_daedalus_source_balance.py',ROOT/'scripts/daedalus_source_balance_reference.py',
        ROOT/'scripts/wing_inertia_reference.py',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'web/plot-colors.js',ROOT/'docs/validation/ISAE_STATUS.md']
    for p in STUDY.iterdir():
        if (p/'terminal.json').exists():inputs += [f for f in p.iterdir() if f.is_file()]
    run(STUDY,args['tag'],inputs,report,args,__file__)


if __name__=='__main__':main()
