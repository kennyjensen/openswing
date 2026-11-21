"""Independent geometry/reduction checks and a plot of the two saved runs."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('receivers', ROOT/'scripts/verify-sa11-winglet-receivers.py')
DRIVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER)
read = DRIVER.read; sha = DRIVER.sha; write = DRIVER.write


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); source = args.input.resolve(); out = args.output.resolve()
    assert not out.exists(), out
    plan = read(source/'plan.json'); analysis = read(source/'analysis.json')
    DRIVER.check(plan['pins']); DRIVER.check(analysis['report_pins'])
    model = DRIVER.INC.model_at(-4.)
    errors = {'axis':0., 'hv':0., 'cp':0., 'force_sum':0., 'decomposition':0.}
    for report in analysis['cases']:
        folder = source/report['case']['id']
        for name, pin in report['artifact_sha256'].items(): assert sha(folder/name) == pin, name
        assert report['production']['status'] == 'rejected'
        settings = read(folder/'mesh-settings.json')
        with np.load(folder/'geometry.npz') as g:
            first = 0
            for beam in model.beams:
                t = np.array(settings[str(beam.index)]['nodes'])
                positions = beam.position(t)
                delta = np.diff(positions, axis=0); widths = np.linalg.norm(delta, axis=1)
                assert np.all(widths > 0)
                # These beams are straight on each side of their explicit
                # breaks. Reconstruct physical arc and Eq.154 without meshes.
                arc = np.r_[0., np.cumsum(widths)]
                theta = np.arccos(np.clip(2*arc/arc[-1]-1, -1., 1.))
                theta_a = .5*(theta[:-1]+theta[1:])
                sa = .5*arc[-1]*(1+np.cos(theta_a))
                fraction = (sa-arc[:-1])/widths
                tm = t[:-1]+fraction*np.diff(t)
                ra = positions[:-1]+fraction[:, None]*delta
                span = delta/widths[:, None]; across = np.hypot(span[:,1], span[:,2])
                chord = beam.value('chord', tm)
                hv = ra.copy(); hv[:,0] += (.25-beam.value('Xax',tm))*chord/across
                cp = hv.copy(); cp[:,0] += beam.value('dCLda',tm)*chord/(4*np.pi*across)
                selected = slice(first, first+len(widths))
                for key, value, saved in [('axis',ra,'rm'),('hv',hv,'hv'),('cp',cp,'cp')]:
                    errors[key] = max(errors[key], float(np.max(abs(value-g[saved][selected]))))
                first += len(widths)
            assert first == len(g['hv']) == 64
        for label, replay in report['replays'].items():
            with np.load(folder/f'{label}.npz') as data:
                for key in ('CL','CD'):
                    total = math.fsum(map(float, data[f'{key}_terms'].ravel()))
                    errors['force_sum'] = max(errors['force_sum'], abs(total-replay[f'formal_{key}']))
                assert float(data['mach'].max()) == replay['maximum_mach']
        for key, d in report['symmetric_decomposition'].items():
            r = report['replays']
            a,b,c,e = [r[k][key] for k in ('native-old','whole-old','native-new','whole-new')]
            independently = dict(change=e-a, receiver=.5*math.fsum([b,-a,e,-c]), circulation=.5*math.fsum([c,-a,e,-b]))
            errors['decomposition'] = max(errors['decomposition'], *(abs(v-d[k]) for k,v in independently.items()))
    assert max(errors[k] for k in ('axis','hv','cp')) < 2e-11, errors
    assert max(errors[k] for k in ('force_sum','decomposition')) < 2e-15, errors
    out.mkdir(parents=True)
    plot(analysis, out)
    result = dict(verified_utc=datetime.now(timezone.utc).isoformat(), errors=errors,
        cases=2, new_solver_calls=0, original_states_still_rejected=True,
        input_analysis=str((source/'analysis.json').relative_to(ROOT)), input_sha256=sha(source/'analysis.json'),
        current_pins_checked=len(plan['pins']), source_reports_checked=len(analysis['report_pins']),
        script_sha256=sha(Path(__file__)), plot_sha256={p.name:sha(p) for p in out.iterdir()},
        scope='Independent straight-piece material-arc reconstruction of Eqs.151-157, scalar force reductions and exact receiver/circulation decomposition; no new aerodynamic solves.')
    write(out/'verification.json', result); print(json.dumps(result), flush=True)


def plot(analysis, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    palette = (ROOT/'web/plot-colors.js').read_text()
    colors = re.findall(r"'(#\w+)'", palette.split('export const plotColors')[1].split(']);')[0])
    rows = analysis['cases']; x = np.arange(2); w = .34
    fig, axes = plt.subplots(1,2,figsize=(10,4.3))
    for j,(label,color) in enumerate([('Native receivers',colors[0]),('Whole-beam receivers',colors[1])]):
        values = [r['old_reference_error_percent']['CD'] if j == 0 else r['new_formal_reference_error_percent']['CD'] for r in rows]
        bars = axes[0].bar(x+(j-.5)*w, values, width=w, label=label, color=color)
        axes[0].bar_label(bars, labels=[f'{v:.3f}%' for v in values], padding=4, fontsize=9)
        values = [r['replays']['native-old' if j == 0 else 'whole-new']['maximum_mach'] for r in rows]
        bars = axes[1].bar(x+(j-.5)*w, values, width=w, label=label, color=color)
        axes[1].bar_label(bars, labels=[f'{v:.3f}' for v in values], padding=4, fontsize=9)
    axes[0].set_ylabel('Formal CD error relative to archive (%)'); axes[0].set_ylim(0,25)
    axes[1].set_ylabel('Maximum section-normal Mach'); axes[1].set_ylim(0,1.95)
    axes[1].axhline(1., color='#aa3333', linestyle='--', linewidth=1)
    axes[1].text(1.4,1.02,'Mach limit',ha='right',fontsize=9,color='#aa3333')
    for ax in axes:
        ax.set_xticks(x,['0°','1°']); ax.set_xlabel('Aircraft angle of attack')
        ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
    axes[0].legend(fontsize=8,loc='upper left')
    fig.suptitle('SA-11: fixed vortex endpoints, different receiver sampling')
    fig.text(.5,.015,'All states remain rejected. Force sums are diagnostics, not accepted aerodynamic loads.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.035,1,.94))
    for ext in ('png','svg'): fig.savefig(out/f'winglet-receivers.{ext}',dpi=160)
    plt.close(fig)


if __name__ == '__main__': main()
