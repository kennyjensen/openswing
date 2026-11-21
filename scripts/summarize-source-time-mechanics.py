"""Publish retained derivative, timing and worker evidence without new solves."""
from hashlib import sha256
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua-time-source-mechanics-20261102'
PREP=ROOT/'artifacts/isae/ua1-stall-periodic-preparation-20261102'


def read(path):return json.loads(path.read_text())
def digest(path):return sha256(path.read_bytes()).hexdigest()


def main():
    before=read(BASE/'before/sha256.json')
    current={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'openswing').glob('*.py')}
    changed={name:dict(before=before[name],after=value) for name,value in current.items() if before[name]!=value}
    assert sorted(changed)==['openswing/mechanical_tangent.py','openswing/structured_time.py','openswing/time_integration.py']
    test_names=['load-tests','bdf-tests','fallback-tests','airflow-step-tests','airflow-continuation',
                'body-time','unchanged-guards','source-radau']
    tests={}
    for name in test_names:
        suite=ET.parse(BASE/(name+'.xml')).getroot().find('testsuite')
        assert int(suite.attrib['failures'])==int(suite.attrib['errors'])==0
        tests[name]=int(suite.attrib['tests'])
    assert sum(tests.values())==13
    benchmarks={mode:[] for mode in ('direct','differences')}
    for mode in benchmarks:
        for repeat in (1,2,3):
            folder=BASE/f'benchmark-{mode}-{repeat}'
            assert read(folder/'plan.json')['source_sha256']==current
            report=read(folder/'report.json');assert report['passed']
            benchmarks[mode].append(report)
    medians={mode:statistics.median(r['seconds'] for r in rows) for mode,rows in benchmarks.items()}
    reduction=100*(1-medians['direct']/medians['differences'])
    browser=read(BASE/'browser/assessment.json');history=read(BASE/'browser/history-assessment.json')
    assert browser['passed'] and history['passed'] and browser['numerical_reexecution'] is False
    assert {'openswing/'+n:v for n,v in browser['module_sha256'].items()}==current
    reference={method:read(PREP/f'reference-{method}/trajectory.json') for method in ('DOP853','Radau')}
    agreement={}
    for key in ('CL','circulation','circulation_rate','CDp_fixed'):
        a,b=[r['rows'] for r in reference.values()]
        agreement[key]=max(abs(x[key]-y[key]) for x,y in zip(a,b))/max(abs(y[key]) for y in b)
    assert max(agreement.values())<1e-9
    source_paths=[Path(__file__),ROOT/'scripts/benchmark-source-time-mechanics.py',
        ROOT/'scripts/diagnose-isae-ua1-stall-periodic.py',ROOT/'scripts/isae_time_browser_compare.mjs',
        ROOT/'scripts/test-source-time-mechanics-browser.mjs',ROOT/'scripts/assess-source-time-mechanics-browser.mjs',
        ROOT/'tests/test_source_time_mechanical_tangent.py',ROOT/'tests/source-time-browser-join.test.mjs',
        ROOT/'.reference/asw_theory.txt']
    inputs=[BASE/(name+'.xml') for name in test_names]
    inputs += [BASE/'browser'/n for n in ['plan.json','assessment.json','history-assessment.json','original-execution.json']]
    for mode in benchmarks:
        for repeat in (1,2,3):inputs += [BASE/f'benchmark-{mode}-{repeat}'/n for n in ['plan.json','report.json']]
    for method in reference:inputs += [PREP/f'reference-{method}'/n for n in ['plan.json','trajectory.json','report.json']]
    result=dict(passed=True,scientific_modules=136,changed_modules=changed,source_sha256=current,
        report_source_sha256={str(p.relative_to(ROOT)):digest(p) for p in source_paths},
        input_sha256={str(p.relative_to(ROOT)):digest(p) for p in inputs},python_tests=tests,
        join_tests_passed=4,benchmarks=benchmarks,median_seconds=medians,median_reduction_percent=reduction,
        browser=browser,browser_history=history,periodic_reference_agreement=agreement,
        production_periodic_stall_validated=False,native_ASWING_comparison=False,registered_pass_count_change=0)
    document=ROOT/'docs/validation/isae-ua-source-mechanics-20261102.md'
    document.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    text=document.read_text().replace('At fixed endpoint geometry, the source constitutive equations are linear in',
        "[Drela's steady description, Eqs. 18–20](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf) "
        'defines the section load law used here. At fixed endpoint geometry, it is linear in')
    text=text.replace('The built-worker check is pending. It will continue the stalled history for\n'
        'two eight-step requests from a retained CPython checkpoint. This checks the\n'
        'new matrix assembly in WASM; it does not establish a new complete browser\n'
        'case or cold-start comparison.',
        'The actual built worker completed **16 steps / 17 unique states**, with no rejected steps. '
        f'The maximum scaled retained-Python difference is **{browser["maxDifference"]:.4e}**, below 2e-8. '
        'Both continuation boundaries preserve the physical BDF predecessors. This starts from a retained '
        'CPython checkpoint; it does not establish a new complete browser case or a cold-start comparison.\n\n'
        'The original verifier exited 1 after the second successful solve because its deep equality check '
        'distinguished `-0` from `0` in an Euler angle. Both complete outputs and the failed driver are retained. '
        'A separate reader accepts signed zeros as equal finite physical values and keeps exact equality '
        'for every nonzero join value. Four focused reader tests pass. The reassessment performs no new solve '
        'and changes no physical accuracy limit.')
    document.write_text(text+'\n[Machine-readable report](isae-ua-source-mechanics-20261102.json).\n')
    note=('The [source time-matrix improvement](docs/validation/isae-ua-source-mechanics-20261102.md) '
        'uses exact endpoint-average derivatives for internal loads and reactions. All **13 Python tests** '
        'and **4 browser-reader tests** pass. A retained 40-step stalled segment uses 450 rather than 612 '
        f'matrix-building residual evaluations; median solve time falls **{reduction:.1f}%** across three paired runs. '
        'The built worker passes a 16-step continuation comparison after correcting a retained signed-zero '
        'verifier failure; maximum scaled Python difference is **1.57e-9**. Physical equations and tolerances '
        'are unchanged. Scientific case counts are unchanged; the four-cycle stalled periodic comparison remains pending.')
    status=ROOT/'docs/validation/ISAE_STATUS.md';old=status.read_text()
    rows=lambda text:[r for r in text.splitlines() if r.startswith('| [')]
    assert rows(old)==rows((BASE/'before/ISAE_STATUS.md').read_text()) and len(rows(old))==42
    status.write_text(old.replace('Current priority is [UA-1 and UA-2]',note+'\n\nCurrent priority is [UA-1 and UA-2]',1))
    assert rows(status.read_text())==rows(old)
    path=ROOT/'docs/STATUS.md';lines=path.read_text().splitlines()
    lines[2:2]=[note.replace('](docs/validation/','](validation/'),''];path.write_text('\n'.join(lines)+'\n')
    path=ROOT/'docs/validation/isae-suite-backlog.md';text=path.read_text()
    row=next(r for r in text.splitlines() if '| **UA-1** |' in r)
    path.write_text(text.replace(row,row.removesuffix(' |')+' '+note.replace('](docs/validation/','](')+' |'))
    print(json.dumps(dict(passed=True,python_tests=13,join_tests=4,median_reduction_percent=reduction,
        preserved_ISAE_rows=42,periodic_reference_agreement=agreement)),flush=True)


if __name__=='__main__':main()
