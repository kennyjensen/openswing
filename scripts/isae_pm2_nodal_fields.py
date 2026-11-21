"""Independent displacement and finite-rotation mesh checks for PM2 equilibria.

Compare exact shared stations without interpolation. Normalize separately on
each beam so large tip folding cannot hide an error in the flexible main wing.
These checks do not certify element load/circulation fields or time accuracy.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def require(value,message):
    if not value:raise ValueError(message)


def vector(value):
    require(len(value)==3 and all(math.isfinite(x) for x in value),'Invalid vector')
    return value


def norm(value):
    value=math.hypot(*vector(value))
    require(math.isfinite(value),'Nonfinite vector norm')
    return value


def distance(a,b):return norm([x-y for x,y in zip(vector(a),vector(b))])


IDENTITY=[[float(i==j) for j in range(3)] for i in range(3)]


def rotation(value):
    require(len(value)==3,'Invalid rotation shape')
    for row in value:vector(row)
    require(max(abs(sum(value[k][i]*value[k][j] for k in range(3))-(i==j))
                for i in range(3) for j in range(3))<1e-10,'Nonorthogonal rotation')
    a,b,c=value
    determinant=a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
    require(abs(determinant-1)<1e-10,'Improper rotation')
    return value


def angle(a,b):
    # ||Ra-Rb||_F = 2 sqrt(2) sin(theta/2), valid for finite SO(3) rotations.
    chord=math.sqrt(sum((a[i][j]-b[i][j])**2 for i in range(3) for j in range(3)))
    return 2*math.asin(min(1.,chord/(2*math.sqrt(2.))))


def exponential(v):
    theta=norm(v)
    if theta==0:return IDENTITY
    x,y,z=[x/theta for x in v];k=[[0.,-z,y],[z,0.,-x],[-y,x,0.]]
    return [[IDENTITY[i][j]+math.sin(theta)*k[i][j]+(1-math.cos(theta))*sum(k[i][l]*k[l][j] for l in range(3))
             for j in range(3)] for i in range(3)]


def fields(result):
    require(result['converged'] and result['continuation_status']=='complete','Incomplete equilibrium')
    state=result['equilibrium_state'];nodes=result['nodes'];n=len(nodes)
    require(n>0 and len(state['positions'])==len(state['rotations'])==len(state['identity']['nodes'])==n,
            'Incomplete nodal state')
    output={}
    for i,node in enumerate(nodes):
        require(node['index']==i,'Incorrect node index')
        key=(node['beam'],node['t'])
        require(math.isfinite(key[1]) and key not in output,'Invalid or duplicate station')
        jig=vector(node['jig_position']);position=vector(node['position']);q=rotation(node['rotation'])
        require(jig==state['identity']['nodes'][i] and position==state['positions'][i],'Node/state mismatch')
        saved=exponential(vector(state['rotations'][i]))
        require(angle(q,saved)<1e-10,'Rotation/state mismatch')
        output[key]=dict(jig=jig,displacement=[x-y for x,y in zip(position,jig)],rotation=q)
    return output


def compare(coarse,fine):
    c,f=fields(coarse),fields(fine)
    require(len(f)>len(c),'Expected finer mesh')
    require(set(c)<=set(f),'Missing shared station')
    require({b for b,t in c}=={b for b,t in f},'Changed beam inventory')
    for key in c:require(c[key]['jig']==f[key]['jig'],'Changed jig geometry')
    rows=[]
    for beam in sorted({b for b,t in f}):
        shared=[key for key in c if key[0]==beam];all_fine=[key for key in f if key[0]==beam]
        for name in ('displacement','rotation'):
            if name=='displacement':
                scale=max(norm(f[key][name]) for key in all_fine)
                differences=[distance(c[key][name],f[key][name]) for key in shared]
            else:
                scale=max(angle(f[key][name],IDENTITY) for key in all_fine)
                differences=[angle(c[key][name],f[key][name]) for key in shared]
            require(scale>0,'Zero field scale cannot establish a relative mesh gate')
            worst=max(range(len(shared)),key=differences.__getitem__);delta=differences[worst]
            rows.append(dict(beam=beam,field=name,shared_nodes=len(shared),fine_nodes=len(all_fine),
                maximum_absolute_change=delta,fine_scale=scale,maximum_percent=100*delta/scale,
                relative_limit=.001,passed=delta<=.001*scale,worst_station=shared[worst][1],
                units='m' if name=='displacement' else 'rad'))
    return dict(checks=rows,passed=sum(row['passed'] for row in rows),required=len(rows),
                all_field_accuracy_established=False,native_values_added=0)


def pin(path):
    path=Path(path).resolve();data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();base=json.loads(args.comparison.read_text())
    require(base['status']=='SPATIAL_COMPARISON_COMPUTED','Missing completed mesh comparison')
    require(base['root_moment']['limit']==.001,'Changed mesh gate')
    for record in base['inputs']:require(pin(record['path'])==record,'Changed comparison evidence')
    # The existing mesh assessor binds both complete audited results here.
    paths=[Path(base['inputs'][i]['path']) for i in (3,4)]
    results=[json.loads(path.read_text()) for path in paths]
    require([len(r['nodes']) for r in results]==[base['coarse_nodes'],base['fine_nodes']],'Mesh identity changed')
    report=compare(*results)
    report.update(status='PM2_NODAL_FIELDS_ASSESSED',coarse_nodes=base['coarse_nodes'],fine_nodes=base['fine_nodes'],
        root_moment=base['root_moment'],inputs=[pin(args.comparison),pin(__file__)]+[pin(p) for p in paths],
        qualification='Per-beam displacement and finite-rotation mesh checks only; no element loads, circulation, gust-history accuracy or native matches are certified.')
    with args.output.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='inputs'}))


if __name__=='__main__':main()
