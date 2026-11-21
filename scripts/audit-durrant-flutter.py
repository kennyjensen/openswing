"""Audit the archived loaded-wing computations and nine refined sign brackets.

Reads exact evidence objects without extracting or executing archive members.
This proves scoped numerical outcomes, not experimental or ASWING parity.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MATCHER = ROOT/'scripts/analyze-durrant-flutter.py'
MATCH = runpy.run_path(str(MATCHER))['match']


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--kernel-root',type=Path,help='Optional historical checkout to compare with archived kernel sources.')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a fresh audit output path.')
    kernel = None
    if args.kernel_root is not None:
        kernel = {str(p.relative_to(args.kernel_root)):digest(p.read_bytes())
                  for p in sorted((args.kernel_root/'openswing').glob('*.py'))}
        if len(kernel) != 58:
            raise ValueError('Expected the recorded 58-module historical kernel.')
    fixed_count = boundary_count = 0
    max_base = max_pencil = 0.
    resolved = {}
    with zipfile.ZipFile(args.archive) as archive:
        if archive.testzip() is not None:
            raise ValueError('Archive CRC failure.')
        index = json.loads(archive.read('index.json'))
        if index['schema'] != 1 or len(index['runs']) != 9:
            raise ValueError('Unexpected evidence archive schema or run set.')
        for original,item in index['files'].items():
            raw = archive.read(item['member'])
            if len(raw) != item['size'] or digest(raw) != item['sha256']:
                raise ValueError('Changed archived bytes: '+original)
        def read(original):
            return archive.read(index['files'][str(original)]['member'])
        def data(original):
            return json.loads(read(original))
        original_run = next(run for run in index['runs'] if run['name']=='boundary')
        expected = data(original_run['plan'])['boundaries']
        key = lambda spec:(spec['wing'],spec['panels'],spec['transition'])
        for run in index['runs']:
            manifest = data(run['manifest'])
            numerical = {k:v for k,v in manifest['source_sha256'].items() if k.startswith('openswing/')}
            if kernel is None:
                kernel = numerical
                if len(kernel) != 58:
                    raise ValueError('Expected the recorded 58-module historical kernel.')
            if numerical != kernel:
                raise ValueError('Archived kernel differs from the explicit checkout.')
            for relative,wanted in manifest['source_sha256'].items():
                if digest(read(run['sources'][relative])) != wanted:
                    raise ValueError('Archived study source differs: '+relative)
            is_boundary = run['name'].startswith('boundary')
            if is_boundary and manifest['source_sha256']['scripts/analyze-durrant-flutter.py'] != digest(MATCHER.read_bytes()):
                raise ValueError('Mode matcher changed since the boundary study.')
            directory = Path(run['manifest']).parent
            cases = {}
            if len(manifest['cases']) != len(run['cases']):
                raise ValueError('Archive case membership differs.')
            for entry in manifest['cases']:
                path = directory/entry['file']
                if str(path) not in run['cases'] or digest(read(path)) != entry['sha256']:
                    raise ValueError('Case membership/hash mismatch.')
                case = data(path)
                assert case['status']=='computed' and case['base']['converged']
                residual = case['base']['residual']
                assert math.isfinite(residual) and residual<1e-7
                max_base = max(max_base,residual)
                assert len(case['searches'])==(2 if is_boundary else len(case['spec'].get('shifts',[[-.1,100.]])))
                for search in case['searches']:
                    for mode in search['modes']:
                        for field in ['left_backward_error','right_backward_error']:
                            value=mode[field]
                            assert math.isfinite(value) and value<1e-9
                            max_pencil=max(max_pencil,value)
                if 'reused_from' in case:
                    origin=case['reused_from']
                    assert digest(read(origin['path']))==origin['sha256']
                    old=data(origin['path'])
                    assert {k:v for k,v in case.items() if k!='reused_from'}=={k:v for k,v in old.items() if k!='reused_from'}
                cases[entry['file']]=case
            if not is_boundary:
                assert manifest['status']=='computed' and 'ended' in manifest
                assert [case['spec'] for case in cases.values()]==manifest['plan']['cases']
                terminal=data('/tmp/openswing-durrant-flutter-'+run['name']+'-20261009.status.json')
                assert terminal['exit_code']==0 and 'ended' in terminal
                fixed_count+=len(cases)
                continue
            boundary_count+=len(cases)
            if run['name']=='boundary-resume3':
                assert manifest['status']=='computed' and 'ended' in manifest
                terminal=data('/tmp/openswing-durrant-flutter-boundary-resume3-20261009.status.json')
                assert terminal['exit_code']==0 and 'ended' in terminal
            for boundary in manifest['boundaries']:
                if boundary['status']!='resolved':
                    continue
                spec=boundary['specification']
                def at(speed,target):
                    choices=[(name,case) for name,case in cases.items() if case['spec']['wing']==spec['wing'] and case['spec']['panels']==spec['panels'] and case['spec']['speed_m_s']==speed]
                    assert choices
                    name,case=choices[-1]
                    root=complex(*target)
                    for search in case['searches']:
                        assert min(abs(complex(*mode['eigenvalue_per_s'])-root) for mode in search['modes'])<1e-7*max(abs(root),1.)
                    return name,case
                lo,hi=boundary['bracket_m_s']
                left,right=[complex(*value) for value in boundary['endpoint_roots_per_s']]
                assert lo<hi and hi-lo<=1e-4*max(abs(lo),abs(hi))
                assert left.real*right.real<=0 and left.real!=right.real
                assert (left.real<right.real)==(spec['transition']=='destabilizing')
                _,lc=at(lo,boundary['endpoint_roots_per_s'][0])
                _,rc=at(hi,boundary['endpoint_roots_per_s'][1])
                pair=min(MATCH(lc,rc)['pairs'],key=lambda p:abs(complex(*p['before'])-left))
                assert abs(complex(*pair['before'])-left)<1e-9*max(1.,abs(left))
                assert abs(complex(*pair['after'])-right)<1e-9*max(1.,abs(right))
                assert pair['resolved'] and pair['modal_assurance']>.8 and pair['row_margin']>.1 and pair['column_margin']>.1
                value=complex(*boundary['best_root_per_s'])
                speed=boundary['best_speed_m_s']
                assert speed in [lo,hi] and abs(value.real)/max(1.,abs(value))<=1e-6
                name,_=at(speed,boundary['best_root_per_s'])
                assert name==boundary['best_file']
                result=dict(specification=spec,speed_m_s=speed,root_per_s=boundary['best_root_per_s'],frequency_Hz=value.imag/(2*math.pi),bracket_m_s=[lo,hi],normalized_growth=abs(value.real)/max(1.,abs(value)),endpoint_mode_match=pair)
                if key(spec) in resolved:
                    assert abs(resolved[key(spec)]['speed_m_s']-speed)<1e-4*speed
                resolved[key(spec)]=result
        assert set(resolved)=={key(spec) for spec in expected} and len(resolved)==9
        assert fixed_count==33 and boundary_count==88
    result=dict(status='passed',recorded=time.time(),archive_sha256=digest(args.archive.read_bytes()),
                auditor_sha256=digest(Path(__file__).read_bytes()),matcher_sha256=digest(MATCHER.read_bytes()),
                scope='Historical pre-apparent-rate-correction kernel; no current-kernel flutter claim.',
                external_checkout_verified=args.kernel_root is not None,
                kernel_sha256=kernel,fixed_cases=fixed_count,boundary_case_records=boundary_count,
                resolved_boundaries=len(resolved),boundaries=list(resolved.values()),
                maximum_base_residual=max_base,maximum_original_pencil_backward_error=max_pencil,
                limitations=['Case count includes cached duplicates; interrupted supervisors remain nonterminal.',
                             'No continuum error bound, full native-spectrum stability, exact original ASWING setup or experimental validation is established.',
                             'Browser and WASM outcomes have separate validation records.',
                             'The apparent-rate self-field correction changes these dynamics; this archive is historical.'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['kernel_sha256','boundaries']},indent=2))


if __name__=='__main__':
    main()
