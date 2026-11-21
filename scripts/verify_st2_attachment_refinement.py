"""ST-2 attachment study with the public API's minimum four-interval beam.

The first plan and its two completed tip-load states remain untouched.
Its two-interval extension request was rejected before a physical solve.
"""
import argparse
from pathlib import Path

import verify_st2_attachment_interpretations as study

common = study.common
FIRST = study.ROOT/'artifacts/isae/st2-attachment-interpretations-20261109'


def prepare(out):
    plan = common.read(FIRST/'plan.json')
    common.authenticate(plan['pins'])
    out.mkdir()
    plan['observed_utc'] = common.utc()
    plan['supersedes'] = dict(plan=str((FIRST/'plan.json').relative_to(study.ROOT)),
        sha256=common.sha(FIRST/'plan.json'),
        reason='Two-interval extension rejected by the public API before solving; use four/eight intervals.')
    plan['pins'][Path(__file__).relative_to(study.ROOT).as_posix()] = common.sha(Path(__file__))
    plan['pins']['openswing/discretization.py'] = common.sha(study.ROOT/'openswing/discretization.py')
    for job in plan['jobs']:
        job['extension_intervals'] *= 2
    plan['protocol'] += ' Extension meshes use four/eight intervals, respecting the existing public API minimum.'
    common.write(out/'plan.json', plan)
    print('Prepared corrected four/eight-interval extension meshes; earlier evidence preserved.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','run','summarize'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--index',type=int)
    args=parser.parse_args();common.bounded()
    if args.action=='prepare':prepare(args.output)
    elif args.action=='run':study.run(args.output,args.index)
    else:study.summarize(args.output)


if __name__=='__main__':main()
