"""Rescore retained ISAE results without rerunning physics or rewriting evidence.

Historical kernels and conditional scopes remain distinct. This is a new
acceptance view of saved predictions, never a claim of a current-source run.
Large suite reports are decoded one job at a time for modest memory use.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.isae_acceptance import apply_reference_acceptance, reference_acceptance_policy, DEFAULT_RELATIVE_TOLERANCE

spec = importlib.util.spec_from_file_location('isae_summary', ROOT/'scripts/summarize-isae-suite.py')
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def pin(path):
    with Path(path).open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(Path(path).resolve()), bytes=Path(path).stat().st_size, sha256=digest)


class JsonStream:
    def __init__(self, stream):
        self.stream, self.buffer, self.eof = stream, '', False
        self.decoder = json.JSONDecoder()

    def more(self):
        chunk = self.stream.read(65536)
        self.buffer += chunk
        self.eof = not chunk

    def peek(self):
        while True:
            self.buffer = self.buffer.lstrip()
            if self.buffer:
                return self.buffer[0]
            if self.eof:
                raise ValueError('Unexpected end of JSON')
            self.more()

    def take(self, token):
        if self.peek() != token:
            raise ValueError('Expected JSON token '+token)
        self.buffer = self.buffer[1:]

    def value(self):
        self.peek()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer)
                if end == len(self.buffer) and not self.eof:
                    self.more()
                    continue
                self.buffer = self.buffer[end:]
                return value
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self.more()


def report_items(path):
    with Path(path).open() as stream:
        p = JsonStream(stream)
        p.take('{')
        while p.peek() != '}':
            key = p.value()
            p.take(':')
            if key == 'jobs':
                p.take('[')
                while p.peek() != ']':
                    yield 'job', p.value()
                    if p.peek() != ']':
                        p.take(',')
                p.take(']')
            else:
                yield key, p.value()
            if p.peek() != '}':
                p.take(',')
        p.take('}')
        if p.buffer.strip() or stream.read().strip():
            raise ValueError('Trailing report JSON')


def assessment_items(path, plan_path):
    plan = json.loads(Path(plan_path).read_text())
    saved = json.loads(Path(path).read_text())
    assert set(saved['jobs']) == {j['id'] for j in plan['jobs']}
    yield 'code_sha256', plan['code_sha256']
    for job in plan['jobs']:
        yield 'job', dict(job, result=saved['jobs'][job['id']])


def directory_items(plan_path, cases, pins):
    """Read selected original job files instead of a large combined report."""
    plan=json.loads(Path(plan_path).read_text())
    yield 'code_sha256',plan['code_sha256']
    for job in plan['jobs']:
        if cases and job['case_id'] not in cases:
            continue
        key=hashlib.sha256(job['id'].encode()).hexdigest()[:20]
        path=Path(plan_path).parent/'jobs'/key/'result.json'
        if path.exists():
            before=pin(path)
            result=json.loads(path.read_text())
            assert result.get('job_id',result.get('id'))==job['id']
            assert pin(path)==before
            pins.append(before)
        else:
            result=None
        yield 'job',dict(job,result=result)


def score(items, relative_tolerance=DEFAULT_RELATIVE_TOLERANCE, cases=()):
    policy = reference_acceptance_policy(relative_tolerance=relative_tolerance)
    groups, metadata, seen = {}, {}, set()
    for key, value in items:
        if key != 'job':
            if key in ('code_sha256', 'runtime', 'revision', 'reference_acceptance', 'current_code_unchanged'):
                metadata[key] = value
            continue
        if cases and value['case_id'] not in cases:
            continue
        assert value['id'] not in seen, 'Duplicate job ID'
        seen.add(value['id'])
        # This independently verifies the saved policy view, strict reference
        # contract, numerical validity and full required-output accounting.
        summary.scalar_counts(value)
        strict_job = summary.strict_policy_job(value)
        counts = summary.scalar_counts(strict_job)
        scope = value.get('comparison_scope') or 'default'
        label = (value['case_id'], scope)
        g = groups.setdefault(label, dict(case_id=label[0], scope=scope, counts=Counter(),
            statuses=Counter(), failed_errors=defaultdict(list), jobs=[]))
        result = strict_job.get('result')
        if result:
            view = apply_reference_acceptance(result, relative_tolerance=relative_tolerance)
            valid = summary.numerically_valid(result)
            passed = sum(c.get('passed') is True for c in view.get('reference_checks', [])) if valid else 0
            assert passed >= counts['passed']
            g['statuses'][result.get('status', 'unknown')] += 1
            errors = []
            for c in view.get('reference_checks', []):
                error = c.get('relative_error')
                if valid and not c.get('passed') and error is not None and abs(c['expected']) > policy['tiny_reference']:
                    channel = c['name'].split(':')[-1]
                    g['failed_errors'][channel].append(100*error)
                    errors.append(dict(name=c['name'], percent=100*error))
        else:
            passed = 0
            errors = []
            g['statuses']['unrun'] += 1
        g['counts'].update(counts)
        g['counts']['accepted'] += passed
        g['jobs'].append(dict(id=value['id'], strict_passed=counts['passed'], accepted=passed,
            required=counts['required'], numerically_valid_finite=counts['numerically_valid_finite'],
            failed_relative_errors=errors))
    assert seen, 'No selected jobs'
    rows=[]
    for g in groups.values():
        g['counts']=dict(g['counts'])
        g['statuses']=dict(g['statuses'])
        g['failed_errors']={k:dict(count=len(v),median_percent=statistics.median(v),maximum_percent=max(v))
                            for k,v in g['failed_errors'].items()}
        rows.append(g)
    return dict(status='RESCORED_SAVED_EVIDENCE', current_source_rerun=False,
        physical_calls=0, reference_acceptance=policy, original_run_metadata=metadata,
        groups=rows, whole_family_validation=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--plan', type=Path, help='Use an assessment.json with its original plan')
    parser.add_argument('--job-results', action='store_true', help='Input is a plan.json; read its individual job results')
    parser.add_argument('--cases', nargs='+', default=[])
    parser.add_argument('--relative-tolerance', type=float, default=DEFAULT_RELATIVE_TOLERANCE)
    parser.add_argument('--output', required=True, type=Path)
    args=parser.parse_args()
    assert not args.output.exists(), 'Retain previous assessments; choose a new output'
    inputs=[args.input]+([args.plan] if args.plan else [])
    pins=[pin(p) for p in inputs]
    assert not (args.job_results and args.plan)
    result_pins=[]
    items=(directory_items(args.input,args.cases,result_pins) if args.job_results else
           assessment_items(args.input,args.plan) if args.plan else report_items(args.input))
    data=score(items,args.relative_tolerance,args.cases)
    assert pins==[pin(p) for p in inputs], 'Evidence changed during rescore'
    data.update(inputs=pins, result_files=result_pins, scorer=pin(__file__), acceptance_helper=pin(ROOT/'scripts/isae_acceptance.py'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    for g in data['groups']:
        c=g['counts'];print(f"{g['case_id']} {g['scope']}: {c['accepted']}/{c['required']} at {args.relative_tolerance:.0%}; {c['passed']} strict",flush=True)


if __name__=='__main__':
    main()
