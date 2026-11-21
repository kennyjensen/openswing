"""Operating-point eigenvalue progression and checked instability brackets.

ASWING user guide, MODE / Flutter Analysis: solve a sequence of nonlinear
operating points, then inspect the progression of their frozen eigenvalues.
The matching/refinement algorithm here is an independent implementation.
"""
from collections import deque
from copy import deepcopy
from dataclasses import replace
import re
import numpy as np
from scipy.optimize import linear_sum_assignment
from .aero import AnalysisError
from .linear_dynamics import solve_modes


def physical_scales(result):
    """Undo changing solver scales before comparison in one fixed metric.

    Reactions share the force-scale ratio: mesh lengths do not change between
    points, so force versus moment factors cancel in the reference ratio.
    """
    d=result['diagnostics'];layout=d['state_layout'];out=np.ones(d['full_dimension'])
    for key,scales in [('node_coordinates',[layout['node_coordinates']['translation_scale']]*3+[1.]*3),
                       ('internal_loads',[layout['internal_loads']['force_scale']]*3+[layout['internal_loads']['moment_scale']]*3)]:
        block=layout[key];out[block['start']:block['start']+block['width']]=np.tile(scales,block['width']//6)
    for key,scale in [('reactions',layout['internal_loads']['force_scale']),('circulation',layout['circulation']['scale']),
                      ('local_velocity',layout['local_velocity']['scale']),('local_rates',layout['local_rates']['scale'])]:
        block=layout[key];out[block['start']:block['start']+block['width']]=scale
    block=layout['operating'];out[block['start']:block['start']+len(block['scales'])]=block['scales']
    block=layout['frame']
    if block['width']:out[block['start']:block['start']+block['width']]=np.repeat(block['scales'],3)
    block=layout['feedback']
    if block:out[block['start']:block['start']+len(block['scales'])]=block['scales']
    if not np.all(np.isfinite(out)) or np.any(out<=0):raise AnalysisError('Invalid modal coordinate scales for root tracking.')
    return out


def representatives(result,reference_scales,reference_rate=None):
    """Keep real roots and one member of each conjugate pair, never merge repeats."""
    scales=physical_scales(result)
    if scales.shape!=reference_scales.shape:raise AnalysisError('Descriptor layout changed during the sweep.')
    modes=result['modes'];roots=np.array([complex(*m['eigenvalue']) for m in modes]);out=[];used=set()
    for i,mode in enumerate(modes):
        if i in used:continue
        root=roots[i];v=(np.array(mode['right']['real'])+1j*np.array(mode['right']['imag']))*scales/reference_scales
        real=abs(root.imag)<=1e-9*max(abs(root),result['diagnostics']['time_scale']*1e-6)
        paired=None
        if not real:
            possible=[j for j in range(i+1,len(modes)) if j not in used and
                      abs(roots[j]-root.conjugate())<=1e-7*max(abs(root),np.finfo(float).tiny)]
            if possible:
                # Near repeated pairs use shape, not root ordering, to pair signs.
                paired=max(possible,key=lambda j:assurance(v.conj(),
                    (np.array(modes[j]['right']['real'])+1j*np.array(modes[j]['right']['imag']))*scales/reference_scales))
                used.add(paired)
            if root.imag<0:root,v=root.conjugate(),v.conj()
        else:root=complex(root.real,0.)
        norm=np.linalg.norm(v)
        if not np.isfinite(norm) or norm==0:raise AnalysisError('A root has no finite tracking vector.')
        out.append(dict(root=root,vector=v/norm,mode_index=i,conjugate_index=paired,real=real,
                        scale=max(abs(root),reference_rate or result['diagnostics']['time_scale']),
                        relaxation=mode.get('constitutive_relaxation',False)))
    return out


def assurance(a,b):
    denominator=np.vdot(a,a).real*np.vdot(b,b).real
    return float(np.clip(abs(np.vdot(a,b))**2/denominator,0.,1.)) if denominator>0 else 0.


def compare(a,b,prediction=None):
    mac=assurance(a['vector'],b['vector'])
    scale=max(abs(a['root']),abs(b['root']),a.get('scale',0.),b.get('scale',0.),np.finfo(float).tiny)
    distance=abs(b['root']-(a['root'] if prediction is None else prediction))/scale
    # Real/complex splitting is not an individually identifiable continuation.
    admissible=a['real']==b['real']
    return mac,float(distance),(.8*(1-mac)+.2*min(distance,4.)) if admissible else 4.


def match_roots(previous,current,*,predictions=None,min_assurance=.6,ambiguity_margin=.05,max_distance=1.):
    """One-to-one assignment with explicit births/deaths and ambiguity gaps."""
    n,k=len(previous),len(current)
    if not n or not k:return [],list(range(n)),list(range(k))
    entries=[[compare(a,b,None if predictions is None else predictions[i]) for b in current] for i,a in enumerate(previous)]
    cost=np.array([[e[2] for e in row] for row in entries])
    valid=np.array([[e[0]>=min_assurance and e[1]<=max_distance and previous[i]['real']==current[j]['real']
                    for j,e in enumerate(row)] for i,row in enumerate(entries)])
    # Dummies permit leaving a root unmatched instead of forcing a bad partner.
    padded=np.c_[np.where(valid,cost,4.),np.full((n,n),.9)]
    rows,cols=linear_sum_assignment(padded);matches=[];optimum=float(padded[rows,cols].sum())
    for i,j in zip(rows,cols):
        if j>=k or not valid[i,j]:continue
        # Assess the entire assignment. A nearby nonnormal mode can have
        # greater affinity to BOTH current roots; row/column runners-up alone
        # incorrectly reject a unique joint assignment in that situation.
        alternative=padded.copy();alternative[i,j]=4.
        rr,cc=linear_sum_assignment(alternative)
        gap=max(0.,float(alternative[rr,cc].sum())-optimum)
        margin=gap/max(gap+2*cost[i,j],np.finfo(float).eps)
        if gap<=64*np.finfo(float).eps*(1+abs(optimum)) or margin<ambiguity_margin:continue
        mac,distance,_=entries[i][j]
        matches.append(dict(previous=int(i),current=int(j),assurance=mac,distance=distance,margin=margin,assignment_cost_gap=gap))
    return matches,[i for i in range(n) if i not in {m['previous'] for m in matches}], [j for j in range(k) if j not in {m['current'] for m in matches}]


def trace_spectrum(evaluate,values,*,refine=True,min_assurance=.6,ambiguity_margin=.05,
                   max_distance=1.,parameter_rtol=1e-4,parameter_atol=0.,growth_tolerance=1e-6,
                   max_iterations=24,progress=None,adaptive=False,max_subdivisions=4,max_extra_points=16,
                   resample_after_subdivision=False):
    """Track an evaluator returning (representative roots, serializable point).

    All successful and failed evaluations are retained. Failed/ambiguous
    intervals are gaps; no stability or crossing is inferred across a gap.
    """
    values=np.asarray(values,dtype=float)
    if values.ndim!=1 or len(values)<2 or not np.all(np.isfinite(values)) or np.any(np.diff(values)<=0):
        raise AnalysisError('Sweep values must be at least two finite, strictly increasing numbers.')
    if not 0<min_assurance<=1 or not 0<=ambiguity_margin<1 or not np.isfinite(max_distance) or max_distance<=0:
        raise AnalysisError('Invalid root matching thresholds.')
    if not 0<parameter_rtol<.1 or not np.isfinite(parameter_atol) or parameter_atol<0 or not 0<growth_tolerance<.1:
        raise AnalysisError('Invalid boundary parameter or growth tolerances.')
    if not isinstance(max_iterations,int) or isinstance(max_iterations,bool) or not 1<=max_iterations<=60:
        raise AnalysisError('Boundary iteration limit must be an integer from 1 to 60.')
    if not isinstance(adaptive,bool):raise AnalysisError('Adaptive tracking must be true or false.')
    for name,limit,upper in [('subdivision depth',max_subdivisions,12),('extra point budget',max_extra_points,256)]:
        if not isinstance(limit,int) or isinstance(limit,bool) or not 0<=limit<=upper:
            raise AnalysisError(f'Adaptive {name} must be an integer from 0 to {upper}.')
    points=[];internals={};branches=[];gaps=[];boundaries=[];cache={};subdivisions=[];tracking_points=[]
    def sample(value,kind,retry=False):
        value=float(value)
        if value in cache and not retry:return cache[value]
        old_index=cache.get(value)
        if progress:progress('point',len(points)+1,len(values))
        index=len(points)
        try:
            roots,detail=evaluate(value)
            point=dict(index=index,value=value,kind=kind,converged=True,**detail)
        except (AnalysisError,ValueError) as exc:
            roots=[];point=dict(index=index,value=value,kind=kind,converged=False,error=str(exc))
        point['roots']=[dict(eigenvalue=[r['root'].real,r['root'].imag],mode_index=r['mode_index'],
            conjugate_index=r.get('conjugate_index'),relaxation=r.get('relaxation',False)) for r in roots]
        if old_index is not None:points[old_index]['superseded_by']=index
        points.append(point);internals[index]=roots;cache[value]=index
        return index
    def add(branch,point,root,match=None):
        branches[branch]['samples'].append(dict(point=point,root=root,match=match))
    previous=None;labels={};last_nonzero={};pending=[]
    queue=deque((float(v),'grid',0,False) for v in values)
    while queue:
        value,kind,depth,retry=queue.popleft()
        index=sample(value,kind,retry);roots=internals[index];next_labels={};matches=[];missing=[];new=[]
        both=previous is not None and points[previous]['converged'] and points[index]['converged']
        if both:
            predictions=[]
            for i,old in enumerate(internals[previous]):
                history=branches[labels[i]]['samples'];prediction=old['root']
                if len(history)>1:
                    earlier=history[-2];p=earlier['point'];r=internals[p][earlier['root']]['root']
                    prediction+=(old['root']-r)*(value-points[previous]['value'])/(points[previous]['value']-points[p]['value'])
                predictions.append(prediction)
            matches,missing,new=match_roots(internals[previous],roots,predictions=predictions,
                min_assurance=min_assurance,ambiguity_margin=ambiguity_margin,max_distance=max_distance)
        uncertain=previous is not None and points[previous]['converged'] and (not points[index]['converged'] or missing or new)
        if adaptive and uncertain and depth<max_subdivisions and len(subdivisions)<max_extra_points:
            left=points[previous]['value'];mid=left+(value-left)/2
            if left<mid<value:
                subdivisions.append(dict(left=previous,attempt=index,value=mid,depth=depth+1,
                    reason='assignment uncertainty' if both else 'equilibrium or eigenvalue failure'))
                queue.appendleft((value,kind,depth+1,resample_after_subdivision))
                queue.appendleft((mid,'adaptive',depth+1,False))
                continue
        tracking_points.append(index)
        if both:
            for match in matches:
                i,j=match['previous'],match['current'];branch=labels[i];next_labels[j]=branch;add(branch,index,j,match)
            if missing or new:gaps.append(dict(left=previous,right=index,lost=[labels[i] for i in missing],new_roots=new,
                reason='No unique admissible mode assignment. Refine the parameter grid, mode count or search shift.',
                adaptive_limit_reached=bool(adaptive and (depth>=max_subdivisions or len(subdivisions)>=max_extra_points))))
        elif previous is not None:
            gaps.append(dict(left=previous,right=index,lost=list(labels.values()),new_roots=list(range(len(roots))),reason='An operating-point or eigenvalue solve failed.',
                adaptive_limit_reached=bool(adaptive and uncertain and (depth>=max_subdivisions or len(subdivisions)>=max_extra_points))))
        for j,r in enumerate(roots):
            if j not in next_labels:
                branch=len(branches);branches.append(dict(index=branch,samples=[]));next_labels[j]=branch;add(branch,index,j)
            branch=next_labels[j];root=r['root'];scale=max(abs(root),r.get('scale',0.),np.finfo(float).tiny)
            sign=0 if abs(root.real)<=growth_tolerance*scale else int(np.sign(root.real))
            if sign:
                if branch in last_nonzero:
                    old_point,old_root,old_sign=last_nonzero[branch]
                    if sign!=old_sign:pending.append((branch,old_point,old_root,index,j,old_sign,sign))
                last_nonzero[branch]=(index,j,sign)
        previous=index;labels=next_labels

    def refine_boundary(item):
        branch,lp,li,rp,ri,before,after=item
        left,right=(lp,li),(rp,ri);trials=[];best=min((left,right),key=lambda pair:abs(internals[pair[0]][pair[1]]['root'].real))
        reason=None;resolved=False
        for iteration in range(max_iterations if refine else 0):
            best=min((left,right),key=lambda pair:abs(internals[pair[0]][pair[1]]['root'].real))
            l,r=points[left[0]]['value'],points[right[0]]['value']
            a,b=internals[left[0]][left[1]],internals[right[0]][right[1]]
            bestmode=internals[best[0]][best[1]];bestroot=bestmode['root']
            if r-l<=parameter_atol+parameter_rtol*max(abs(l),abs(r),np.finfo(float).tiny) and abs(bestroot.real)<=growth_tolerance*max(abs(bestroot),bestmode.get('scale',0.),np.finfo(float).tiny):
                resolved=True;break
            fraction=float(np.clip(-a['root'].real/(b['root'].real-a['root'].real),.1,.9))
            x=l+fraction*(r-l)
            if x==l or x==r:reason='Parameter precision exhausted.';break
            mid=sample(x,'refinement');trials.append(mid)
            if not points[mid]['converged']:reason=points[mid]['error'];break
            roots=internals[mid];prediction=a['root']+fraction*(b['root']-a['root'])
            scores=[]
            for j,candidate in enumerate(roots):
                ca,cb=compare(a,candidate,prediction),compare(b,candidate,prediction)
                valid=min(ca[0],cb[0])>=min_assurance and max(ca[1],cb[1])<=max_distance and a['real']==candidate['real']==b['real']
                scores.append((max(ca[2],cb[2]) if valid else 4.,j))
            scores.sort()
            separation=scores[1][0]-scores[0][0] if len(scores)>1 else float('inf')
            tied=bool(len(scores)>1 and separation<=64*np.finfo(float).eps*(1+abs(scores[0][0])))
            if not scores or scores[0][0]>=.9 or tied or separation<ambiguity_margin:
                reason='Boundary mode cannot be matched uniquely to both bracket endpoints.';break
            j=scores[0][1];c=roots[j];pair=(mid,j)
            if abs(c['root'].real)<abs(internals[best[0]][best[1]]['root'].real):best=pair
            if c['root'].real==0:
                left=right=best=pair;resolved=True;break
            if np.sign(c['root'].real)==np.sign(a['root'].real):left=pair
            else:right=pair
        best=min((left,right),key=lambda pair:abs(internals[pair[0]][pair[1]]['root'].real))
        l,r=points[left[0]]['value'],points[right[0]]['value'];bestmode=internals[best[0]][best[1]];root=bestmode['root']
        resolved=resolved or (refine and r-l<=parameter_atol+parameter_rtol*max(abs(l),abs(r),np.finfo(float).tiny) and
                             abs(root.real)<=growth_tolerance*max(abs(root),bestmode.get('scale',0.),np.finfo(float).tiny))
        return dict(branch=branch,direction='destabilizing' if after>before else 'stabilizing',
            kind='aperiodic instability' if internals[best[0]][best[1]]['real'] else 'oscillatory instability candidate',
            status='resolved' if resolved else 'unrefined' if not refine else 'unresolved',
            bracket=[l,r],value=points[best[0]]['value'],eigenvalue=[root.real,root.imag],
            point=best[0],root=best[1],endpoint_points=[left[0],right[0]],trials=trials,
            reason=None if resolved or not refine else reason or 'Iteration limit reached before both parameter and growth tolerances were met.')
    boundaries=[refine_boundary(item) for item in pending]
    return dict(points=points,branches=branches,gaps=gaps,boundaries=boundaries,tracking_points=tracking_points,subdivisions=subdivisions,
        converged=all(p['converged'] for p in points if 'superseded_by' not in p),tracking_complete=not gaps,
        refinement_complete=all(b['status']=='resolved' for b in boundaries) if refine else None,
        settings=dict(values=values.tolist(),refine=bool(refine),adaptive=adaptive,max_subdivisions=max_subdivisions,max_extra_points=max_extra_points,min_assurance=min_assurance,ambiguity_margin=ambiguity_margin,
            max_distance=max_distance,parameter_rtol=parameter_rtol,parameter_atol=parameter_atol,
            growth_tolerance=growth_tolerance,max_iterations=max_iterations))


def solve_stability(model,condition,panels=8,*,parameter='speed',values=(30.,40.,50.),modes=None,
                    progress=None,warm_start=False,initial_state=None,**options):
    """Solve the full nonlinear/modal model at each prescribed parameter value."""
    if condition is None:raise AnalysisError('An operating-condition definition is required for a stability sweep.')
    modal=deepcopy(modes or {});base={k:options.pop(k) for k in list(options) if k in
        ('gravity','loads','operating_constraints','strut_mode','controller','tolerance','continuation_steps')}
    if not isinstance(warm_start,bool):raise AnalysisError('Warm start must be true or false.')
    if 'initial_state' in modal:
        if initial_state is not None:raise AnalysisError('Supply the initial equilibrium only once.')
        initial_state=modal.pop('initial_state')
    seeds={}
    if 'controller' in modal:
        if 'controller' in base:raise AnalysisError('Supply the controller only once for a stability sweep.')
        base['controller']=modal.pop('controller')
    if modal.get('quiescent_density') is not None:
        raise AnalysisError('Quiescent fluid does not define a flight-condition stability sweep.')
    if modal.get('vacuum'):raise AnalysisError('Flight-condition stability sweeps currently require aerodynamic modes.')
    constraints=base.get('operating_constraints',())
    variable=lambda c:c['variable'] if isinstance(c,dict) else c.variable
    if parameter in [variable(c) for c in constraints]:raise AnalysisError('The sweep variable is also a trim unknown; sweep its target instead.')
    scalar_units=dict(speed='input L/T',alpha='deg',beta='deg',altitude_m='m',density='input F T^2/L^4')
    match=re.fullmatch(r'(control|power|target)\.(\d+)',parameter)
    if parameter in scalar_units:unit=scalar_units[parameter]
    elif match:
        group,index=match[1],int(match[2]);unit='target units (see operating constraint)' if group=='target' else 'file actuator setting'
        if group=='target' and index>=len(constraints):raise AnalysisError('Target index is zero-based and must refer to an operating constraint.')
        if group in ('control','power') and index not in (model.controls if group=='control' else model.engine_controls):
            raise AnalysisError('Sweep actuator is not declared by this aircraft.')
        if group in ('control','power') and base.get('controller') is not None:raise AnalysisError('Actuator sweeps with feedback require an explicit command/bias definition; sweep speed or a trim target instead.')
    else:raise AnalysisError('Sweep parameter must be speed, alpha, beta, altitude_m, density, control.N, power.N or target.N.')
    reference=None;reference_layout=None;reference_rate=None
    def evaluate(value):
        nonlocal reference,reference_layout,reference_rate
        local=deepcopy(base);current=deepcopy(condition)
        if parameter in scalar_units:current=replace(current,**{parameter:value})
        elif group=='target':
            rows=deepcopy(list(constraints));row=rows[index]
            if isinstance(row,dict):row['target']=value
            else:rows[index]=replace(row,target=value)
            local['operating_constraints']=rows
        else:
            settings=getattr(current,'controls' if group=='control' else 'powers').copy();settings[index]=value
            current=replace(current,**{('controls' if group=='control' else 'powers'):settings})
        parent=None
        if warm_start:
            earlier=[x for x in seeds if x<value]
            parent=max(earlier) if earlier else None
            seed=seeds[parent] if parent is not None else initial_state
        else:seed=initial_state
        if seed is not None:local['initial_state']=seed
        result=solve_modes(model,current,panels,progress=(lambda i,n:progress('linearizing',i,n)) if progress else None,**modal,**local)
        signature=(result['diagnostics']['full_dimension'],result['diagnostics']['state_layout']['operating']['variables'],
                   None if result['controller'] is None else result['controller'].get('state_channels'))
        if reference is None:
            reference=physical_scales(result);reference_layout=signature;reference_rate=result['diagnostics']['time_scale']
        if signature!=reference_layout:raise AnalysisError('Modal coordinate ordering changed during the sweep.')
        roots=representatives(result,reference,reference_rate)
        seeds[value]=result['base']['equilibrium_state']
        return roots,dict(result=result,initialization=dict(warm=seed is not None,parent_value=parent),condition=vars(current),operating_constraints=[vars(c) if not isinstance(c,dict) else c for c in local.get('operating_constraints',())],
                          spectrum_complete=len(result['modes'])==result['diagnostics']['finite_dimension'])
    out=trace_spectrum(evaluate,values,progress=progress,resample_after_subdivision=warm_start,**options)
    out['settings']['warm_start']=warm_start
    out.update(analysis='stability_sweep',parameter=parameter,parameter_unit=unit,
        spectrum_complete=all(p.get('spectrum_complete',False) for p in out['points'] if 'superseded_by' not in p),
        tracking_reference_scales=None if reference is None else reference.tolist(),
        limitations=[
            'Instability boundaries apply to the returned frozen-mode spectrum. Unreturned roots or two crossings between sampled points can be missed; refine grid, count, shift, mesh and tangent/rank tolerances.',
            'Assignments use eigenvector assurance in one fixed reference metric and predicted eigenvalue distance. Ambiguous, missing and real/complex-splitting modes create gaps; no crossing is inferred across them.',
            ('Warm continuation corrects the nearest solved lower-parameter physical equilibrium at full loads. Retried endpoints use inserted intermediate states. Local correction does not establish branch uniqueness or follow folds.' if warm_start else
             'Each operating point is equilibrated from the supplied seed or undeformed configuration. Nonlinear branch following is not established.'),
            'Adaptive subdivision is bounded by depth and extra-point budgets. Unresolved assignments remain gaps; it cannot certify mode identity at repeated roots or recover modes outside the search window.',
            'An oscillatory crossing is a candidate instability of the implemented model, not automatically structural flutter. Inspect mode shape, flight dynamics, damping passivity, base drift and external validation.',
            'Boundary values are actually computed sample points. Resolved refinement requires both a narrow sign bracket and small normalized growth; a discontinuous sign jump is not a resolved zero.',
            'ASWING executable and experimental flutter agreement remain unverified.'
        ])
    return out
