"""Sided endpoint load checks and cellwise circulation refinement diagnostics.

Internal forces and moments are compared at the same material station and
same side of any point-load jump, in the fixed body axes. Each beam/component
uses its own finer-grid scale. Circulation is a separate piecewise-constant
cell diagnostic, not a claim about values at shared collocation points.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def require(value,message):
    if not value:raise ValueError(message)


def finite_vector(value):
    require(len(value)==3 and all(math.isfinite(v) for v in value),'Invalid endpoint load vector')
    return value


def fields(result):
    require(result['converged'] and result['continuation_status']=='complete','Incomplete equilibrium')
    nodes={(n['beam'],n['t']):n for n in result['nodes']}
    require(len(nodes)==len(result['nodes']),'Duplicate node station')
    traces={};cells={};last={}
    elements=result['elements'];strips=result['strips']
    require(len(elements)==len(strips)>0,'Mismatched element/strip inventory')
    for element,strip in zip(elements,strips):
        beam=element['beam'];lo,hi=element['t0'],element['t1'];length=element['length']
        require(all(math.isfinite(v) for v in (lo,hi,length)) and lo<hi and length>0,'Invalid element interval')
        if beam in last:require(lo==last[beam],'Noncontiguous or overlapping beam intervals')
        last[beam]=hi
        require(len(element['endpoint_traces'])==2,'Missing sided endpoint trace')
        for trace,side,t in zip(element['endpoint_traces'],('right','left'),(lo,hi)):
            require(trace['side']==side and trace['t']==t,'Incorrect endpoint side or station')
            require((beam,t) in nodes and nodes[(beam,t)]['index']==trace['node'],'Endpoint/node mismatch')
            key=(beam,t,side);require(key not in traces,'Duplicate sided endpoint trace')
            traces[key]={name:finite_vector(trace[name]) for name in ('force','moment')}
        require(strip['beam']==beam and strip['lifting'] and lo<=strip['t']<=hi,'Unsupported or mismatched lifting strip')
        gamma=strip['circulation'];require(math.isfinite(gamma),'Nonfinite circulation')
        cells.setdefault(beam,[]).append(dict(lo=lo,hi=hi,length=length,gamma=gamma))
    return nodes,traces,cells


def compare(coarse,fine):
    cn,c,cc=fields(coarse);fn,f,fc=fields(fine)
    require(len(fn)>len(cn),'Expected finer mesh')
    require(set(cn)<=set(fn) and set(c)<=set(f),'Missing common node or sided trace')
    require(cc.keys()==fc.keys(),'Changed beam inventory')
    for key in cn:require(cn[key]['jig_position']==fn[key]['jig_position'],'Changed jig geometry')
    rows=[];flow=[]
    for beam in sorted(fc):
        shared=[key for key in c if key[0]==beam];all_fine=[key for key in f if key[0]==beam]
        for field in ('force','moment'):
            for axis,label in enumerate(('x','y','z')):
                scale=max(abs(f[key][field][axis]) for key in all_fine)
                delta=[abs(c[key][field][axis]-f[key][field][axis]) for key in shared]
                worst=max(range(len(shared)),key=delta.__getitem__);key=shared[worst]
                relative=None if scale==0 else delta[worst]/scale
                rows.append(dict(beam=beam,field=field,body_component=label,
                    shared_sided_traces=len(shared),fine_sided_traces=len(all_fine),
                    maximum_absolute_change=delta[worst],fine_scale=scale,
                    maximum_percent=None if relative is None else 100*relative,
                    relative_limit=.001,passed=relative is not None and relative<=.001,
                    worst_station=key[1],side=key[2],
                    units='input F' if field=='force' else 'input F L',
                    zero_scale_policy=None if scale else 'No relative accuracy claim without an independently declared absolute gate'))
        old,new=cc[beam],fc[beam]
        require((old[0]['lo'],old[-1]['hi'])==(new[0]['lo'],new[-1]['hi']),'Changed circulation domain')
        index=0;error=reference=measure=maximum=peak=0.
        for cell in old:
            sub=[]
            while index<len(new) and new[index]['lo']<cell['hi']:
                v=new[index];require(cell['lo']<=v['lo']<v['hi']<=cell['hi'],'Nonnested circulation cells')
                sub.append(v);index+=1
            require(bool(sub) and sub[0]['lo']==cell['lo'] and sub[-1]['hi']==cell['hi'],'Incomplete circulation-cell coverage')
            # Material interval measures must agree before using fine-cell
            # lengths as a shared quadrature. No geometry reparameterization.
            total=sum(v['length'] for v in sub)
            require(abs(total-cell['length'])<=1e-12*max(total,cell['length']),'Changed material interval measure')
            for v in sub:
                delta=abs(cell['gamma']-v['gamma']);w=v['length']
                error+=w*delta**2;reference+=w*v['gamma']**2;measure+=w
                maximum=max(maximum,delta);peak=max(peak,abs(v['gamma']))
        require(index==len(new),'Extra circulation cells')
        flow.append(dict(beam=beam,coarse_cells=len(old),fine_cells=len(new),
            material_measure=measure,rms_absolute_change=math.sqrt(error/measure),
            fine_rms=math.sqrt(reference/measure),maximum_absolute_change=maximum,fine_peak=peak,
            rms_relative_percent=None if reference==0 else 100*math.sqrt(error/reference),
            maximum_relative_percent=None if peak==0 else 100*maximum/peak,
            numerical_gate_assessed=False))
    return dict(checks=rows,passed=sum(r['passed'] for r in rows),required=len(rows),
        circulation_cell_diagnostics=flow,all_field_accuracy_established=False,native_values_added=0)


def pin(path):
    path=Path(path).resolve();data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--comparison',type=Path,required=True);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    base=json.loads(args.comparison.read_text());plan=json.loads(args.plan.read_text())
    require(base['status']=='SPATIAL_COMPARISON_COMPUTED','Missing complete mesh comparison')
    require(base['root_moment']['limit']==plan['relative_limit']==.001,'Changed accuracy gate')
    require(pin(__file__)==plan['comparator'],'Comparator changed after preregistration')
    for record in base['inputs']:require(pin(record['path'])==record,'Changed comparison evidence')
    paths=[Path(base['inputs'][i]['path']) for i in (3,4)]
    result=compare(*(json.loads(p.read_text()) for p in paths))
    result.update(status='PM2_SIDED_LOAD_FIELDS_ASSESSED',
        coarse_nodes=base['coarse_nodes'],fine_nodes=base['fine_nodes'],
        qualification='18 separate body-component endpoint load gates for three beams, with point-load jumps kept sided. Cellwise circulation diagnostics compare piecewise-constant representations, not shared collocation samples. No full field accuracy or native passes claimed.',
        inputs=[pin(args.comparison),pin(args.plan),pin(__file__)]+[pin(p) for p in paths])
    with args.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='inputs'}))


if __name__=='__main__':main()
