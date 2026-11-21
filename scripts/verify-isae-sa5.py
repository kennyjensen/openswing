"""Literal ISAE SA-5 comparison; the independent reference is CFD, not experiment."""
from pathlib import Path
import hashlib
import io
import json
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError


def main():
    revision = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
    cache = ROOT/'.reference/isae-validation'/revision
    folder = next(cache.glob('1 - Aerodynamics/SA*/SA - 5 - *'))
    source = folder/'Aswing_Simulation_V5_96_Only/SA_5.asw'
    table = folder/'Aswing_Simulation_V5_96_Only/SA_5.txt'
    cfd = folder/'CFD_Data_StarCCM/SA5_StarCCM.csv'
    manifest = json.loads((cache.parent/'manifest.json').read_text())
    paths = [source, table, cfd, source.with_suffix('.sh')]
    sources = {p.relative_to(cache).as_posix(): manifest['files'][p.relative_to(cache).as_posix()] for p in paths}
    for p in paths:
        assert hashlib.sha256(p.read_bytes()).hexdigest() == sources[p.relative_to(cache).as_posix()]['sha256']
    aswing = np.loadtxt(table)
    reference = np.loadtxt(cfd, skiprows=1)
    assert aswing.shape == (12, 10) and reference.shape == (11, 3)
    alphas = sorted(set(aswing[:, 2]) | set(reference[:, 0]))
    model = parse_asw(source.read_text())
    assert not model.diagnostics
    cases, comparisons = [], []
    modules = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'openswing').glob('*.py'))}
    identity = dict(modules=modules, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    savedir = ROOT/'.reference/isae-sa5-runs'/hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    savedir.mkdir(parents=True, exist_ok=True)
    for frozen in [False, True]:
        for mach in [0., None]:
            mode = ('frozen' if frozen else 'current') + ('_PG0' if mach == 0 else '_PGspeed')
            lookup = {}
            for panels in [50, 100, 200]:
                for alpha in alphas:
                    spec = dict(mode=mode, panels=panels, alpha=float(alpha))
                    saved = savedir/(hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()+'.json')
                    if saved.exists():
                        row = json.loads(saved.read_text())
                        assert row['specification'] == spec
                    else:
                        start = time.monotonic()
                        condition = FlightCondition(speed=47.9, alpha=alpha, density=1.2256, mach=mach, freeze_influences=frozen)
                        try:
                            result = solve_rigid(model, condition, panels=panels)
                            assert result['converged'] and result['residual'] < 1e-8
                            qS = .5*condition.density*condition.speed**2*model.reference[0, 0]
                            force = np.sum([s['force'] for s in result['strips']], axis=0)
                            moment = np.sum([np.cross(np.asarray(s['position'])-model.reference[1], s['force'])+s['moment'] for s in result['strips']], axis=0)
                            a = np.deg2rad(alpha)
                            error = max(abs(force@[-np.sin(a), 0, np.cos(a)]/qS-result['CL']),
                                abs(force@[np.cos(a), 0, np.sin(a)]/qS-result['CD']),
                                abs(moment[1]/(qS*model.reference[0, 1])-result['Cm']),
                                abs(result['CD']-result['CDi_near']-result['CDp']))
                            assert error < 2e-10
                            row = dict(specification=spec, status='computed', result={k:float(result[k]) for k in ['CL','CD','Cm','CDi','CDi_near','CDp','residual']}, independent_check_error=error)
                            row['result'].update(CZ_body=float(force[2]/qS), CX_body=float(force[0]/qS))
                        except AnalysisError as exc:
                            row = dict(specification=spec, status='rejected', error=str(exc))
                        row['seconds'] = time.monotonic()-start
                        saved.write_text(json.dumps(row,indent=2)+'\n')
                    lookup[panels, alpha] = len(cases)
                    cases.append(row)
                print('SA-5', mode, panels, 'complete', flush=True)
            for label, rows, columns, alpha_column in [('archived_aswing',aswing,{'CL':5,'CD':6,'Cm':8,'CDi':7},2),('CFD_StarCCM_body_axes',reference,{'CZ_body':1,'CX_body':2},0),('CFD_StarCCM_wind_axes_unmatched',reference,{'CL':1,'CD':2},0)]:
                entries = [cases[lookup[200, r[alpha_column]]] for r in rows]
                errors = {}
                for key, col in columns.items():
                    error = np.asarray([p['result'][key]-r[col] for p,r in zip(entries, rows) if p['status']=='computed'])
                    errors[key] = dict(count=len(error), bias=float(error.mean()), rmse=float(np.sqrt(np.mean(error**2))), maximum_absolute_error=float(max(abs(error)))) if len(error) else None
                comparisons.append(dict(mode=mode, reference=label, requested=len(rows), computed=sum(p['status']=='computed' for p in entries), errors=errors))
    output = dict(status='LITERAL_MODEL_COMPARISONS_RECORDED_NOT_MATCHED_VALIDATION',full_suite_validated=False,
        provenance={**identity,'revision':revision,'sources':sources}, settings=dict(speed=47.9,density=1.2256,meshes=[50,100,200]),
        reference=model.reference.tolist(), archived_aswing=aswing.tolist(), cfd=reference.tolist(), cases=cases, comparisons=comparisons,
        limitations=[
            'The archived input lists one half beam from y=0 to y=2.22 with z=y and unit chord. The documented zero-origin reflection expands it to a single full beam with y in [-2.22,2.22] and z=abs(y); Sref=6 and Bref=5.9 remain the literal reference dimensions.',
            'The separate comparison series is StarCCM CFD, not a measured experimental dataset.',
            'Part I describes CFD force coefficients on the x/z axes and an integration correction to ASWING lift. Body-axis CX/CZ and explicitly unmatched wind-axis CD/CL comparisons are both recorded; exact CFD geometry, normalization and force-reduction convention are not independently reconstructed.',
            'Unknown original PG/K/F startup states are independent sensitivities. No parameters or coefficients are fitted.',
            'A physical residual and finite-mesh checks do not establish experimental agreement.'])
    (ROOT/'docs/validation/isae-sa5.json').write_text(json.dumps(output,indent=2)+'\n')


if __name__ == '__main__':
    main()
