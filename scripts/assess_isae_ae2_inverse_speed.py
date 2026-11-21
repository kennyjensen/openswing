"""Saved-data audit and diagnostic plot for AE-2 inverse-speed probes."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.probe_isae_ae2_inverse_speed import checked, pin, read, write


def assess(stage):
    plan = checked(stage);rows = [];outcomes = [];checks = 0;pins = []
    archive_pin, = [p for p in plan['pins'] if Path(p['path']).name == '[m15_02]_S_A5.txt']
    archive = Path(archive_pin['path']).read_text().splitlines()
    for case in plan['cases']:
        folder = stage/'cases'/case['name']
        target = case['native_row']
        assert archive[target['output_file_line_1based']-1] == target['raw_line']
        assert target['raw_line'].split() == target['raw_tokens']
        assert dict(zip(('RY_m','Psi_deg','sensor_V_m_s','sensor_beta_deg'),
            map(float, target['raw_tokens'][2:]))) == target['values']
        if not (folder/'terminal.json').exists():
            assert not folder.exists(), 'An unaccounted attempt is present.'
            outcomes.append(dict(name=case['name'], status='unrun', predecessor=case['predecessor']))
            continue
        terminal = read(folder/'terminal.json')
        assert terminal['reaped'] is True
        pins += [pin(p) for p in sorted(folder.iterdir()) if p.is_file()]
        if terminal['returncode'] != 0:
            outcomes.append(dict(name=case['name'], status='failed', terminal=terminal))
            continue
        request, result, fresh, report = [read(folder/name) for name in
            ('request.json','result.json','restored-result.json','report.json')]
        assert {k:v for k,v in request.items() if k != 'initial_state'} == case['request']
        assert report['result'] == pin(folder/'result.json') and report['request'] == pin(folder/'request.json')
        assert report['status'] == 'computed' and all(c['passed'] for c in report['checks'])
        if case['predecessor']:
            previous = stage/'cases'/case['predecessor']
            assert request['initial_state'] == read(previous/'result.json')['equilibrium_state']
            assert report['predecessor'] == pin(previous/'report.json')
        else:
            assert 'initial_state' not in request
        assert result['numerics'] == request['numerics']
        assert 0 <= result['residual'] <= 1e-8 and 0 <= fresh['residual'] <= 1e-8
        assert result['residual'] == fresh['residual']
        sensor = result['sensors'][0];other = fresh['sensors'][0]
        values = dict(IAS=result['operating_values']['speed'], RY_m=sensor['position_earth'][1],
            Psi_deg=sensor['heading'], sensor_V_m_s=sensor['speed'], sensor_beta_deg=sensor['beta'])
        assert values == report['values'] and all(math.isfinite(v) for v in values.values())
        assert math.dist(sensor['position_earth'], other['position_earth']) <= 1e-10
        assert abs(sensor['heading']-other['heading']) <= 1e-8
        flow = sensor['air_velocity_sensor'];speed = math.sqrt(sum(v*v for v in flow))
        assert abs(speed-sensor['speed']) <= 1e-12
        assert abs(math.degrees(math.asin(-flow[1]/speed))-sensor['beta']) <= 1e-10
        for kind in ('force','moment'):
            applied, support = result['applied_'+kind], result['support_'+kind]
            norm = lambda v: math.sqrt(sum(x*x for x in v))
            assert norm([a+b for a,b in zip(applied,support)]) <= 1e-7*(norm(applied)+norm(support))
        state = result['equilibrium_state']
        assert max(map(abs, state['positions'][0]+state['rotations'][0])) <= 1e-10
        custom = bool(request['operating_constraints'])
        if custom:
            assert abs(values['RY_m']-target['values']['RY_m']) <= 1e-8
            assert result['custom_trim']['column_scaled_reciprocal_condition'] > 1e-10
            assert result['custom_trim']['one_sided_tangent_ratio'] <= 1
        else:
            assert values['IAS'] == 20
        checks += len(report['checks'])
        rows.append(dict(name=case['name'], mesh=request['panels']['default'], inverse=custom,
            native_speed=case['native_speed'], native_values=target['values'], values=values,
            speed_difference=values['IAS']-case['native_speed'],
            speed_error_percent=100*(values['IAS']-case['native_speed'])/case['native_speed'],
            heading_error_percent=100*(values['Psi_deg']-target['values']['Psi_deg'])/abs(target['values']['Psi_deg']),
            residual=fresh['residual'], solve_seconds=report['solve_seconds'],
            custom_tangent=result.get('custom_trim'), physical_checks=len(report['checks'])))
        outcomes.append(dict(name=case['name'], status='computed'))
    assert not any(n == 'openswing' or n.startswith('openswing.') for n in sys.modules)
    checked(stage)
    destination = stage/'assessment.json';assert not destination.exists()
    report = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='SAVED_DIAGNOSTIC_AUDIT_PASS_WITH_INCOMPLETE_FINE_MESH', plan=pin(stage/'plan.json'),
        assessor=pin(__file__), rows=rows, outcomes=outcomes, raw_files=pins,
        physical_checks_passed=checks, primary_votes_added=0, physical_calls=0,
        production_imports=0, fine_inverse_comparison_complete=False,
        limitations=plan['limitations'])
    write(destination, report)
    print(json.dumps(dict(physical_checks_passed=checks, outcomes=outcomes,
        rows=[{k:r[k] for k in ('name','speed_difference','speed_error_percent','heading_error_percent')} for r in rows]), indent=2))


def plot(stage):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    report = read(stage/'assessment.json');rows = report['rows']
    native = {r['native_speed']:r['native_values']['RY_m'] for r in rows}
    fig, ax = plt.subplots(figsize=(8,4.8), layout='constrained')
    ax.scatter(list(native), list(native.values()), marker='x', s=70, c='black', label='Archived ASWING values', zorder=4)
    coarse = sorted((r for r in rows if r['mesh'] == 20), key=lambda r:r['values']['IAS'])
    ax.plot([r['values']['IAS'] for r in coarse], [r['values']['RY_m'] for r in coarse],
        'o-', color='#0072B2', label='Current positive branch: nominal 20 diagnostic')
    fine = [r for r in rows if r['mesh'] == 40]
    ax.scatter([r['values']['IAS'] for r in fine], [r['values']['RY_m'] for r in fine],
        marker='s', color='#D55E00', label='Nominal 40: cold 20 m/s only')
    selected, = [r for r in coarse if r['native_speed'] == 17]
    y = selected['values']['RY_m']
    ax.annotate('', xy=(selected['values']['IAS'],y), xytext=(17,y),
        arrowprops=dict(arrowstyle='<->', color='#666666'))
    ax.text(17.5,y-.005, f"Same tip Y requires {selected['values']['IAS']:.3f} m/s", fontsize=10)
    ax.set(xlabel='Airspeed (m/s)', ylabel='Tip sensor Earth Y (m)',
        title='AE-2 negative coupling, beta 5°: inverse-speed diagnostic', xlim=(16.65,20.4))
    ax.grid(alpha=.25);ax.legend(fontsize=8, loc='upper right')
    fig.text(.5,.01,'Prescribed native tip Y; solved airspeed. No native passes added; fine inverse mesh remains incomplete.',
        ha='center',fontsize=8)
    fig.savefig(stage/'inverse-speed.png',dpi=160,bbox_inches='tight')
    fig.savefig(stage/'inverse-speed.svg',bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('assess','plot'));p.add_argument('--stage',type=Path,required=True)
    a = p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(30)
    {'assess':assess,'plot':plot}[a.action](a.stage.resolve())
