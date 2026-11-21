"""History comparisons require complete time ordering and converged states."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ffwt4_assessment',ROOT/'scripts/assess-isae-ffwt4-time.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def state(tick):
    return dict(time=.0149*tick,converged=True,residual=1e-10,
        restart=dict(accepted_method=dict(effective_order=1 if tick==1 else 2)),
        sensors=[dict(index=1,load_trace='left',moment_local=[.75,0.,0.])])


@pytest.mark.parametrize('tick',[0,1,20,21,199])
def test_only_first_physical_step_restarts_with_order_one(tick):
    assert audit.snapshot_value(state(tick),tick)==.75


@pytest.mark.parametrize('fault',['time','residual','nonfinite','converged','trace','duplicate','order'])
def test_invalid_saved_states_cannot_be_counted(fault):
    s=state(21)
    if fault=='time':s['time']+=.001
    if fault=='residual':s['residual']=1.01e-8
    if fault=='nonfinite':s['sensors'][0]['moment_local'][0]=float('nan')
    if fault=='converged':s['converged']=False
    if fault=='trace':s['sensors'][0]['load_trace']='right'
    if fault=='duplicate':s['sensors'].append(deepcopy(s['sensors'][0]))
    if fault=='order':s['restart']['accepted_method']['effective_order']=1
    with pytest.raises(ValueError):audit.snapshot_value(s,21)


def test_table_reader_retains_lexical_precision_and_rejects_dropped_rows(tmp_path):
    path=tmp_path/'table.txt'
    lines=[f'{i+1} {i*.0149:.5f} 0.732178' for i in range(200)]
    path.write_text('# i t Mc\n'+'\n'.join(lines)+'\n')
    rows=audit.native_rows(path)
    assert rows[0]['token']=='0.732178' and rows[0]['tolerance']==5e-7
    path.write_text('\n'.join(lines[:10]+lines[11:])+'\n')
    with pytest.raises(ValueError,match='gap or duplicate'):audit.native_rows(path)
