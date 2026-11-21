"""Publish the saved FW comparison for the app; no solver or plotting work."""
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/fw-current-mesh-20261114/report"
OUTPUT = ROOT / "public/validation/fw-root-locus"


def main():
    result = json.loads((REPORT / "result.json").read_text())
    receipt = json.loads((REPORT / "terminal.json").read_text())
    reference_path = ROOT / "docs/validation/fw-reference.json"
    reference = json.loads(reference_path.read_text())
    assert receipt["returncode"] == 0 and receipt["process_reaped"]
    assert receipt["inputs_unchanged"]
    cases = sorted(result["cases"], key=lambda c: c["speed_ft_s"])
    assert all(c["trim"]["mesh_recipe"] == "accurate-arc-v2" for c in cases)
    assert sum(len(c["comparisons"]) for c in cases) == result["fresh_mesh_compared_positions"]
    assert sum(len(p["plotted_roots_per_s"]) for p in reference["points"]) == result["total_published_positions"]
    speeds = " and ".join(f'{c["speed_ft_s"]:g}' for c in cases)
    tables, differences, extras = [], [], []
    for case in cases:
        speed = case["speed_ft_s"]
        rows = []
        for row in case["comparisons"]:
            label = escape(row["label"])
            sigma, omega = row["current"]
            native_sigma, native_omega = row["reference"]
            frequency_error = row["frequency_relative_error_percent"]
            frequency_text = "—" if frequency_error is None else f"{frequency_error:+.2f}%"
            rows.append(f'<tr><th scope="row">{label}</th><td>{native_sigma:+.6f}</td>'
                        f'<td>{sigma:+.6f}</td><td>{sigma-native_sigma:+.6f}</td>'
                        f'<td>{native_omega:.6f}</td><td>{abs(omega):.6f}</td><td>{frequency_text}</td></tr>')
            for coordinate, field, index, unit in [
                ("Growth rate", "growth_relative_error_percent", 0, "1/s"),
                ("Angular frequency", "frequency_relative_error_percent", 1, "rad/s"),
            ]:
                error = row[field]
                if error is not None and abs(error) > 5:
                    delta = row["difference"][index]
                    differences.append(f'<tr><th scope="row">{speed:g} / {label}</th><td>{coordinate}</td>'
                                       f'<td>{error:+.2f}%</td><td>{delta:+.6f} {unit}</td></tr>')
        tables.append(f'<h3>{speed:g} ft/s</h3><div class="table-scroll" tabindex="0" role="region" aria-label="Roots at {speed:g} feet per second">'
                      '<table><caption>Published ASWING and OpenSwing roots</caption><thead><tr><th scope="col">Root</th>'
                      '<th scope="col">ASWING σ (1/s)</th><th scope="col">OpenSwing σ (1/s)</th><th scope="col">Δσ (1/s)</th>'
                      '<th scope="col">ASWING ω (rad/s)</th><th scope="col">OpenSwing ω (rad/s)</th><th scope="col">ω error</th>'
                      '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>')
        for extra in case["unmatched"]:
            sigma, omega = extra["eigenvalue"]
            extras.append(f'{speed:g} ft/s: σ = {sigma:+.6f}/s, ω = {abs(omega):.6f} rad/s.')

    observed = escape(receipt["observed_utc"])
    page = f'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FW root-locus comparison · OpenSwing</title>
