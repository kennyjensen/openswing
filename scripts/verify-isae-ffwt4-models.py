"""Check literal FFWT-4 attachment domains and two small meshes, without solves."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from scripts.isae_ffwt4_evidence import pin, require, write

FAMILY = ('4 - Aeroelasticity/FFWT - Flared Folding Wingtips Cases/'
          'FFWT-4-U - Gust Alleviation of a Wing with and wo FFWT - Quantitative')


def inspect(path):
    model = parse_asw(path.read_text(), beam_interpolation='drela-segspl-v1')
    domains = {b.index: [float(v) for v in b.domain] for b in model.beams}
    attachments = []
    for kind, beam_column, station_column in (('weight', 0, 1), ('sensor', 1, 2)):
        for index, row in enumerate(model.records.get(kind, []), 1):
            beam, station = int(row[beam_column]), float(row[station_column])
            attachments.append(dict(kind=kind, record=index, beam=beam, station=station,
                domain=domains.get(beam), inside=beam in domains and domains[beam][0] <= station <= domains[beam][1]))
    for index, row in enumerate(model.records.get('joint', []), 1):
        for beam, station in ((int(row[0]), float(row[2])), (int(row[1]), float(row[3]))):
            attachments.append(dict(kind='joint', record=index, beam=beam, station=station,
                domain=domains.get(beam), inside=beam in domains and domains[beam][0] <= station <= domains[beam][1]))
    meshes = []
    for nominal in (8, 16):
        try:
            model_meshes(model, nominal)
        except ValueError as error:
            meshes.append(dict(nominal=nominal, status='rejected', error=str(error)))
        else:
            meshes.append(dict(nominal=nominal, status='meshed'))
    return dict(model=path.name, source=pin(path), beam_domains=domains,
                attachments=attachments, outside=[a for a in attachments if not a['inside']],
                diagnostics=model.diagnostics, meshes=meshes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Preserve earlier model audit')
    base = ROOT/'.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865'/FAMILY
    paths = sorted(base.glob('*.asw'))
    require(len(paths) == 9, 'Unexpected model inventory')
    kernels = [pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))]
    models = [inspect(path) for path in paths]
    require(kernels == [pin(p['path']) for p in kernels], 'Kernel changed during audit')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = dict(status='LITERAL_MODELS_INSPECTED', models=models, kernel_pins=kernels,
                  kernel_pins_unchanged=True, physical_solves=0, helper=pin(__file__),
                  full_family_validated=False,
                  qualification='Meshing is an OpenSwing compatibility check, not evidence of native ASWING rejection or full historical setup recovery.')
    write(args.output, result)
    print(json.dumps([dict(model=m['model'], outside=m['outside'], meshes=m['meshes']) for m in models]))


if __name__ == '__main__':
    main()
