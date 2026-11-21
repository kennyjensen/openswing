"""Fresh full-state Daedalus response on the redistributed app mesh.

Assembly and response run as small, serial, resource-limited stages. Reuse the
checked assembly implementations, never the matrices from a different mesh.
"""
import argparse
from pathlib import Path
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, read
from daedalus_bounded_job import run
import check_daedalus_regular_mesh as regular

STUDY = ROOT/'artifacts/daedalus-regular-mesh-response-20261114'
SEED = regular.STUDY/'trim-1/state.json'
REFERENCE = ROOT/'docs/validation/daedalus-rudder-four-outputs.csv'


def configure():
    previous = regular.previous
    previous.source.imports()
    previous.setup = regular.setup
    previous.STUDY = STUDY
    previous.stages.setup = regular.setup
    previous.stages.dynamic = previous.dynamic
    previous.source.dynamic = previous.dynamic
    return previous


def execute(folder, arguments):
    args = SimpleNamespace(**arguments)
    args.seed = Path(args.seed)
    args.matrix = Path(args.matrix) if args.matrix else None
    args.parts = [Path(p) for p in args.parts or []]
    previous = configure()
    assert read(args.seed)['launch']['panels'] == read(regular.PRESET)
    if args.stage == 'geometry':
        return previous.stages.geometry(folder, args)
    if args.stage == 'geometry_join':
        return previous.stages.join_geometry(folder, args)
    if args.stage == 'response':
        return previous.response(folder, args)
    return previous.source.staged_linear(folder, args)


def inputs():
    return list((ROOT/'openswing').glob('*.py')) + [
        SEED, regular.PRESET, ROOT/'examples/dae.asw', ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'scripts/check_daedalus_regular_mesh.py',
        ROOT/'scripts/check_daedalus_default_mesh_response.py',
        ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'scripts/check_daedalus_structural_resolution.py',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['geometry', 'geometry_join', 'other',
                                        'mass', 'assemble', 'response'])
    parser.add_argument('--tag', required=True)
    parser.add_argument('--matrix')
    parser.add_argument('--parts', nargs='+')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--count', type=int, default=96)
    parser.add_argument('--step', type=float, default=1e-5)
    parser.add_argument('--frequencies', type=float, nargs='+',
                        default=[.1, 1.15737773741517, 1.5])
    args = vars(parser.parse_args())
    args.update(seed=str(SEED), speed=6.7)
    pinned = inputs()
    for part in (args['parts'] or []) + ([args['matrix']] if args['matrix'] else []):
        pinned.extend(p for p in Path(part).iterdir() if p.suffix in ('.npz', '.json'))
    if args['stage'] == 'response':
        pinned.append(STUDY/'mass/layout.json')
    run(STUDY, args['tag'], pinned, execute, args, __file__)


if __name__ == '__main__':
    main()