<style>
:root{{color-scheme:dark;font-family:system-ui,sans-serif;color:#dce8e7;background:#101719;line-height:1.6}}
*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:1200px;margin:auto;padding:24px clamp(16px,4vw,40px) 64px}}
a{{color:#91e1bd;text-underline-offset:3px}}a:hover{{color:#c6f5df}}a:focus-visible,summary:focus-visible,[tabindex]:focus-visible{{outline:2px solid #91e1bd;outline-offset:4px}}
nav,.downloads{{display:flex;flex-wrap:wrap;gap:12px 24px}}h1{{font-size:clamp(1.6rem,4vw,2.4rem);line-height:1.2;margin:28px 0 12px}}h2{{font-size:1.2rem;margin-top:28px}}h3{{font-size:1rem}}
p{{max-width:85ch}}.muted,figcaption{{color:#a7bab8}}.coverage{{display:flex;flex-wrap:wrap;gap:12px;margin:24px 0}}
.coverage p{{background:#162023;border:1px solid #2a393c;border-radius:6px;padding:14px 20px;margin:0;flex:1 1 200px}}
.coverage strong{{display:block;font-size:1.5rem;color:#91e1bd}}figure{{margin:24px 0}}.plot-scroll{{overflow:auto;border-radius:6px;background:white}}
.plot-scroll img{{display:block;width:100%;min-width:760px;height:auto}}figcaption{{margin:10px 0;font-size:.9rem}}
.table-scroll{{max-width:100%;overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:.9rem;font-variant-numeric:tabular-nums}}
caption{{text-align:left;color:#a7bab8;padding:8px 0}}th,td{{padding:10px 12px;border-bottom:1px solid #2a393c;text-align:right;white-space:nowrap}}th:first-child,td:first-child{{text-align:left}}
thead{{background:#162023}}details{{border:1px solid #2a393c;border-radius:6px;padding:16px;margin:24px 0}}summary{{cursor:pointer;color:#91e1bd;font-weight:600}}footer{{border-top:1px solid #2a393c;margin-top:32px;padding-top:16px;font-size:.85rem}}
</style></head>
<body><main>
<nav aria-label="Comparison navigation"><a href="/">OpenSwing</a><a href="/isae-progress/">ISAE progress</a></nav>
<h1>FW root-locus comparison</h1>
<p>OpenSwing’s flying-wing roots overlaid on Drela’s published ASWING results at <strong>{speeds} ft/s</strong>. This saved comparison opens without running a solver.</p>
<div class="coverage"><p><strong>{len(cases)} of {len(reference['points'])} speeds</strong>Compared with the current mesh</p><p><strong>{result['fresh_mesh_compared_positions']} / {result['total_published_positions']} root positions</strong>Compared so far; this is coverage, not a pass count</p></div>
<figure>
<div class="plot-scroll" tabindex="0" role="region" aria-label="Root comparison plot; scroll horizontally on small screens"><a href="comparison.svg" aria-label="Open the root comparison plot at full size"><img src="comparison.svg" width="1680" height="992" alt="Growth rate versus angular frequency: published roots are circles, OpenSwing roots are crosses. Orange is 38 feet per second and blue is 64. The right panel enlarges the slow modes. A gray triangle marks an additional OpenSwing root."></a></div>
<figcaption>Left: all compared roots. Right: slow-mode zoom. Horizontal axis: growth rate σ (1/s); vertical axis: angular frequency ω (rad/s). Negative growth means decay. Scroll sideways on a phone, or tap the plot to enlarge it.</figcaption>
</figure>
<nav class="downloads" aria-label="Plot downloads"><a href="comparison.svg" download>Download SVG</a><a href="comparison.png" download>Download PNG</a><a href="result.json" download>Comparison data (JSON)</a><a href="{escape(reference['source']['url'], quote=True)}" target="_blank" rel="noopener">Drela’s original root map ↗</a></nav>
<h2>Remaining differences</h2>
<p>Coordinates exceeding the 5% relative target are shown below. The small growth-rate differences are within the estimated ±0.01/s uncertainty of reading the published plot. The <strong>38 ft/s R5 frequency difference exceeds both the target and that uncertainty</strong>.</p>
<div class="table-scroll" tabindex="0" role="region" aria-label="Differences exceeding five percent"><table><thead><tr><th scope="col">Speed / root</th><th scope="col">Coordinate</th><th scope="col">Relative error</th><th scope="col">Absolute difference</th></tr></thead><tbody>{''.join(differences)}</tbody></table></div>
<p class="muted">Near-zero growth is best compared in absolute units; the complete table below includes Δσ. R labels identify points within each speed, not established mode branches across speeds. Connecting lines join reference/current pairs only.</p>
<details><summary>All compared roots and numerical differences</summary>{''.join(tables)}<p>Additional OpenSwing roots without a plotted reference counterpart: {' '.join(extras) or 'None in these searches.'}</p><p>Real modes have no oscillation-frequency percentage (—). Differences use OpenSwing minus published ASWING.</p></details>
<h2>Comparison setup</h2>
<p>Literal <a href="{escape(reference['aircraft']['url'], quote=True)}">Drela fw.asw</a>, with the current mesh recipe, a requested count of 32 and 40 actual lifting panels. The steady unpowered glide is inferred from the published trim table. A cold trim at 64 ft/s is continued through 50 to 38 ft/s. Physical properties are unchanged.</p>
<p>All {result['direct_residual_passed']}/{result['direct_residual_total']} independent full-equation checks pass (maximum normalized residual {result['maximum_scaled_full_residual']:.3g}). These check the computed modes against the equations; they do not make every ASWING comparison a pass. The original ASWING mesh and detailed settings remain unknown. The other speeds and Bode gain/phase comparison remain open.</p>
<footer><p>Numerical report recorded <time datetime="{observed}">{observed}</time>. This is a saved validation snapshot, independent of the model currently loaded in the app.</p>
<p><a href="checks.json" download>Full-equation checks</a> · <a href="reference.json" download>Digitized reference</a> · <a href="source-pins.json" download>Solver source hashes</a> · <a href="publication.json" download>Snapshot provenance</a></p></footer>
</main></body></html>
'''
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = {name: REPORT / name for name in
             ("comparison.svg", "comparison.png", "result.json", "checks.json", "source-pins.json")}
    files["reference.json"] = reference_path
    for name, path in files.items():
        shutil.copyfile(path, OUTPUT / name)
    (OUTPUT / "index.html").write_text(page)
    publication = dict(
        published_utc=datetime.now(timezone.utc).isoformat(),
        numerical_report_observed_utc=receipt["observed_utc"],
        report=str(REPORT.relative_to(ROOT)),
        generator=str(Path(__file__).relative_to(ROOT)),
        copied_files={name: dict(source=str(path.relative_to(ROOT)), sha256=sha256(path.read_bytes()).hexdigest())
                      for name, path in files.items()},
    )
    (OUTPUT / "publication.json").write_text(json.dumps(publication, indent=2) + "\n")
    print(f"Published {len(cases)} speeds, {result['fresh_mesh_compared_positions']} root comparisons to {OUTPUT}")


if __name__ == "__main__":
    main()
