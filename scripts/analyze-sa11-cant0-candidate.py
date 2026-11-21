"""Verify the unpaired, unchanged full-scale cant0 geometry checks."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/isae/sa11-cant0-candidate-20261108'
spec = importlib.util.spec_from_file_location('cant', ROOT / 'scripts/verify-sa11-cant0-candidate.py')
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)


def main():
    plan = D.read(OUT / 'plan.json'); D.check(plan)
    assert D.sha(OUT / 'driver-used.py') == plan['pins']['scripts/verify-sa11-cant0-candidate.py']
    model = D.parse_asw(D.D.CANT.read_text())
    assert json.loads(json.dumps(D.audit_model(model))) == plan['source_audit']
    rows, artifacts = [], {}
    for case in plan['cases']:
        folder = OUT / case['id']
        r = D.read(folder / 'report.json')
        assert r['case'] == case and not r['original_setup_authenticated']
        assert r['original_joint_errors_preserved'] and r['accepted_primary_checks'] == 0
        for name, digest in r['artifact_sha256'].items():
            assert D.sha(folder / name) == digest, (case, name)
        process = D.read(folder / 'process.json'); assert process['returncode'] == 0
        condition = D.read(folder / 'condition.json')
        assert condition['alpha'] == case['alpha'] and condition['speed'] == 255
        assert condition['mach'] == 0 and condition['stall'] and condition['freeze_influences']
        fields = dict(np.load(folder / 'native-fields.npz'))
        mapping = D.read(folder / 'mapped-beams.json')
        meshes, g, errors, details = D.mapped_beams(model, fields, mapping['segments'])
        assert errors == r['geometry_errors'] and details == mapping['mapping']
        assert max(errors.values()) < 2e-11
        assert [m['transverse_axis'] for m in details] == [1, 2, 2]
        data = dict(np.load(folder / 'state.npz'))
        s = np.concatenate([m.frames[..., 1] for m in meshes])
        v = data['velocity']
        mn = np.linalg.norm(v - np.sum(v*s,axis=1)[:,None]*s,axis=1)/model.constants[2]
        production = r['production']
        assert production['status'] == 'rejected' and r['production_values'] is None
        assert production['details']['kind'] == 'section_normal_mach'
        assert not (folder / 'openswing.json').exists()
        assert mn.max() > 1 and abs(mn.max()-production['maximum']['normal_mach']) < 1e-12
        assert production['residual'] < 1e-8 and np.all(data['stall_margin'] > 0)
        assert production['stalled_strips'] == 0
        for suffix, target in r['reference_hypotheses'].items():
            raw = np.loadtxt(D.D.SOURCE / 'Wing_tip_up' / f'wingtip_up_Ma_{suffix}.txt')
            row = raw[raw[:,71] == case['alpha']]; assert row.shape == (1,82)
            refs = {key:float(row[0,col]) for key,col in [('CL',77),('CD',78),('CDi',79),('Cm',80),('efficiency',81)]}
            assert refs == target['values']
            assert target['native_error_percent'] == {k:100*(r['native'][k]/refs[k]-1) for k in ('CL','CDi','efficiency')}
            # Normalization agreement is a necessary condition only. It is
            # checked independently in both printed dimensional channels.
            for force, coeff in ((75,77),(76,78)):
                area = 2*row[0,force]/(model.constants[1]*row[0,69]**2*row[0,coeff])
                assert abs(area-model.reference[0,0]) < .001
        # Independent body force reconstruction from exported native fields.
        labels = D.D.BASE.CONVERT.MATCHED.NATIVE.labeled(folder / 'total.txt')
        force = np.sum(2*fields['GAM'].ravel()[:,None]*np.cross(fields['VINF']+fields['VV'],
                         fields['RV2']-fields['RV1']),axis=0)/model.reference[0,0]
        actual = [labels['CXtot, Cltot, Cl\'tot'][0],labels['CYtot, Cmtot'][0],labels['CZtot, Cntot, Cn\'tot'][0]]
        force_error = float(np.max(abs(force-actual))); assert force_error < 2e-10
        rows.append(dict(case=case, native=r['native'], reference_hypotheses=r['reference_hypotheses'],
            geometry_errors=errors, production_status=production['status'], maximum_normal_mach=float(mn.max()),
            maximum=production['maximum'], residual=production['residual'], stalled_strips=0,
            minimum_stall_margin_widths=float(data['stall_margin'].min()/.05),
            native_gamma_reconstruction_relative_error=r['native_gamma_reconstruction_relative_error'],
            production_native_gamma_relative_error=r['production_native_gamma_relative_error'],
            native_velocity_reconstruction_error=r['native_field_reconstruction_error'],
            production_velocity_reconstruction_error=r['production_velocity_reconstruction_error'],
            native_force_reconstruction_error=force_error,
            native_seconds=process['seconds'], production_seconds=production['seconds']))
        for path in folder.iterdir():
            if path.is_file(): artifacts[str(path.relative_to(ROOT))] = D.sha(path)
    assert len(rows) == 2
    D.check(plan)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), cases=rows, native_calls=2,
        production_calls=2, production_rejected=2, stalled_strips=0,
        source_pins=plan['pins'], artifact_pins=artifacts, plan_sha256=D.sha(OUT/'plan.json'),
        analyzer_sha256=D.sha(Path(__file__)), original_inputs_changed=False,
        production_equations_changed=False, primary_fraction_or_scope_changed=False,
        original_setup_authenticated=False, finding='The unpaired full-scale cant0 geometry does not match the upper .75/.78 CL/CDi/efficiency targets at alpha0/1. Matching reference area alone is insufficient; no reassignment is justified.')
    D.write(OUT / 'analysis.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_pins','artifact_pins')}), flush=True)


if __name__ == '__main__': main()
