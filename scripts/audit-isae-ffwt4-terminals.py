"""Check that a complete FFWT-4 continuation uses only successful process exits."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import json

from isae_ffwt4_evidence import pin, read, require, write


def assess(last_segment):
    folder = last_segment.resolve()
    root = folder.parent
    journal = root/'serial-terminal.json'
    journal_pin = pin(journal)
    jobs = read(journal)['jobs']
    receipts = {job['folder']: job for job in jobs}
    require(len(receipts) == len(jobs), 'Duplicate terminal receipt')
    chain, visited, inputs = [], set(), [journal_pin]
    while True:
        require(folder.parent == root and folder not in visited, 'Invalid continuation ancestry')
        visited.add(folder)
        plan = read(folder/'plan.json')
        report = read(folder/'report.json')
        receipt = receipts.get(folder.name)
        require(receipt is not None and receipt['exit_code'] == 0, 'No successful exit: '+folder.name)
        require(report['status'] == 'SEGMENT_COMPUTED', 'Incomplete segment report')
        start, end = plan['start_step'], plan['end_step']
        require(0 < end-start <= 20, 'Unbounded or empty segment')
        require((report['start_step'], report['end_step'], report['accepted_steps'], report['rejected_steps'])
                == (start, end, end-start, 0), 'Segment accounting differs')
        require(report['source_pins_unchanged'] and report['kernel_pins_unchanged'], 'Unverified source bytes')
        for key in ('request', 'result', 'checkpoint'):
            record = report[key]
            require(Path(record['path']).parent == folder, 'Segment output outside its folder')
            require(Path(record['path']).is_file() and Path(record['path']).stat().st_size == record['bytes'],
                    'Missing or truncated segment output')
        inputs += [pin(folder/'plan.json'), pin(folder/'report.json')]
        chain.append(dict(folder=folder.name, start_step=start, end_step=end,
                          divisor=plan['divisor'], accepted_steps=end-start, exit_code=0))
        if 'parent_checkpoint' not in plan:
            require(start == 0, 'Ancestry does not start at zero')
            break
        parent = Path(plan['parent_checkpoint']['path']).parent
        for key in ('parent_plan', 'parent_report', 'parent_checkpoint'):
            require(Path(plan[key]['path']).parent == parent and pin(plan[key]['path']) == plan[key],
                    'Changed parent evidence')
        folder = parent
    chain.reverse()
    divisor = chain[0]['divisor']
    require(divisor in (2, 4, 8), 'Unsupported refinement ratio')
    for i, segment in enumerate(chain):
        require(segment['divisor'] == divisor, 'Changed refinement ratio')
        require(segment['start_step'] == (chain[i-1]['end_step'] if i else 0), 'Gap in accepted steps')
    accepted = sum(s['accepted_steps'] for s in chain)
    require(accepted == chain[-1]['end_step'] == 199*divisor, 'Incomplete physical history')
    selected = {s['folder'] for s in chain}
    excluded = [dict(folder=j['folder'], exit_code=j['exit_code']) for j in jobs if j['folder'] not in selected]
    require(pin(journal) == journal_pin, 'Terminal journal changed during audit')
    return dict(status='COMPLETE_CHAIN_HAS_SUCCESSFUL_EXITS',
                observed_at=datetime.now(timezone.utc).isoformat(),
                selected_jobs=len(chain), attempted_jobs=len(jobs), excluded_attempts=excluded,
                accepted_steps=accepted, rejected_steps=0, chain=chain, inputs=inputs,
                helper=pin(__file__), evidence_helper=pin(Path(__file__).with_name('isae_ffwt4_evidence.py')),
                qualifications=[
                    'Exit codes are the retained subprocess return codes, not inferred from progress logs.',
                    'The separate full-history assessment authenticates and inspects every saved result.',
                    'Excluded attempts contribute no accepted steps and do not count as integrator rejections.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--last-segment', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Preserve previous audit')
    result = assess(args.last_segment)
    write(args.output, result)
    print(json.dumps({key: result[key] for key in ('status', 'selected_jobs', 'attempted_jobs',
                                                 'excluded_attempts', 'accepted_steps', 'rejected_steps')}))


if __name__ == '__main__':
    main()
