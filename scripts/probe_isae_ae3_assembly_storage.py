"""Release consumed geometry workspaces before exact sparse concatenation."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae3_roll_control as run
from scripts.probe_isae_ae2_cold_trace import read,write,pin

OUT=ROOT/'artifacts/isae/ae3-assembly-storage-20261111'
BASE=ROOT/'artifacts/isae/ae3-geometry-storage-20261111'
run.OUT=run.run.OUT=run.run.supervisor.OUT=OUT
run.run.supervisor.__file__=__file__


def patch(original):
    start=original.index("    result = hstack(columns, format='csc')\n")
    report=original.index('    return result, dict(method=',start)
    # Snapshot scalar diagnostics, then discard only local references to the
    # consumed derivative workspaces. Published fields/column views stay owned
    # by their caller. Concatenation and every physical equation are unchanged.
    diagnostics=original[report:].replace('    return result, dict(method=', '    diagnostics = dict(method=',1)
    release='''    # Field derivatives are complete. Their geometry/maps and the last dense
    # batch are no longer needed while hstack allocates the full sparse block.
    # Drop local references only: captured base fields and caller-retained
    # output columns remain valid. No cache shared with the network is cleared.
    direct_geometry = stencil = evaluator = None
    base_geometry = base_fields = gradients = direct = values = derivative = gradient = None
'''
    return original[:start]+diagnostics+release+original[start:report]+'    return result, diagnostics\n'


def prepare():
    assert not OUT.exists()
    parent=read(BASE/'plan.json');adoption=read(BASE/'adoption.json')
    # Old source identity remains witnessed by the preserved original, not
    # relabelled as the subsequently adopted decoder.
    for p in parent['pins']:
        witness=adoption['historical_source_witness'] if p==adoption['before'] else p
        assert pin(witness['path'])['sha256']==p['sha256'],p['path']
    for p in adoption['production_matches_tested_candidate']:
        assert pin(p['path'])==p,p['path']
    for tree in ('original','candidate'):
        shutil.copytree(ROOT/'openswing',OUT/tree/'openswing',ignore=shutil.ignore_patterns('__pycache__'))
    source=ROOT/'openswing/geometry_tangent.py'
    (OUT/'candidate/openswing/geometry_tangent.py').write_text(patch(source.read_text()))
    paths={p['path'] for p in parent['pins']}
    paths.update(str(p) for p in (Path(__file__),BASE/'plan.json',BASE/'adoption.json',BASE/'assessment.json',
        ROOT/'tests/test_geometry_assembly_storage.py',ROOT/'tests/test_direct_geometry_matrix.py',
        ROOT/'tests/test_newton_geometry_composition.py',ROOT/'tests/test_direct_circulation.py'))
    paths.update(str(p) for tree in ('original','candidate') for p in (OUT/tree).rglob('*') if p.is_file())
    cases=[dict(name='lifetime-original',kind='pytest',candidate=False,
                test='test_geometry_assembly_storage.py',selection='',expected_exit=1),
           dict(name='lifetime-candidate',kind='pytest',candidate=True,
                test='test_geometry_assembly_storage.py',selection='',expected_exit=0)]
    for name,selection in [('matrix-wing','complete_geometry and (rectangular or flexible or torsion)'),
                           ('matrix-body','complete_geometry and (wing-body or stepped-body)'),
                           ('matrix-jet','complete_geometry and jet'),
                           ('matrix-steady','steady_chart'),
                           ('matrix-fallback','unavailable_composition')]:
        cases.append(dict(name=name,kind='pytest',candidate=True,test='test_direct_geometry_matrix.py',
                          selection=selection,expected_exit=0))
    cases.append(dict(name='newton-fallback',kind='pytest',candidate=True,
                      test='test_newton_geometry_composition.py',selection='unavailable_composition',expected_exit=0))
    for previous in parent['cases']:
        if previous['kind']!='solve':continue
        case=deepcopy(previous);case['name']=case['name'].replace('geometry-storage-','assembly-storage-')
        cases.append(case)
    write(OUT/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=cases,
        pins=[pin(p) for p in sorted(paths)],limits=run.run.supervisor.LIMITS,
        candidate_root=str(OUT/'candidate'),original_root=str(OUT/'original'),
        constraint=parent['constraint'],control_change=parent['control_change'],qualifications=parent['qualifications'],
        parity_gate=parent['parity_gate'],primary_votes_added=0,production_changes=False,
        method=__doc__,changed_module='geometry_tangent.py',
        original_module=pin(source),candidate_module=pin(OUT/'candidate/openswing/geometry_tangent.py')))
    print('Prepared isolated assembly-lifetime checks, matrix regressions and two serial AE-3 solves.')


def worker(name):
    plan=read(OUT/'plan.json');case=next(c for c in plan['cases'] if c['name']==name)
    root=Path(plan['candidate_root'] if case['candidate'] else plan['original_root'])
    sys.path.insert(0,str(root))
    import openswing
    assert Path(openswing.__file__).resolve().parent==root/'openswing'
    if case['kind']=='pytest':
        import pytest
        folder=OUT/'cases'/name
        sys.exit(pytest.main([str(ROOT/'tests'/case['test']),'-q','-k',case['selection'],
            '--junitxml='+str(folder/'tests.xml'),'-p','no:cacheprovider']))
    from scripts import probe_isae_ae3_rebuild_memory as checked
    checked.OUT=OUT
    checked.run.OUT=checked.run.run.OUT=checked.run.run.supervisor.OUT=OUT
    checked.worker(name)


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='launch':run.run.supervisor.launch(sys.argv[2])
    elif sys.argv[1]=='worker':worker(sys.argv[2])
    else:raise ValueError(sys.argv[1])
