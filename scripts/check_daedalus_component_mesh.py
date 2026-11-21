"""Count Daedalus component mesh/display intervals without running a solve."""
import argparse
from check_daedalus_load_sensitivity import ROOT, write
from daedalus_bounded_job import run

STUDY = ROOT / 'artifacts/daedalus-component-mesh-20261114'


def inspect(folder, args):
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.discretization import report
    from openswing.geometry import geometry_summary, model_meshes

    model = parse_asw((ROOT / 'examples/dae.asw').read_text())
    cases = []
    for count in (16, 48):
        meshes = model_meshes(model, count)
        geometries = geometry_summary(model, meshes=meshes)
        reports = report(model, meshes, count)['beams']
        components = []
        for mesh, geometry, nodes in zip(meshes, geometries, reports):
            assert nodes['settings'] == dict(count=count, spacing='cosine')
            assert len(nodes['nodes']) == len(mesh.tm) + 1
            assert geometry['panels'] == len(mesh.tm)
            if mesh.beam.lifting:
                assert len(geometry['quads']) == len(geometry['streamwise_quads']) == len(mesh.tm)
            else:
                assert len(geometry['quads']) == 12 * len(mesh.tm)
            np.testing.assert_array_equal(np.array(geometry['axis'])[:, 0], mesh.r0)
            components.append(dict(beam=mesh.beam.index, name=mesh.beam.name,
                lifting=mesh.beam.lifting, requested_intervals=count,
                intervals=len(mesh.tm), unique_stations=len(nodes['nodes']),
                length_ft=float(sum(mesh.length)),
                smallest_interval_ft=float(min(mesh.length)),
                largest_interval_ft=float(max(mesh.length)),
                display_faces=len(geometry['quads']),
                nodes=nodes['nodes']))
        cases.append(dict(default_intervals_per_beam=count, components=components))
    write(folder / 'cases.json', cases)
    return dict(cases=[dict(default_intervals_per_beam=c['default_intervals_per_beam'],
        components=[{k:v for k,v in row.items() if k != 'nodes'} for row in c['components']])
        for c in cases],
        findings=[
            'The global default count is applied separately to every beam, not apportioned by span or chord.',
            'The public Daedalus fairing is a lifting plate in the input, with chord and dCLda tables; its lines are analysis strip boundaries.',
            'The nonlifting tailboom is drawn as a 12-sided tube at the analysis stations, adding circumference and longitudinal edges.',
            'These counts describe fresh imports with no per-beam overrides; saved projects can use different meshes.',
        ],
        qualification='No native GIF mesh count or node algorithm recovered. No solver, renderer or default changed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args = vars(parser.parse_args())
    inputs = list((ROOT / 'openswing').glob('*.py')) + [ROOT / p for p in (
        'examples/dae.asw', 'web/main.js', 'web/node-editor.js',
        'web/surface-faces.js', 'web/viewer.js', 'web/software-viewer.js',
        'reference/aswing_doc.txt', 'docs/validation/aswing-authoritative-sources.json',
        'reference/daedalus-rudder-animations-20261113/fast-rudder-frame0.png',
        'docs/validation/ISAE_STATUS.md')]
    run(STUDY, args['tag'], inputs, inspect, args, __file__)


if __name__ == '__main__':
    main()
