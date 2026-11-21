"""Audit a history and retain immutable process receipts for that assessment."""
import argparse
import importlib.util
import json
from pathlib import Path

from isae_ffwt4_evidence import pin, require, write

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT/'scripts/assess-isae-ffwt4-history-v3.py'
spec = importlib.util.spec_from_file_location('ffwt4_history_core', CORE)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--last-segment', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    journal = args.last_segment.resolve().parent/'serial-terminal.json'
    snapshot = args.output.with_suffix('.terminals.json')
    require(not args.output.exists() and not snapshot.exists(), 'Preserve previous assessment evidence')
    origin = pin(journal)
    raw = journal.read_bytes()
    core_pin = pin(CORE)
    result = core.assess(args.last_segment)
    require(result['terminal_journal'] == origin and pin(journal) == origin and pin(CORE) == core_pin,
            'Assessment inputs changed while capturing receipts')
    snapshot.write_bytes(raw)
    saved = pin(snapshot)
    require((saved['bytes'], saved['sha256']) == (origin['bytes'], origin['sha256']), 'Receipt snapshot differs')
    result['terminal_journal_origin'] = origin
    result['terminal_journal'] = saved
    result['core_helper'] = result['helper']
    result['inputs'].append(core_pin)
    result['helper'] = pin(__file__)
    result['qualifications'].append('The immutable receipt copy authenticates this frontier even when the live journal gains later jobs.')
    write(args.output, result)
    print(json.dumps({k: result[k] for k in ('complete','nominal','nodes','accepted_steps','required_steps',
        'rejected_steps','end_time','maximum_residual','summary','excluded_attempts')}), flush=True)


if __name__ == '__main__':
    main()
