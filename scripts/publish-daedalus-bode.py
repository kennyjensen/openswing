"""Publish the checked saved Daedalus comparison; no solver or plotting job."""
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'artifacts/daedalus-regular-mesh-response-20261114/report'
OUTPUT = ROOT/'public/validation/daedalus-bode'


def main():
    result = json.loads((REPORT/'result.json').read_text())
    terminal = json.loads((REPORT/'terminal.json').read_text())
    assert terminal['returncode'] == 0 and terminal['process_reaped'] and terminal['inputs_unchanged']
    assert not terminal['timed_out']
    for path, digest in json.loads((REPORT/'plan.json').read_text())['inputs_sha256'].items():
        assert sha256(Path(path).read_bytes()).hexdigest() == digest, path
    labels = {'yaw-low-min':'Yaw dip near 1 Hz', 'roll-low-min':'Roll dip near 1.5 Hz',
              'yaw-high-min':'Yaw dip near 7 Hz', 'roll-high-min':'Roll dip near 7 Hz',
              'yaw-high-max':'Yaw peak near 9 Hz'}
    rows = []
    for f in result['features']:
        rows.append(f'<tr><th scope="row">{labels[f["name"]]}</th>'
            f'<td>{f["reference_frequency_hz"]:.5f}</td><td>{f["current_extremum_frequency_hz"]:.5f}</td>'
            f'<td>{f["extremum_frequency_difference_percent"]:+.2f}%</td>'
            f'<td>{f["reference_magnitude"]:.6g}</td><td>{f["current_extremum_magnitude"]:.6g}</td>'
            f'<td>{f["extremum_magnitude_difference_percent"]:+.2f}%</td>'
            f'<td>{f["same_frequency_difference_percent"]:+.2f}%</td></tr>')
    one_hz = []
    names = dict(yaw_rate='Yaw rate', roll_rate='Roll rate', sideslip='Sideslip', bank='Bank')
    for r in result['one_hz']:
        one_hz.append(f'<tr><th scope="row">{names[r["channel"]]}</th><td>{r["unit"]}</td>'
            f'<td>{r["reference_magnitude"]:.6g}</td><td>{r["magnitude"]:.6g}</td>'
            f'<td>{r["difference_percent"]:+.2f}%</td></tr>')
    observed = escape(terminal['observed_utc'])
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daedalus Bode comparison · OpenSwing</title>
<style>
:root{{color-scheme:dark;font-family:system-ui,sans-serif;color:#dce8e7;background:#101719;line-height:1.6}}
*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:1200px;margin:auto;padding:24px clamp(16px,4vw,40px) 64px}}
a{{color:#91e1bd;text-underline-offset:3px}}a:hover{{color:#c6f5df}}a:focus-visible,[tabindex]:focus-visible{{outline:2px solid #91e1bd;outline-offset:4px}}
nav{{display:flex;flex-wrap:wrap;gap:12px 24px}}h1{{font-size:clamp(1.6rem,4vw,2.4rem);line-height:1.2;margin:28px 0 12px}}h2{{font-size:1.2rem;margin-top:28px}}
p{{max-width:90ch}}.muted,figcaption{{color:#a7bab8}}.finding{{padding:16px 20px;border-left:3px solid #e2a365;background:#1e2425}}
figure{{margin:24px 0}}.plot-scroll{{overflow:auto;background:white;border-radius:6px}}.plot-scroll img{{display:block;width:100%;min-width:760px;height:auto}}figcaption{{margin:10px 0;font-size:.9rem}}
.table-scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:.9rem;font-variant-numeric:tabular-nums}}caption{{text-align:left;padding:8px 0;color:#a7bab8}}
th,td{{padding:10px 12px;text-align:right;white-space:nowrap;border-bottom:1px solid #2a393c}}th:first-child,td:first-child{{text-align:left}}thead{{background:#162023}}
footer{{border-top:1px solid #2a393c;margin-top:32px;padding-top:16px;font-size:.85rem}}
</style></head><body><main>
<nav aria-label="Comparison navigation"><a href="/">OpenSwing</a><a href="/validation/fw-root-locus/index.html">FW root locus</a><a href="/isae-progress/">ISAE progress</a></nav>
<h1>Daedalus Bode comparison</h1>
<p>Four rudder-response magnitudes from the current OpenSwing mesh, compared with Drela’s published ASWING drawing. This saved snapshot opens without running a solver.</p>
<h2>Reproduce this case in Bode response</h2>
<ol><li>In the app’s Editor, select Daedalus, then click <strong>Load checked level-flight case</strong>. This loads the trim and settings used here; selecting the aircraft alone preserves other analysis settings.</li><li>Click <strong>Run analysis</strong>. Select <strong>control.3 · Rudder → Flight frame → Yaw angular velocity Ω_z · body z</strong>.</li><li>Set angular response units to <strong>Degrees</strong>, frequency units to <strong>Cycles / input T</strong> (Hz for this model), and gain to <strong>Magnitude · logarithmic</strong>.</li></ol>
<p>At exactly 1 Hz the saved OpenSwing magnitude is <strong>0.0748817 deg/s per F3</strong>. The checked case uses <strong>ASWING structure + airflow</strong> equations, 6.7 m/s (21.9816 ft/s), level-flight trim and a free response frame. Loading the aircraft alone can retain <strong>Existing midpoint equations</strong> and other operating settings. Its default 41-point grid is coarser than the 162 samples below. This can soften a narrow feature; it should not cause a large discrepancy at a shared frequency.</p>
<p>The older label “Yaw rate r · body z” selected this same Ω_z value. Ω_z is aircraft-frame angular velocity. Lowercase ω_z is local elastic angular velocity, available under <strong>Structural nodes → Elastic angular velocity ω_z</strong>. The <a href="/validation/daedalus-sensor-average/index.html">sensor-average experiment</a> is a separate diagnostic.</p>
<p class="finding"><strong>The match remains incomplete.</strong> OpenSwing’s yaw dip near 1 Hz is too shallow, while the nearby roll dip is too deep. The high-frequency peak is much closer in frequency. Drela’s original operating point is unavailable; the comparison does not establish identical run settings.</p>
<figure><div class="plot-scroll" tabindex="0" role="region" aria-label="Four Bode magnitude plots; scroll horizontally on small screens"><a href="comparison.svg" aria-label="Open the Bode comparison at full size"><img src="comparison.svg" width="1200" height="840" alt="Logarithmic frequency and magnitude plots for yaw rate, roll rate, sideslip and bank. OpenSwing is red; Drela’s drawing is dashed blue. The strongest disagreements occur around the low-frequency yaw and roll dips."></a></div>
<figcaption>Frequency is in Hz; amplitudes are per unit native F3. Shading represents a conservative allowance for reading the PDF coordinates, not physical uncertainty or a pass tolerance. Lines join saved samples. Tap the plot to enlarge it.</figcaption></figure>
<nav aria-label="Comparison downloads"><a href="comparison.svg" download>SVG</a><a href="comparison.png" download>PNG</a><a href="comparison.csv" download>All values (CSV)</a><a href="result.json" download>Complete result (JSON)</a><a href="https://web.mit.edu/drela/Public/web/aswing/rudder-bode.pdf" target="_blank" rel="noopener">Drela’s original drawing ↗</a></nav>
<h2>At exactly 1 Hz</h2>
<div class="table-scroll" tabindex="0" role="region" aria-label="Response at one Hertz"><table><caption>OpenSwing minus the central reference drawing, divided by the reference</caption><thead><tr><th scope="col">Output</th><th scope="col">Unit</th><th scope="col">Drela</th><th scope="col">OpenSwing</th><th scope="col">Difference</th></tr></thead><tbody>{''.join(one_hz)}</tbody></table></div>
<p>Yaw is high while roll and bank are low. A single input-amplitude conversion cannot reconcile these differences. The drawing supplies no response phases, so only magnitudes are compared.</p>
<h2>Dip and peak locations</h2>
<div class="table-scroll" tabindex="0" role="region" aria-label="Extrema and their differences"><table><caption>Rate magnitudes in deg/s per native F3; frequency in Hz</caption><thead><tr><th scope="col">Feature</th><th scope="col">Drela Hz</th><th scope="col">OpenSwing Hz</th><th scope="col">Frequency difference</th><th scope="col">Drela magnitude</th><th scope="col">OpenSwing magnitude</th><th scope="col">Extremum magnitude difference</th><th scope="col">Difference at Drela’s Hz</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="muted">Extremum magnitudes compare each curve at its own dip or peak. The final column instead compares both at Drela’s frequency. OpenSwing extrema were refined with the full saved matrices; the reference extrema are vertices of the published drawing. No aircraft parameter was adjusted to obtain these values.</p>
<h2>Animation versus angular rate</h2>
<p>The app now defaults to model-time playback. For Daedalus, 1 Hz plays one cycle per second. The optional four-second phase-inspection clock changes visible turning speed and cannot be read as physical angular rate. Input amplitude scales animation, while these Bode magnitudes remain per unit input.</p>
<p>At 1 Hz, the checked aircraft-frame heading amplitude is 0.0119351° per F3. Its physical heading-rate amplitude is 0.0749905°/s; the plotted body yaw rate is 0.0748817°/s. The small difference comes from the Euler-angle projection.</p>
<h2>Compared configuration and numerical checks</h2>
<p>Literal public dae.asw, trimmed level flight at 6.7 m/s, Mach 0.1, circulation lag, live influence geometry, and source airflow. The redistributed default mesh has 98 intervals and 103 nodes. All 1,953 descriptor states are retained; exact elimination reduces the frequency factorization to 717 coordinates.</p>
<p>{result['observed_samples']} distinct saved frequencies are shown. The maximum scaled matrix residual is {result['maximum_scaled_matrix_residual']:.3g}. Three independent full-equation derivative directions also check the assembled matrices. These establish numerical consistency, not agreement with the unknown original ASWING setup or mesh convergence.</p>
<footer><p>Snapshot recorded <time datetime="{observed}">{observed}</time>. This comparison is independent of the model currently loaded in the app.</p>
<nav aria-label="Provenance downloads"><a href="reference.json" download>Native reference vertices</a><a href="source-pins.json" download>Numerical source hashes</a><a href="publication.json" download>Snapshot provenance</a></nav></footer>
</main></body></html>
'''
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = ['comparison.svg', 'comparison.png', 'comparison.csv', 'result.json', 'reference.json', 'source-pins.json']
    for name in files:
        shutil.copyfile(REPORT/name, OUTPUT/name)
    (OUTPUT/'index.html').write_text(page)
    receipt = dict(published_utc=datetime.now(timezone.utc).isoformat(),
        numerical_report_observed_utc=terminal['observed_utc'], report=str(REPORT.relative_to(ROOT)),
        generator=str(Path(__file__).relative_to(ROOT)), copied_files={name:dict(
            source=str((REPORT/name).relative_to(ROOT)), sha256=sha256((REPORT/name).read_bytes()).hexdigest()) for name in files},
        page_sha256=sha256((OUTPUT/'index.html').read_bytes()).hexdigest())
    (OUTPUT/'publication.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'Published {result["observed_samples"]} saved frequencies to {OUTPUT}')


if __name__ == '__main__':
    main()
