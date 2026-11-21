"""Check the ST-4 energy reference against continuous transfer solutions."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from isae_st4_transfer import frequencies
from isae_st4_reference import GJ, LENGTH, EA_X

ROOT = Path(__file__).resolve().parents[1]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    a = p.parse_args()
    report = a.work / 'st4-reference.json'
    data = json.loads(report.read_text())
    expected = np.array([1, 3, 5]) * np.sqrt(GJ / .0078) / (4 * LENGTH)
    torsion = frequencies([], .0078, expected, cg_x=EA_X)
    np.testing.assert_allclose(torsion['frequencies_Hz'], expected, rtol=2e-12, atol=2e-12)
    rows = []
    for run in data['runs']:
        if run['elements'] != 256:
            continue
        path = ROOT / run['cache']
        assert sha(path) == run['sha256']
        reference = json.loads(path.read_text())
        inputs = reference['identity']
        fe = np.array(reference['result']['frequencies_Hz'])
        result = frequencies(inputs['points'], inputs['rotary'], fe)
        rows.append(dict(source_sha256=run['source_sha256'], source=run['source'],
                         **result, energy_reference_relative_errors=(fe / result['frequencies_Hz'] - 1).tolist()))
        print(len(rows), Path(run['source']).name, max(abs(np.array(rows[-1]['energy_reference_relative_errors']))), flush=True)
    out = dict(status='PASS_CONTINUOUS_TRANSFER_REFERENCE', script_sha256=sha(__file__),
               reference_sha256=sha(ROOT / 'scripts/isae_st4_transfer.py'),
               energy_reference_sha256=sha(report), closed_form_torsion=dict(expected_Hz=expected.tolist(), **torsion),
               rows=rows, full_physical_validation=False)
    (a.work / 'transfer.json').write_text(json.dumps(out, indent=2) + '\n')


if __name__ == '__main__':
    main()
