"""Plot recorded reconstruction evidence without implying experimental validation."""
from pathlib import Path
import hashlib
import json
import runpy
import argparse
import zipfile

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--archive', type=Path, default=ROOT/'docs/validation/durrant-flutter-records.zip')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
OUT = args.output
OUT.mkdir(exist_ok=False, parents=True)
helper_path = ROOT/'scripts/analyze-durrant-flutter.py'
helper = runpy.run_path(str(helper_path))
cases, manifests = [], []
with zipfile.ZipFile(args.archive) as archive:
    index = json.loads(archive.read('index.json'))
    def original(path):
        info = index['files'][str(path)]
        raw = archive.read(info['member'])
        assert hashlib.sha256(raw).hexdigest() == info['sha256']
        return raw
    for run in index['runs']:
        name = run['name']
        path = Path(run['manifest'])
        raw = original(path)
        data = json.loads(raw)
        manifests.append(dict(directory=str(path.parent), manifest_sha256=hashlib.sha256(raw).hexdigest(), observed_manifest=data))
        for entry in data['cases']:
            raw = original(path.parent/entry['file'])
            assert hashlib.sha256(raw).hexdigest() == entry['sha256']
            case = json.loads(raw)
            if case['status'] != 'computed':
                continue
            spec = helper['model_spec'](case)
            if (spec['panels'] == 8 and spec['step'] == 1e-5 and spec['stall']
                    and not spec['freeze_influences'] and spec['time_unit_s'] == 1.
                    and spec['nea'] == .001 and spec['variant'] == 'tables'):
                case['id'] = name+'/'+entry['file']
                cases.append(case)

plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'svg.fonttype': 'none'})
fig, axes = plt.subplots(2, 2, figsize=(12, 8.4), layout='constrained')
colors = {'25': '#007c83', '75': '#994f92'}
trace_records = []
for wing in ['25', '75']:
    group = sorted({c['spec']['speed_m_s']: c for c in cases if c['spec']['wing'] == wing}.values(), key=lambda c: c['spec']['speed_m_s'])
    path = [c for c in group if c['spec']['speed_m_s'] >= 20]
    first = path[0]
    target = complex(0, 170 if wing == '25' else 120)
    selected = min(helper['modes'](first), key=lambda m: abs(helper['root'](m)-target))
    value = helper['root'](selected)
    speeds, growth, ids = [first['spec']['speed_m_s']], [value.real], [first['id']]
    previous = first
    for case in path[1:]:
        pairs = helper['match'](previous, case)['pairs']
        pair = min(pairs, key=lambda p: abs(complex(*p['before'])-value))
        if not pair['resolved'] or abs(complex(*pair['before'])-value) > 1e-8*max(1., abs(value)):
            trace_records.append(dict(wing=wing, gap_before=previous['id'], gap_after=case['id'], reason='Unresolved oscillatory branch correspondence'))
            break
        value = complex(*pair['after'])
        speeds.append(case['spec']['speed_m_s']);growth.append(value.real);ids.append(case['id'])
        previous = case
    axes[0, 0].plot(speeds, growth, 'o-', ms=3.5, color=colors[wing], label=f'{wing}% spar')
    trace_records.append(dict(wing=wing, speeds=speeds, growth=growth, case_ids=ids))
    angles=[]
    for c in group:
        q = np.asarray(c['base']['nodes'][-1]['rotation'])
        angles.append(np.rad2deg(np.arctan2(q[1, 0], q[0, 0])))
    axes[1, 1].plot([c['spec']['speed_m_s'] for c in group], angles, 'o-', ms=3.5, color=colors[wing], label=f'{wing}% spar')

axes[0, 0].axhline(0, color='#555', lw=.8)
axes[0, 0].set(xlabel='Airspeed (m/s)', ylabel='Growth rate (1/s)',
    title='Matched oscillatory branches, N = 8\nTrace stops if correspondence becomes unresolved')
axes[0, 0].legend(frameon=False)

boundaries=[b for manifest in manifests for b in manifest['observed_manifest'].get('boundaries', [])]
for wing, direction, marker in [('25', 'destabilizing', 'o'), ('25', 'stabilizing', 's'), ('75', 'destabilizing', 'o')]:
    values=[b for b in boundaries if b['status']=='resolved' and b['specification']['wing']==wing and b['specification']['transition']==direction]
    values.sort(key=lambda b: b['specification']['panels'])
    if values:
        axes[0, 1].plot([b['specification']['panels'] for b in values], [b['best_speed_m_s'] for b in values],
                       marker+'-', color=colors[wing], label=f'{wing}% {direction}')
for wing, speed in [('25',33.21),('75',24.58)]:
    axes[0, 1].axhline(speed,color=colors[wing],ls='--',lw=1,label=f'{wing}% published ASWING')
axes[0, 1].set(xlabel='Requested structural intervals', ylabel='Airspeed (m/s)',
    xticks=[8,16,32], xlim=(6,34), title='Available refined crossings\nPublished boundaries refer to an incompletely known setup')
axes[0, 1].legend(frameon=True, facecolor='white', framealpha=1, edgecolor='none', fontsize=8, loc='upper right')

for speed, color in [(20., '#4c78a8'), (24., '#d37516'), (28., '#56924b'), (33.21, '#92518d')]:
    case=next(c for c in cases if c['spec']['wing']=='25' and c['spec']['speed_m_s']==speed)
    strips=case['base']['strips']
    axes[1, 0].plot([(s['t']-1)*.718 for s in strips], [s['cl'] for s in strips], '.-', color=color, label=f'{speed:g} m/s')
axes[1, 0].axhline(-.3, color='#555', ls='--', lw=.8, label='CLmin = −0.3')
axes[1, 0].set(xlabel='Material span (m)', ylabel='Local lift coefficient', title='25% spar static loading, N = 8\nSmooth stall leakage acts before the nominal limit')
axes[1, 0].legend(frameon=False, fontsize=8, ncol=2)

speed=np.linspace(12,40,200)
approx=np.rad2deg(1.225*speed**2*.09446**2*(-.1)*.718**2/(4*.7101))
axes[1, 1].plot(speed,approx,'--',color='#444',lw=1,label='25% uniform-Cm approximation')
axes[1, 1].set(xlabel='Airspeed (m/s)', ylabel='Tip chord angle about body z (degrees)',
    title='Static twist reduces incidence\nUniform-torque approximation omits lift-arm torque')
axes[1, 1].legend(frameon=False,fontsize=8)
for ax in axes.ravel():
    ax.grid(alpha=.2)
fig.suptitle('Historical Durrant Case 4 results — before apparent-rate correction\nThese roots are superseded diagnostics, not current-kernel flutter predictions',fontsize=13)
artifacts={}
for extension in ['png','svg','pdf']:
    p=OUT/f'durrant-flutter-diagnostics.{extension}'
    fig.savefig(p,dpi=170)
    artifacts[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
receipt=dict(plotter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest(),
             matcher_sha256=hashlib.sha256(helper_path.read_bytes()).hexdigest(),
             input_manifests=manifests,traces=trace_records,artifacts=artifacts,
             scope='Historical pre-apparent-rate-correction cases and all nine refined crossings. These are not current-kernel predictions, a complete-spectrum stability proof or experimental validation.')
(OUT/'provenance.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
print(OUT/'durrant-flutter-diagnostics.png')
