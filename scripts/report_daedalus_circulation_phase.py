"""Recompute current-source aerodynamic comparison gates from saved evidence."""
import argparse
import ast
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT, SOURCE, read, pin, write
from check_daedalus_circulation_phase import STUDY, REFERENCE, restore, metrics
from daedalus_bounded_job import run


def report(folder, args):
    import csv
    import re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    jobs = sorted(p for p in STUDY.iterdir() if (p/'terminal.json').exists())
    prior_runners = {pin(p/'runner.py'):p/'runner.py' for p in jobs}
    checks = []; pin_count = 0; archived_runner_matches = 0
    terminals = []
    for path in jobs:
        terminal = read(path/'terminal.json'); terminals.append(terminal)
        assert terminal['process_reaped'] and terminal['inputs_unchanged'] and not terminal['timed_out'],path
        assert terminal['cpu_seconds'] < 15 and terminal['peak_rss_kib'] < 512*1024
        assert terminal['returncode'] == (1 if path.name == 'reference-base-q32' else 0),path
        for file, digest in read(path/'plan.json')['inputs_sha256'].items():
            if pin(file) != digest:
                assert Path(file).name == 'check_daedalus_circulation_phase.py' and digest in prior_runners,(file,digest)
                archived_runner_matches += 1
            pin_count += 1
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for entry in catalog['files']:
        if entry['id'] in ('drela-steady','drela-unsteady') or 'Technical Description' in entry['title']:
            assert pin(ROOT/entry['local_pdf']) == entry['sha256']
            assert pin(ROOT/entry['local_text']) == entry['text_sha256']
            checks.append(entry['id'])
    assert len(checks) == 2,checks
    # The independent source equations and their transitive helpers import no
    # OpenSwing modules. Input capture and report plumbing remain distinct.
    for name in REFERENCE:
        tree=ast.parse((ROOT/'scripts'/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):assert all(not a.name.startswith('openswing') for a in node.names)
            if isinstance(node,ast.ImportFrom):assert not (node.module or '').startswith('openswing')
    for name in ('check_daedalus_circulation_phase.py','check_daedalus_circulation_mass.py',Path(__file__).name):
        ast.parse((ROOT/'scripts'/name).read_text())
    base_target=dict(np.load(STUDY/'capture-base/base-targets.npz'))
    comparison_rows=[]; directional_max={}; base_max={}; width_max={}; complex_max={}; quad_max={}
    arrays_compared=0; scalars_compared=0
    def compare(actual,expected,kind,label):
        nonlocal arrays_compared,scalars_compared
        values=metrics(actual,expected)
        arrays_compared+=len(values);scalars_compared+=sum(v['count'] for v in values.values())
        for key,value in values.items():comparison_rows.append([kind,label,key,value['count'],value['max_absolute'],value['max_gate_ratio']])
        return values
    def maxima(destination,values):
        for key,value in values.items():destination[key]=max(destination.get(key,0.),value['max_absolute'])
    for q in (16,32):
        actual=dict(np.load(STUDY/f'source-base-q{q}/arrays.npz'))
        maxima(base_max,compare(actual,base_target,'base',str(q)))
    for case in ('slow','dip'):
        native=restore(STUDY/f'capture-{case}/directions.pkl')
        for part,name in enumerate(('real','imag')):
            maxima(width_max,compare(native[0]['targets'][part],native[1]['targets'][part],'native-width',case+'-'+name))
            for q in (16,32):
                path=STUDY/f'source-{case}-{name}-q{q}'
                expected=dict(np.load(path/'arrays.npz'))
                for width in native:
                    maxima(directional_max,compare(width['targets'][part],expected,'direction',f'{case}-{name}-q{q}-h{width["step"]}'))
                # Both complex widths were compared independently by the job;
                # the final array is stored and the earlier differences logged.
                maxima(complex_max,read(path/'result.json')['complex_step_comparisons'])
            first=dict(np.load(STUDY/f'source-{case}-{name}-q16/arrays.npz'))
            last=dict(np.load(STUDY/f'source-{case}-{name}-q32/arrays.npz'))
            maxima(quad_max,compare(first,last,'quadrature',case+'-'+name))
    maxima(quad_max,compare(dict(np.load(STUDY/'source-base-q16/arrays.npz')),
                            dict(np.load(STUDY/'source-base-q32/arrays.npz')),'quadrature','base'))
    mass=np.load(STUDY/'mass-columns/arrays.npz')
    difference=abs(mass['actual_mass']-mass['expected_mass'])
    assert np.all(difference <= 2e-8+2e-8*abs(mass['expected_mass']))
    mass_report=read(STUDY/'mass-columns/result.json')
    assert difference.max() == mass_report['max_absolute_error']
    with (folder/'comparisons.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['kind','case','quantity','scalar_count','max_absolute_error','max_gate_ratio']);writer.writerows(comparison_rows)
    # Phase-sensitive lift comparison uses fresh current-state targets, not
    # old expected arrays or the fitted reference Bode drawing.
    packet=restore(STUDY/'capture-base/base.pkl');wing=packet['fixture']['beams'][0]
    count=len(wing['element_ids']);stations=wing['original_mesh']['tm']
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    plt.rcParams.update({'figure.facecolor':'#111827','axes.facecolor':'#111827','text.color':'white',
        'axes.labelcolor':'white','xtick.color':'white','ytick.color':'white','axes.edgecolor':'#9ca3af','font.size':9})
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    plot_arrays={'wing_stations':stations};wing_rate={}
    for row,case in enumerate(('slow','dip')):
        native=restore(STUDY/f'capture-{case}/directions.pkl')[-1]
        complex_force=[]
        for part,name in enumerate(('real','imag')):
            ref=dict(np.load(STUDY/f'source-{case}-{name}-q32/arrays.npz'))
            actual=native['targets'][part]['lifting_rate_force'][:count,2]
            expected=ref['lifting_rate_force'][:count,2];complex_force.append(ref['lifting_rate_force'][:count])
            plot_arrays[f'{case}_{name}_native']=actual;plot_arrays[f'{case}_{name}_reference']=expected
            ax=axes[row,part];ax.plot(stations,expected,color=palette[0],label='Independent equations',lw=1.5)
            ax.plot(stations,actual,'o',ms=3,mfc='none',color=palette[1],label='Current OpenSwing')
            frequency=read(STUDY/f'capture-{case}/result.json')['frequency_hz']
            ax.set_title(f'{frequency:.6g} Hz — {name} component');ax.set_xlabel('Wing material coordinate [ft]')
            ax.set_ylabel('Strip vertical rate lift [lb/F3]');ax.grid(alpha=.16);ax.legend(facecolor='#111827',labelcolor='white')
        force=complex_force[0]+1j*complex_force[1]
        wing_rate[case]=dict(force_real=force.sum(axis=0).real.tolist(),force_imag=force.sum(axis=0).imag.tolist())
    fig.suptitle('Current Daedalus circulation-rate lift\nSupplied coupled motion; independently evaluated flow and aerodynamic loads')
    fig.savefig(folder/'rate-lift.png',dpi=150);fig.savefig(folder/'rate-lift.svg');plt.close(fig)
    np.savez_compressed(folder/'plot-data.npz',**plot_arrays)
    return dict(array_comparisons=arrays_compared,scalar_comparisons=scalars_compared,
        directional_max_absolute_errors=directional_max,base_max_absolute_errors=base_max,
        native_width_max_absolute_errors=width_max,complex_step_max_absolute_errors=complex_max,
        quadrature_max_absolute_errors=quad_max,circulation_mass=mass_report,wing_rate_lift=wing_rate,
        jobs=len(jobs),successes=sum(t['returncode']==0 for t in terminals),rejected=1,
        max_cpu_seconds=max(t['cpu_seconds'] for t in terminals),max_wall_seconds=max(t['wall_seconds'] for t in terminals),
        max_rss_MiB=max(t['peak_rss_kib'] for t in terminals)/1024,
        inputs_hashes_checked=pin_count,archived_driver_matches=archived_runner_matches,primary_sources=checks,
        isae_status_sha256=pin(ROOT/'docs/validation/ISAE_STATUS.md'),
        qualification='Current source/SEGSPL steady and harmonic aerodynamic checks with independent equations; parsed properties, physical motion chart and supplied aircraft response remain inputs. This is not a native-ASWING Bode match or independent prediction of the aircraft motion. No completion fraction changed.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_daedalus_circulation_phase.py',ROOT/'scripts/check_daedalus_circulation_mass.py',
        ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'web/plot-colors.js',ROOT/'docs/validation/ISAE_STATUS.md']
    inputs += [ROOT/'scripts'/name for name in REFERENCE]
    for path in STUDY.iterdir():
        if (path/'terminal.json').exists():inputs += [p for p in path.iterdir() if p.is_file()]
    run(STUDY,args['tag'],inputs,report,args,__file__)


if __name__=='__main__':main()
