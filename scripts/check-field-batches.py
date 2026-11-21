from pathlib import Path
from copy import deepcopy
import sys,json,time
r=Path('/tmp/openswing-batched-field-actions-20261013');sys.path[:0]=[str(r/'candidate-02'),'/home/userland/aswing/tests']
import numpy as np
from openswing.vortex_tangent import VortexSourceTangent,VortexFieldTangent
from openswing.volume_tangent import VolumeSourceTangent,VolumeFieldTangent
from test_shared_vortex_sources import fixture,query_core
from test_volume_tangent import field_fixture
differences=[];count=0;maximum=0.
def check(actual,expected,label):
    global count,maximum
    for a,b in zip(actual,expected,strict=True):
        count+=1
        error=float(np.max(abs(a-b)/(1+abs(b)),initial=0.));maximum=max(maximum,error)
        if a.tobytes()!=b.tobytes():differences.append(dict(label=label,error=error))
for flag in (-1,0,1):
    for kind in ['none','mixed','one','all','empty','single']:
        points,a,b,wind,pg,core,gamma,owners,physical,bound,ground=fixture(flag,kind)
        source=VortexSourceTangent(a,b,core,owners)
        tangent=VortexFieldTangent(points,a,b,wind,pg,query_core(core,owners,physical),gamma,ground,
            exclude_bound=bound,single_dot=kind=='single',_source=source,_physical=physical)
        rng=np.random.default_rng(342);dp,da,db,dc=[np.zeros_like(v) for v in (points,a,b,core)]
        for value in (dp,da,db,dc):value[::2]=rng.normal(size=value[::2].shape)*1e-4
        for variant in ['same','changed_support','base']:
            multipliers=(1,-1,2,-2) if variant=='same' else (1,0,2,-2) if variant=='changed_support' else (0,0,0,0)
            p=[points+k*dp for k in multipliers]
            changes=[source.difference(a+k*da,b+k*db,core+k*dc,owners) for k in multipliers]
            actual=tangent.values_shared(p,changes,[physical]*4)
            expected=[tangent.value_shared(q,c,physical) for q,c in zip(p,changes)]
            check(actual,expected,['vortex',flag,kind,variant])
    for exclusion in ['none','body','bodies','point','points','both']:
        volume,points=field_fixture(flag);options={}
        if exclusion in ('body','bodies','both'):options['exclude_body']=2 if exclusion=='body' else np.where(np.arange(len(points))%2,2,-1)
        if exclusion in ('point','points','both'):options['exclude_point']=0 if exclusion=='point' else np.where(np.arange(len(points))%2,0,-1)
        source=VolumeSourceTangent(volume);tangent=VolumeFieldTangent(volume,points,_source=source,**options)
        rng=np.random.default_rng(846);dp=np.zeros_like(points);dp[::2]=rng.normal(size=dp[::2].shape)*1e-4
        directions={}
        for name in ['positions','sources','doublets']:
            value=np.zeros_like(getattr(volume,name));value[::3]=rng.normal(size=value[::3].shape)*1e-4;directions[name]=value
        for variant in ['same','changed_support','base']:
            multipliers=(1,-1,2,-2) if variant=='same' else (1,0,2,-2) if variant=='changed_support' else (0,0,0,0)
            p=[points+k*dp for k in multipliers];volumes=[];changes=[]
            for k in multipliers:
                v=deepcopy(volume)
                for name,direction in directions.items():setattr(v,name,getattr(volume,name)+k*direction)
                volumes.append(v);changes.append(source.difference(v))
            actual=tangent.values_shared(volumes,p,changes)
            expected=[tangent.value(v,q,_change=c) for v,q,c in zip(volumes,p,changes)]
            check(actual,expected,['volume',flag,exclusion,variant])
report=dict(status='PASS' if not differences else 'NOT_EXACT',samples=count,max_normalized_error=maximum,differences=differences)
(r/'primitive-comparison.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],count,len(differences),maximum,flush=True)
