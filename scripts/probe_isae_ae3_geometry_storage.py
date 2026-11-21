"""Isolated fix for retained dense geometry columns; exact equations unchanged."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae3_roll_control as run
from scripts.probe_isae_ae2_cold_trace import read,write,pin

OUT=ROOT/'artifacts/isae/ae3-geometry-storage-20261111'
BASE=ROOT/'artifacts/isae/ae3-rebuild-memory-20261111'
run.OUT=run.run.OUT=run.run.supervisor.OUT=OUT
run.run.supervisor.__file__=__file__

OLD_DECODE="""        def decode(value):
            if isinstance(value,Leaf):return values[value.start:value.stop].reshape(value.shape+(width,))
            if isinstance(value,dict):return {key:decode(item) for key,item in value.items()}
            if isinstance(value,tuple):return tuple(map(decode,value))
            if isinstance(value,list):return list(map(decode,value))
            return None
        self.applications+=1
        return decode(self.layout)
"""
NEW_DECODE="""        self.applications+=1
        return _decode_columns(self.layout,values,width)
"""
HELPER='''def _decode_columns(layout,values,width):
    """Return views without a recursive closure retaining the dense buffer.

    A per-call recursive function forms a function/cell cycle. Its captured
    values then survive ordinary reference release until cyclic collection,
    accumulating one dense block per geometry batch. Module-level recursion
    preserves the same views and releases storage when the last view is gone.
    """
    if isinstance(layout,Leaf):
        return values[layout.start:layout.stop].reshape(layout.shape+(width,))
    if isinstance(layout,dict):
        return {key:_decode_columns(item,values,width) for key,item in layout.items()}
    if isinstance(layout,tuple):
        return tuple(_decode_columns(item,values,width) for item in layout)
    if isinstance(layout,list):
        return [_decode_columns(item,values,width) for item in layout]
    return None


'''


def prepare():
    assert not OUT.exists()
    parent=read(BASE/'plan.json')
    for p in parent['pins']:assert pin(p['path'])==p,p['path']
    source=ROOT/'openswing/local_geometry_matrix.py';original=source.read_text()
    assert original.count(OLD_DECODE)==1 and original.count('def signature(g):')==1
    patched=original.replace(OLD_DECODE,NEW_DECODE).replace('def signature(g):',HELPER+'def signature(g):')
    code=OUT/'candidate'
    shutil.copytree(ROOT/'openswing',code/'openswing',ignore=shutil.ignore_patterns('__pycache__'))
    (code/'openswing/local_geometry_matrix.py').write_text(patched)
    # Preserve the original package for post-adoption source witnesses.
    shutil.copytree(ROOT/'openswing',OUT/'original/openswing',ignore=shutil.ignore_patterns('__pycache__'))
    paths={p['path'] for p in parent['pins']}
    paths.update(str(p) for p in (Path(__file__),BASE/'plan.json',
        ROOT/'tests/test_local_geometry_matrix.py',ROOT/'tests/test_geometry_partials.py',
        ROOT/'tests/test_direct_circulation.py',
        ROOT/'docs/validation/isae-ae3-roll-sweep-20261111.md',
        ROOT/'artifacts/isae/ae3-roll-sweep-20261111/assessment.json'))
    paths.update(str(p) for tree in (code,OUT/'original') for p in tree.rglob('*') if p.is_file())
    cases=[dict(name='lifetime-original',kind='pytest',candidate=False,selection='consumed_column_storage',expected_exit=1),
        dict(name='lifetime-candidate',kind='pytest',candidate=True,selection='consumed_column_storage',expected_exit=0),
        dict(name='columns-spatial',kind='pytest',candidate=True,selection='preserves_every_local_geometry_column and spatial',expected_exit=0),
        dict(name='columns-absolute',kind='pytest',candidate=True,selection='preserves_every_local_geometry_column and absolute',expected_exit=0),
        dict(name='field-cache-regressions',kind='pytest',candidate=True,
             selection='not preserves_every_local_geometry_column and not consumed_column_storage',expected_exit=0)]
    for previous in parent['cases']:
        case=deepcopy(previous);case['kind']='solve';case['candidate']=True
        case['name']=case['name'].replace('rebuild-','geometry-storage-')
        cases.append(case)
    write(OUT/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        cases=cases,pins=[pin(p) for p in sorted(paths)],limits=run.run.supervisor.LIMITS,
        candidate_root=str(code),constraint=parent['constraint'],control_change=parent['control_change'],
        qualifications=parent['qualifications'],parity_gate=2e-10,primary_votes_added=0,
        production_changes=False,method=__doc__,changed_module='local_geometry_matrix.py',
        previous_goal_turn='Progress: completed qualified six-speed/two-mesh sweep; identified repeatable geometry allocation failure. Releasing obsolete Newton storage was insufficient and not adopted.',
        hypothesis='Recursive local decoder closure retains each dense temporary until cyclic garbage collection; module-level recursion retains identical views without this cycle.',
        original_module=pin(source),candidate_module=pin(code/'openswing/local_geometry_matrix.py')))
    print('Prepared two lifetime checks, three regression groups, and two bounded AE-3 solves.')


def worker(name):
    plan=read(OUT/'plan.json');case=next(c for c in plan['cases'] if c['name']==name)
    if case['candidate']:sys.path.insert(0,plan['candidate_root'])
    import openswing
    expected=Path(plan['candidate_root'])/'openswing' if case['candidate'] else ROOT/'openswing'
    assert Path(openswing.__file__).resolve().parent==expected
    if case['kind']=='pytest':
        import pytest
        folder=OUT/'cases'/name
        sys.exit(pytest.main([str(ROOT/'tests/test_local_geometry_matrix.py'),'-q','-k',case['selection'],
            '--junitxml='+str(folder/'tests.xml'),'-p','no:cacheprovider']))
    # The previous candidate's worker has the same physical and state-parity
    # checks; override its module search path and output root explicitly.
    from scripts import probe_isae_ae3_rebuild_memory as checked
    checked.OUT=OUT
    checked.run.OUT=checked.run.run.OUT=checked.run.run.supervisor.OUT=OUT
    checked.worker(name)


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='launch':run.run.supervisor.launch(sys.argv[2])
    elif sys.argv[1]=='worker':worker(sys.argv[2])
    else:raise ValueError(sys.argv[1])
