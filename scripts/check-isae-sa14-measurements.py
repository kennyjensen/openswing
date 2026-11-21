"""Distinguish pressure stations from drawn curve endpoints in Figure7 CSV."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    sources=json.loads((D/'isae-sa14-sources.json').read_text())
    figure=next(f for f in sources['experimental'] if f['filename']=='Figure7.csv')
    primary=ROOT/sources['primary']['path'];assert sha(primary)==sources['primary']['sha256']
    rows=[]
    # Primary Figure4 (PDF29, printed28): outer stations are .10,.30,.55,
    # .75,.90,.96; wing alone additionally has centerline and .03 stations.
    # The matching tolerance describes digitization coordinates, not a change
    # to the measured force, solver station, or model geometry.
    tolerance=.015
    for series in figure['series']:
        stations=[.10,.30,.55,.75,.90,.96]
        if series['label'].startswith('Wing_only'):stations=[0.,.03]+stations
        points=[]
        for p in series['points']:
            x,y=p['xy'];nearest=min(stations,key=lambda s:abs(s-x))
            if abs(x-nearest)<tolerance:
                classification='instrumented_station';nominal=nearest
            elif abs(x-1.)<tolerance:
                classification='drawn_tip_curve_endpoint';nominal=1.
            else:raise AssertionError(('Unresolved digitization coordinate',series['label'],p))
            points.append(dict(p,classification=classification,nominal_primary_station=nominal,
                               coordinate_difference=x-nominal))
        assert sum(p['classification']=='instrumented_station' for p in points)==len(stations)
        assert sum(p['classification']=='drawn_tip_curve_endpoint' for p in points)==1
        rows.append(dict(label=series['label'],points=points))
    assert sum(p['classification']=='instrumented_station' for r in rows for p in r['points'])==42
    out=dict(status='PRIMARY_STATION_AUDIT_COMPLETE',source_sha256=sha(D/'isae-sa14-sources.json'),
        primary_sha256=sha(primary),script_sha256=sha(Path(__file__)),visually_reviewed_pdf_pages=[29,32],
        source_figure=4,comparison_figure=7,coordinate_matching_tolerance=tolerance,
        rows=rows,instrumented_points=42,drawn_tip_curve_endpoints=6,
        limitations=['This is an explicit inference from primary instrumentation locations and the plotted markers/curves. Original digitization metadata is unavailable.',
            'No value or abscissa is changed; the six tip curve points remain in the raw and all-point comparison records.',
            'This supplement does not reinterpret the unresolved Figure17.csv or supply experimental uncertainty.'])
    (D/'isae-sa14-measurements.json').write_text(json.dumps(out,indent=2)+'\n')
    print(out['status'],42,'instrumented points,',6,'drawn endpoints',flush=True)


if __name__=='__main__':main()
