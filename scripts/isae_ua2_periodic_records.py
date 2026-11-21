"""Map saved UA-2 intervals to bounded jobs without changing physical time grids."""
import json
from isae_ua2_incidence_periodic import grid, windows


def records(base, steps):
    path=base/'recovery-plan.json'
    if path.exists():
        result=json.loads(path.read_text())['records'][str(steps)]
    else:
        result=[dict(id=f'n{steps}-part{i:02d}',folder=f'n{steps}-part{i:02d}',
            receipt=f'n{steps}-part{i:02d}-execution.json',logical_part=i,
            start_index=a,end_index=b) for i,(a,b) in enumerate(windows(steps))]
    end=0
    for r in result:
        a,b=windows(steps)[r['logical_part']]
        assert r['start_index']==end
        assert a<=r['start_index']<r['end_index']<=b
        end=r['end_index']
    assert end==len(grid(steps))-1
    assert len({r['folder'] for r in result})==len(result)
    return result
