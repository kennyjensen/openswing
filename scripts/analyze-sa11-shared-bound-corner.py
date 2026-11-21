"""Analytic endpoint check for retained aligned-root native AVL fields.

No new circulation solve or field substitution. Verify the strongest bound
source and its incoming semi-infinite-line limit at the sharp shared corner.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/sa11-native-aligned-root-20261108'
OUT = ROOT/'artifacts/isae/sa11-shared-bound-corner-20261108'
SPEC = importlib.util.spec_from_file_location('field', ROOT/'scripts/analyze-sa11-native-root-conformity.py')
FIELD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(FIELD)
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert not OUT.exists(), OUT
    previous = read(BASE/'analysis.json')
    pins = dict(previous['source_pins'])
    for path, expected in pins.items():
        if path not in ('ISAE_STATUS.md', 'docs/validation/ISAE_STATUS.md'): assert sha(ROOT/path) == expected, path
    pins.pop('ISAE_STATUS.md', None)
    for path in [ROOT/'docs/validation/ISAE_STATUS.md', Path(__file__), ROOT/'openswing/airflow_diagnostics.py',
                 ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
                 ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.txt',
                 BASE/'analysis.json']:
        pins[str(path.relative_to(ROOT))] = sha(path)
    rows = []
    radius = np.geomspace(1e-5, 1e-2, 25)
    for case in previous['cases']:
        directory = BASE/case['case']['id']; report = read(directory/'report.json')
        for name, expected in report['artifact_sha256'].items(): assert sha(directory/name) == expected
        with np.load(directory/'native-fields.npz') as data:
            f = {key:data[key].copy() for key in data.files}
        i = report['native_force_points']['worst_index']
        gamma = f['GAM'].ravel()*240
        ids = np.flatnonzero(np.arange(len(gamma)) != i)
        contributions = FIELD.finite(f['RV'][i]@FIELD.PG, f['RV1'][ids]@FIELD.PG,
                                    f['RV2'][ids]@FIELD.PG)*gamma[ids,None]@FIELD.PG
        j = int(np.argmax(np.linalg.norm(contributions,axis=1))); source = int(ids[j])
        joint = f['RV1'][i]
        assert np.array_equal(f['RV2'][source],joint)
        incoming = joint-f['RV1'][source]; incoming /= np.linalg.norm(incoming)
        outgoing = f['RV2'][i]-joint; outgoing /= np.linalg.norm(outgoing)
        offset = f['RV'][i]-joint; distance = np.linalg.norm(offset)
        assert np.linalg.norm(np.cross(offset,outgoing)) < 1e-14
        t = incoming@FIELD.PG; t /= np.linalg.norm(t)
        u = outgoing@FIELD.PG
        # Incoming ray O - l*t with circulation directed toward O. Evaluation
        # at O + r*u gives V = Gamma/r * P^T(t cross u)/(4*pi*(u²+|u|t.u)).
        coefficient = (np.cross(t,u)/(u@u+np.linalg.norm(u)*(t@u)))@FIELD.PG*FIELD.PI4INV
        asymptotic = gamma[source]*coefficient/distance
        exact = contributions[j]
        curve = np.array([FIELD.finite((joint+r*outgoing)@FIELD.PG,
            (f['RV1'][source]@FIELD.PG)[None],(joint@FIELD.PG)[None])[0]*gamma[source]@FIELD.PG for r in radius])
        expected = gamma[source]/radius[:,None]*coefficient
        bound = contributions.sum(axis=0)
        assert np.max(abs(bound-np.array(case['velocities_m_s']['bound']))) < 1e-7
        error = float(np.linalg.norm(exact-asymptotic)/np.linalg.norm(exact))
        assert error < 1e-4
        coefficient_error = float(np.linalg.norm(curve[0]*radius[0]/gamma[source]-coefficient)/np.linalg.norm(coefficient))
        assert coefficient_error < 1e-6
        rows.append(dict(case=case['case'],receiver_index=i,source_index=source,
            source_start=f['RV1'][source].tolist(),shared_endpoint=joint.tolist(),receiver=f['RV'][i].tolist(),
            receiver_distance_to_joint_m=float(distance),source_circulation_m2_s=float(gamma[source]),
            turn_degrees=float(np.rad2deg(np.arccos(np.clip(incoming@outgoing,-1,1)))),
            source_velocity_m_s=exact.tolist(),total_bound_velocity_m_s=bound.tolist(),
            source_speed_m_s=float(np.linalg.norm(exact)),other_bound_speed_m_s=float(np.linalg.norm(bound-exact)),
            coefficient_per_gamma_over_distance=coefficient.tolist(),asymptotic_velocity_m_s=asymptotic.tolist(),
            asymptotic_relative_error=error,smallest_radius_coefficient_relative_error=coefficient_error,
            radius_m=radius.tolist(),exact_speed_m_s=np.linalg.norm(curve,axis=1).tolist(),
            asymptotic_speed_m_s=np.linalg.norm(expected,axis=1).tolist()))
    predicted_growth = (rows[1]['source_circulation_m2_s']/rows[0]['source_circulation_m2_s']
                        *rows[0]['receiver_distance_to_joint_m']/rows[1]['receiver_distance_to_joint_m'])
    observed_growth = rows[1]['source_speed_m_s']/rows[0]['source_speed_m_s']
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),source_pins=pins,cases=rows,
        predicted_source_speed_growth=predicted_growth,observed_source_speed_growth=observed_growth,
        new_solver_calls=0,production_changed=False,comparison_fraction_or_scope_changed=False,
        source_audit='Steady equations64/65/67 evaluate the full induced field at rhv;69/72/73 use its span-normal component and local Mach for profile moment;155/156 distinguish bound receiver and control point;160 includes all beam horseshoes. No adjacent-bound exclusion or control-point force substitution is stated.',
        caveat='Fixed saved circulation and idealized sharp straight filaments. This verifies the local endpoint mechanism, not divergence at every fixed physical location, a full continuum solution, a native ASWING implementation detail or an accepted production state. Do not remove the source or weaken the Mach guard.')
    OUT.mkdir(parents=True)
    (OUT/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (OUT/'analyzer-used.py').write_text(Path(__file__).read_text())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = re.findall(r"'(#\w+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors')[1].split(']);')[0])
    fig,ax=plt.subplots(figsize=(8,4.9))
    for color,r in zip(colors,rows):
        ax.loglog(1000*radius,r['exact_speed_m_s'],color=color,label=f"{r['case']['span_strips']} span positions: finite bound source")
        ax.loglog(1000*radius,r['asymptotic_speed_m_s'],color=color,linestyle=':',linewidth=2)
        ax.plot(1000*r['receiver_distance_to_joint_m'],r['source_speed_m_s'],'o',color=color)
    ax.set_xlabel('Distance along upper bound line from the shared endpoint (mm)')
    ax.set_ylabel('Velocity from adjoining main-wing bound filament (m/s)')
    ax.grid(which='both',alpha=.25);ax.legend(fontsize=8)
    ax.set_title('SA-11 aligned native mesh: the adjacent-bound field follows Γ/r',fontsize=11)
    fig.text(.5,.025,'Dotted: analytical incoming-ray limit. Dots: native force receivers. Saved-field diagnostic; no new passes.',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.06,1,1));fig.savefig(OUT/'bound-corner.png',dpi=160)
    fig.savefig(OUT/'bound-corner.svg');plt.close(fig)
    print(json.dumps(dict(predicted_growth=predicted_growth,observed_growth=observed_growth,
        rows=[{k:r[k] for k in ('case','source_index','receiver_distance_to_joint_m','source_circulation_m2_s','turn_degrees','source_speed_m_s','other_bound_speed_m_s','asymptotic_relative_error')} for r in rows])))


if __name__=='__main__':main()
