"""Plot the saved SA-6 matched-observable and single-aileron comparisons."""
from pathlib import Path
import json
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'docs/validation'
data = json.loads((DEST/'isae-sa6-single-aileron.json').read_text())
colors = re.findall(r"'(#\w{6})'", re.search(
    r'plotColors = Object.freeze\(\[(.*?)\]\)',
    (ROOT/'web/plot-colors.js').read_text(), re.S).group(1))
for kind in ('combined', 'single'):
    fig, axes = plt.subplots(3, 2, figsize=(11, 10), sharex=True)
    for i, pitch in enumerate((0, 8, 12)):
        for j, coefficient in enumerate(('Cl', 'Cn')):
            ax = axes[i, j]
            if kind == 'combined':
                rows = [r for r in data['combined'] if r['case']=='20b_35c_literal'
                        and r['panels']==160 and r['body_pitch_deg']==pitch]
                x = [r['deflection_deg'] for r in rows]
                ax.plot(x, [r['reference'][coefficient] for r in rows], 'o',
                        color='#333333', fillstyle='none', label='Primary combined table')
                ax.plot(x, [r['matched'][coefficient] if r['status']=='computed' else float('nan')
                            for r in rows], color=colors[0], label='Separate up minus down')
                ax.plot(x, [r['simultaneous'][coefficient] for r in rows], '--',
                        color=colors[1], label='Simultaneous controls (previous)')
            else:
                for k, direction in enumerate(('up', 'down')):
                    rows = [r for r in data['single_aileron_rows'] if r['panels']==160
                            and r['body_pitch_deg']==pitch and r['direction']==direction]
                    x = [r['deflection_deg'] for r in rows]
                    ax.plot(x, [r['reference'][coefficient] for r in rows], 'o',
                            color=colors[k], fillstyle='none', label=f'Primary right {direction}')
                    ax.plot(x, [r['prediction'][coefficient] if r['status']=='computed' else float('nan')
                                for r in rows], color=colors[k], label=f'OpenSwing right {direction}')
            ax.set_title(f'Body pitch {pitch}° — {"roll" if j==0 else "yaw"}')
            ax.set_ylabel(r'$C_\ell$' if coefficient == 'Cl' else r'$C_n$')
            ax.grid(alpha=.2)
            ax.set_xticks([4, 12, 20, 28, 36, 44])
            if i==2:
                ax.set_xlabel('Deflection magnitude (degrees)')
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=2 if kind=='single' else 3,
               bbox_to_anchor=(.5, .01), fontsize=9)
    title = ('Corrected comparison: separate single-aileron results' if kind=='combined'
             else 'Single right aileron: upward and downward responses')
    fig.suptitle(f'SA-6 — {title}\n35%-chord, 20-inch-span aileron; 160 requested intervals\n'
                 'Body-axis moments; both coefficients normalized by wing span', fontsize=12)
    fig.tight_layout(rect=(0, .085, 1, .93))
    stem = f'isae-sa6-single-aileron-{kind}'
    for extension in ('svg', 'png'):
        fig.savefig(DEST/f'{stem}.{extension}', dpi=150)
    plt.close(fig)
