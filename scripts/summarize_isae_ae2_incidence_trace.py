"""Audit and plot staged AE-2 branch diagnostics without running a solver."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read, write, pin
from scripts.probe_isae_ae2_incidence_stages import checked, stage_receipt
from scripts.probe_isae_ae2_incidence import request_for


def assess(out, runs):
    assert not out.exists()
    records = []; pins = [pin(Path(__file__))]
    for run in runs:
        plan = checked(run); pins.append(pin(run/'plan.json'))
        for case in plan['cases']:
            folder = run/case['name']
            record = dict(run=str(run), case=case['name'], beta=case['beta'], status='UNSTARTED', phases={})
            for phase in plan['phases']:
                stage = folder/phase
                if not stage.exists():
                    continue
                receipt = read(stage/'terminal.json')
                assert receipt['process_reaped']
                sources = read(stage/'sources-verified.json')
                assert sources['all_pins_checked_before_and_after']
                assert sources['terminal'] == pin(stage/'terminal.json') and sources['plan'] == pin(run/'plan.json')
                record['phases'][phase] = receipt
                pins += [pin(stage/f) for f in ('terminal.json', 'sources-verified.json', 'stderr.log', 'stdout.log')]
                if (stage/'progress.jsonl').exists():
                    pins.append(pin(stage/'progress.jsonl'))
            if record['phases']:
                record['status'] = 'PENDING_VERIFICATION'
            if any(r['returncode'] != 0 for r in record['phases'].values()):
                record['status'] = 'FAILED_EXECUTION'
                assert not (folder/'report.json').exists()
            elif (folder/'report.json').exists():
                for phase in plan['phases']:
                    stage_receipt(run, case['name'], phase)
                report = read(folder/'report.json'); result = read(folder/'result.json')
                assert report['status'] == 'VERIFIED_WARM_EQUILIBRIUM'
                assert report['result'] == pin(folder/'result.json') and report['request'] == pin(folder/'request.json')
                assert all(c['passed'] for c in report['checks'])
                assert len(report['checks']) == (21 if case['predecessor'] is None else 19)
                assert report['fresh_residual'] <= 1e-12 and result['converged'] and result['residual'] <= 1e-12
                expected, seed = request_for(run, plan, case)
                assert read(folder/'request.json') == expected and report['seed'] == pin(seed)
                pending = read(folder/'candidate.json'); tangent = read(folder/'tangent.json')
                assert pending['status'] == 'PENDING_VERIFICATION' and pending['accepted'] is False
                assert all(pin(p['path']) == p for p in pending['pins'])
                assert tangent['candidate'] == pin(folder/'candidate.json') and tangent['matrix'] == pin(folder/'tangent.npz')
                assert tangent['status'] == 'COMPLETE_ORIGINAL_FINAL_TANGENT' and tangent['shape'] == [2105, 2105]
                assert result['diagnostic_stages']['pending'] == pin(folder/'candidate.json')
                assert result['diagnostic_stages']['final_tangent'] == pin(folder/'tangent.json')
                record.update(status='VERIFIED_DIAGNOSTIC', values=report['values'],
                    physical_checks=len(report['checks']), residual=report['fresh_residual'],
                    newton=pending['newton'], rank=result['equilibrium_initialization'], control=report['control'])
                pins += [pin(folder/f) for f in ('report.json', 'result.json', 'candidate.json', 'tangent.json')]
            records.append(record)
    p1 = ROOT/'artifacts/isae/ae2-beta1-recovery-staged-0048-20261110/plan.json'
    p5 = ROOT/'artifacts/isae/ae2-branch-fixed-current-20261110/plan.json'
    r5 = p5.with_name('report.json'); jid = 'AE-2-m15_02-b05-ias017-m160'
    j1 = next(c['job'] for c in read(p1)['cases'] if c['id'] == 'AE-2-m15_02-b01-ias017-m160')
    j5 = next(j for j in read(p5)['jobs'] if j['id'] == jid)
    cold = next(j['result'] for j in read(r5)['jobs'] if j['id'] == jid)
    assert cold['status'] == 'computed' and cold['numerical_pass']
    for job in (j1, j5):
        for p in job['source_pins']+job['kernel_pins']:
            current = pin(p['path'])
            assert current['path'] == p['path'] and current['sha256'] == p['sha256']
            assert Path(p['path']).stat().st_size == p['bytes']
    native = [j['reference_row'] for j in (j1, j5)]
    cold_values = {c['name']: c['predicted'] for c in cold['reference_checks']}
    pins += [pin(p) for p in (p1, p5, r5)]
    verified = [r for r in records if r['status'] == 'VERIFIED_DIAGNOSTIC']
    phases = [phase for r in records for phase in r['phases'].values()]
    summary = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='AUDITED_DIAGNOSTIC', records=records, native=native, cold_beta5_values=cold_values,
        accepted_states=len(verified), physical_checks=sum(r['physical_checks'] for r in verified),
        maximum_full_residual=max(r['residual'] for r in verified),
        supervised_processes=len(phases), failed_processes=sum(r['returncode'] != 0 for r in phases),
        all_processes_reaped=True, reached_beta=max(r['beta'] for r in verified),
        reached_beta5=any(r['beta'] == 5 for r in verified), primary_votes_added=0,
        primary_passed=708, primary_required=2200, pins=pins,
        qualifications=['Diagnostic continuation is not an independent native comparison scope.',
            'Intermediate incidences have no archived reference here; no values are invented or interpolated.',
            'Original cold-start comparisons and failed diagnostics remain intact.',
            'Following a branch does not prove uniqueness, stability, or original ASWING iteration history.'])
    write(out/'assessment.json', summary)
    print({k:summary[k] for k in ('accepted_states','physical_checks','reached_beta','supervised_processes','failed_processes','primary_votes_added')}, flush=True)


def plot(out):
    assessment = read(out/'assessment.json')
    assert all(pin(p['path']) == p for p in assessment['pins'])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows = sorted((r for r in assessment['records'] if r['status'] == 'VERIFIED_DIAGNOSTIC'), key=lambda r:r['beta'])
    labels = [('RY_m','Sensor Earth Y (m)'), ('Psi_deg','Heading (degrees)'),
        ('sensor_V_m_s','Sensor speed (m/s)'), ('sensor_beta_deg','Sensor flow angle (degrees)')]
    fig, axes = plt.subplots(2,2,figsize=(10,6.5), constrained_layout=True)
    for ax,(key,label) in zip(axes.flat, labels):
        ax.plot([r['beta'] for r in rows], [r['values'][key] for r in rows], 'o-',
            color='#0072b2', markerfacecolor='white', label='Verified incidence continuation')
        ax.scatter([r['beta_deg'] for r in assessment['native']], [r['values'][key] for r in assessment['native']],
            marker='D', color='black', s=42, label='Archived ASWING (1° and 5° only)', zorder=4)
        ax.scatter([5], [assessment['cold_beta5_values'][key]], color='#d55e00', marker='x',
            s=65, label='Original OpenSwing cold start at 5°', zorder=4)
        ax.set(xlabel='Commanded beta (degrees)', ylabel=label, xlim=(.75,5.25))
        ax.grid(alpha=.25)
    axes[0,0].legend(fontsize=7)
    fig.suptitle('AE-2 negative coupling · IAS 17 m/s · nominal 160\nDiagnostic branch trace; primary score unchanged')
    fig.savefig(out/'incidence.png',dpi=150);fig.savefig(out/'incidence.svg');plt.close(fig)
    write(out/'plot.json',dict(assessment=pin(out/'assessment.json'),png=pin(out/'incidence.png'),svg=pin(out/'incidence.svg')))
    print('Saved incidence.png and incidence.svg',flush=True)


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2)
    signal.alarm(45)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['assess','plot'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--run',type=Path,action='append',default=[])
    a=p.parse_args()
    if a.action=='assess':assess(a.output.resolve(),[v.resolve() for v in a.run])
    else:plot(a.output.resolve())
