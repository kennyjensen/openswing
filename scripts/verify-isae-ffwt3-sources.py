"""Check literal FFWT-3 joints, sensors and history inventory without a solve."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import isae_suite_ffwt3 as adapter
from openswing.asw import parse_asw
from openswing.geometry import model_meshes


def audit_model(path):
    model = parse_asw(path.read_text(), beam_interpolation='drela-segspl-v1')
    domains = {b.index: [float(v) for v in b.domain] for b in model.beams}
    outside = []
    for i, joint in enumerate(model.records['joint'], 1):
        for beam, station in ((int(joint[0]), float(joint[2])),
                              (int(joint[1]), float(joint[3]))):
            if not domains[beam][0] <= station <= domains[beam][1]:
                outside.append(dict(joint=i, beam=beam, station=station, domain=domains[beam]))
    contract = adapter.model_contract(path.stem)
    adapter.require(contract['beam_domains'] == {str(k):v for k,v in domains.items()} and
                    contract['out_of_range_joints'] == outside, 'literal geometry contract differs')
    sensors = [dict(index=int(r[0]), beam=int(r[1]), station=float(r[2]),
                    inside=bool(domains[int(r[1])][0] <= r[2] <= domains[int(r[1])][1]))
               for r in model.records['sensor']]
    adapter.require([s['index'] for s in sensors] == [1,2] and all(s['inside'] for s in sensors),
                    'sensor inventory or station changed')
    rejections = []
    for nominal in (8,16):
        try:
            model_meshes(model, nominal)
        except ValueError as exc:
            adapter.require('Attachment station is outside beam' in str(exc), 'unexpected mesh failure')
            rejections.append(dict(nominal=nominal, error=str(exc)))
        else:
            raise ValueError('FFWT3 literal model unexpectedly meshes')
    return dict(model=path.name, source=adapter.pin(path), diagnostics=model.diagnostics,
                beam_domains=domains, out_of_range_joints=outside, sensors=sensors,
                meshing_rejections=rejections)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    kernels = [adapter.pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))]
    jobs = adapter.plan(ROOT)
    models = [audit_model(p) for p in sorted(adapter.sources(ROOT)[1].glob('*.asw'))]
    adapter.require(kernels == [adapter.pin(Path(p['path'])) for p in kernels], 'production changed')
    result = dict(schema='isae-ffwt3-source-audit-v1', status='SOURCE_BLOCKERS_VERIFIED',
        models=models, jobs=len(jobs), retained_reference_values=sum(j['retained_reference_values'] for j in jobs),
        required_slots=sum(j['expected_outputs'] for j in jobs),
        missing_reference_slots=sum(j['expected_outputs']-j['retained_reference_values'] for j in jobs),
        blocker_counts=dict(Counter(code for job in jobs for code in job['blocker_codes'])),
        histories=[{k:j[k] for k in ('id','native_rows','scheduled_rows','time_range','blocker_codes',
                                   'source_pins','retained_reference_values','expected_outputs')} for j in jobs],
        kernel_pins=kernels, kernel_pins_unchanged=True, physical_solves=0,
        helper_pin=adapter.pin(__file__), qualifications=adapter.QUALIFICATIONS,
        full_family_validated=False)
    path=args.output_dir/'literal-model-audit.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','jobs','retained_reference_values','required_slots',
                                          'missing_reference_slots','blocker_counts','physical_solves')}),flush=True)


if __name__ == '__main__':
    main()
