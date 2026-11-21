"""Refine the FFWT-4 equilibrium mesh with identical authenticated physics."""
import argparse
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.isae_ffwt4_evidence import KernelArchive, pin, read, require, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-initial', type=Path, required=True)
    parser.add_argument('--kernel-archive', type=Path, required=True)
    parser.add_argument('--nominal', type=int, choices=(16, 32, 64, 128, 256), required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    base = args.base_initial.resolve()
    original, base_report = read(base/'plan.json'), read(base/'report.json')
    require(original['family'] == 'FFWT-4' and original['nominal'] == 32, 'Use the original nominal32 baseline')
    require(base_report['status'] == 'INITIAL_COMPARISON_COMPUTED' and base_report['residual'] <= 1e-8,
            'Unconverged base equilibrium')
    require(pin(base/'result.json') == base_report['result'], 'Changed base result')
    archive = KernelArchive(args.kernel_archive, original['kernel_pins'])
    inputs = original['source_pins'] + [original['helper'], pin(base/'plan.json'), pin(base/'request.json'),
        pin(base/'report.json'), base_report['result'], pin(__file__),
        pin(ROOT/'scripts/isae_ffwt4_evidence.py'), pin(ROOT/'docs/validation/isae-ffwt-reference-contract.json')]
    for record in inputs:
        archive.verify(record)
    request = copy.deepcopy(read(base/'request.json'))
    require(request['action'] == 'solve' and request['mode'] == 'mounted' and request['tolerance'] == 1e-8,
            'Unexpected initial solve contract')
    require(request['source'] == Path(original['source_pins'][0]['path']).read_text(), 'Changed literal model')
    request['panels'] = dict(default=args.nominal, beams={'1': dict(count=args.nominal, spacing='cosine')})
    gate = read(ROOT/'docs/validation/isae-ffwt-reference-contract.json')['gates']['mesh']
    require(gate == .001, 'The existing FFWT mesh-accuracy limit changed')
    folder = args.output_dir.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    plan = dict(schema='isae-ffwt4-spatial-initial-v1', family='FFWT-4', nominal=args.nominal,
        source_pins=original['source_pins'], kernel_pins=original['kernel_pins'],
        runtime_kernel_pins=archive.runtime_pins, kernel_archive=archive.manifest_pin,
        helper=pin(__file__), evidence_helper=pin(ROOT/'scripts/isae_ffwt4_evidence.py'), inputs=inputs,
        base_plan=pin(base/'plan.json'), base_request=pin(base/'request.json'), base_report=pin(base/'report.json'),
        base_result=base_report['result'], native_target=original['native_target'],
        fixed_history_slots=original['fixed_history_slots'],
        accuracy_gate=dict(relative=gate, normalization='Absolute change divided by the finer-mesh root moment magnitude.'),
        qualifications=original['qualifications']+[
            'Only the nominal cosine mesh count differs from the authenticated original nominal32 request.',
            'All mandatory stations remain; actual node and element counts are reported.',
            'Cold equilibrium plus an independently rebuilt residual; no state is transferred from a coarser mesh.',
            'The archived kernel is identical to the completed time-refinement study.',
            'This is spatial evidence at t=0 only, not full gust-history mesh accuracy or new native coverage.'],
        full_family_validated=False)
    write(folder/'plan.json', plan)
    write(folder/'request.json', request)
    archive.activate()
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.bridge import dispatch
    from openswing.discretization import requirements
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore, identity, matching_identity, warm_start_recipe
    import numpy as np
    started = time.monotonic()
    with (folder/'progress.jsonl').open('w') as stream:
        def progress(*event):
            stream.write(json.dumps(dict(seconds=time.monotonic()-started, event=event))+'\n')
            stream.flush()
        result = dispatch(request, progress=progress)
    write(folder/'result.json', result)
    require(result['converged'] and result['residual'] <= 1e-8, 'Unconverged initial solve')
    model = parse_asw(request['source'], beam_interpolation='drela-segspl-v1')
    require(len(model.beams) == 1 and model.beams[0].domain == (-.5, .5) and not model.diagnostics,
            'Literal model changed')
    conditions = dict(request['condition'], circulation_modes={1: 0})
    network = SourceAirflowNetwork(model, request['panels'], FlightCondition(**conditions), None, [],
        steady_trim=True, mesh_recipe=warm_start_recipe(model, request['panels'], result['equilibrium_state']))
    actual_identity = identity(network)
    require(matching_identity(actual_identity, result['equilibrium_state']['identity']), 'Rebuilt mesh differs')
    residual = network.residual(restore(network, result['equilibrium_state']))
    fresh = float(np.max(abs(residual)))
    require(fresh <= 1e-8 and network.nfev == 1, 'Fresh residual failed')
    stations = actual_identity['stations']['1'][0]
    required = requirements(model)[1]
    require(all(min(abs(float(t)-v['t']) for t in stations) <= 1e-12 for v in required),
            'Mandatory mesh station omitted')
    sensors = [v for v in result['sensors'] if v['index'] == 1]
    require(len(sensors) == 1 and sensors[0]['load_trace'] == 'left', 'Root sensor trace changed')
    predicted = sensors[0]['moment_local'][0]
    value = Decimal(original['native_target']['tokens'][2])
    half = Decimal(10)**value.as_tuple().exponent/2
    allowed = max(float(half), .05*abs(float(value)))
    for record in inputs+archive.runtime_pins+[archive.manifest_pin]:
        archive.verify(record)
    report = dict(status='INITIAL_COMPARISON_COMPUTED', nominal=args.nominal,
        seconds=time.monotonic()-started, cold_solves=1, fresh_residuals=1, residual=fresh,
        nodes=network.nn, elements=network.ne, stations=stations, mandatory_stations=required,
        predicted=predicted, expected=float(value), error_percent=100*abs(predicted-float(value))/abs(float(value)),
        tolerance=allowed, passed=abs(predicted-float(value)) <= allowed, root_sensor=sensors[0],
        reference_values_computed=1, fixed_history_slots=original['fixed_history_slots'],
        request=pin(folder/'request.json'), result=pin(folder/'result.json'),
        kernel_archive=archive.manifest_pin, loaded_kernel_modules=archive.loaded_modules(),
        source_pins_unchanged=True, kernel_pins_unchanged=True, full_family_validated=False)
    write(folder/'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'nominal', 'seconds', 'residual', 'nodes',
        'elements', 'predicted', 'expected', 'error_percent', 'passed')}), flush=True)


if __name__ == '__main__':
    main()
