"""Continuous derivative matrix without subtracting loaded residuals.

At fixed state the physical load evaluator is linear in local accelerations
and at most quadratic in circulation rate (the tangency-drag term). Symmetric
unit-rate probes extract its exact linear coefficient. Nonlinear hinge and
controller compositions are differentiated separately by the chain rule.
"""
import numpy as np
from .local_motion import NetworkMotion, left_jacobian, rotation_matrix, rotation_vector
from .feedback import measurements
from .control_expressions import check_sides


def mass_matrix(system, state, data, step, progress=None, *, sparse=False):
    """Return M=-R_zdot at the loaded state, in physical input-time units."""
    n=system.network;size=system.size;f=system.feedback;r,q=data['r'],data['Q']
    if sparse:
        from scipy.sparse import lil_matrix
        mass=lil_matrix((size,size))
    else:mass=np.zeros((size,size))
    zero=np.zeros(size)
    force_rows=slice(6*n.ne,6*n.ne+3*n.nn)
    moment_rows=slice(6*n.ne+3*n.nn,6*n.ne+6*n.nn)
    # Exact coordinate rate definitions; no finite-difference rank noise.
    for node in range(n.nn):
        for axis in range(3):
            mass[n.size+3*node+axis,6*node+axis]=-n.L/system.V
            mass[n.size+3*n.nn+3*node+axis,6*node+3+axis]=-1/system.W
    if system.frame!='fixed':
        from .linear_dynamics import euler_matrix
        start=system.frame_start
        mass[start:start+9,start:start+9]=-np.diag([1/system.W]*6+[n.L/system.V]*3)
        mass[start+9:start+12,start+9:start+12]=-euler_matrix(system.attitude)/system.W

    hinge_base={row['joint']:row for row in data['hinges']}
    hinges=[];row=6*(n.ne+n.nn)
    for c in n.constraints:
        if c['type']!=2:row+=3
        if c['type']!=1:
            if c['type']==3:
                law=c['law'];mh=hinge_base[law.index]['structural_moment']
                relative=rotation_matrix(-law.angle(mh)*law.axis)@q[c['a']].T@q[c['b']]
                slope=np.deg2rad(law.spline.evaluate(mh,derivative=1))
                gradient=-np.linalg.solve(left_jacobian(rotation_vector(relative)),law.axis)*slope
                hinges.append((slice(row,row+3),c,gradient,q[c['a']]@law.axis))
            row+=3

    signals=[] if f is None else f.signals
    sensed_rate=np.zeros((len(signals),size))
    if f is not None:
        sensed0=measurements(n,state,data)
        direct=np.arange(f.count,f.size)
        mass[system.feedback_start+direct,system.feedback_start+direct]=-f.scales[direct]/f.rate_scales
    key=(state.x[n.operating_start:].tobytes(),repr(data['condition']))

    def probe(rate):
        ud,wd=rate[system.velocity_start:system.frame_start].reshape(2,n.nn,3)
        local=NetworkMotion(n,r,q,state.u,state.w,system.V*ud,system.W*wd)
        gamma_dot=n.circulation_basis.decode(rate[n.gamma_start:n.operating_start]*n.gamma_scale)
        force,moment,aero,masses,ends,end_forces=n.external(r,q,data['meshes'],state.gamma,
            data['condition'],data['motion'],key,local_motion=local,circulation_rate=gamma_dot,gravity=data['gravity'],_loads_only=sparse and f is None)
        values=dict(force=force,moment=moment,aero=aero,masses=masses,element_moments=ends,
                    element_forces=end_forces,local_motion=local)
        sensed=None if f is None else measurements(n,state,{**data,**values})
        return values,sensed

    # Acceleration changes act through element/point inertia at fixed geometry.
    # They do not change induced velocity, source strengths or circulation flow
    # equations. Nodes whose incident elements have disjoint endpoints can share
    # the same symmetric load probe. Feedback retains individual probes because
    # a measurement can combine arbitrary locations before a nonlinear law.
    supports={};element_supports={};flow_supports={};jobs=[]
    if sparse and f is None:
        from .structured_static import coloring
        nodes=[]
        for node in range(n.nn):
            elements=np.flatnonzero((n.a==node)|(n.b==node))
            nodes.append(np.unique(np.r_[node,n.ends[elements].ravel()]))
            element_supports[node]=elements
        for component in range(6):
            for group in coloring(nodes):
                columns=system.velocity_start+(component//3)*3*n.nn+3*group+component%3
                jobs.append(columns)
                for node,j in zip(group,columns):supports[j]=(nodes[node],element_supports[node])
        # Gamma-dot changes the local shed-vorticity correction, rate lift and
        # tangency drag, but not any vortex/volume/jet velocity at fixed Gamma.
        # Color exact supports in both nodal loads and tested flow equations.
        # Fourier coefficients can touch an entire beam and its test rows;
        # retain those full supports rather than assuming diagonal circulation.
        if n.ng:
            lifting=np.concatenate([np.arange(n.beam_elements[mesh.beam.index].start,
                n.beam_elements[mesh.beam.index].stop) for mesh in n.meshes if mesh.beam.lifting])
            basis=n.circulation_basis
            if len(lifting)!=basis.panels:
                raise ValueError('Circulation-rate support does not match the lifting mesh.')
            rows=[];columns=np.arange(n.gamma_start,n.operating_start)
            for k,j in enumerate(columns):
                panels=np.flatnonzero(basis.sample[:,k]!=0.)
                elements=lifting[panels];nodes=np.unique(n.ends[elements].ravel())
                flow=np.flatnonzero(np.any(basis.test[:,panels]!=0.,axis=1))
                supports[j]=(nodes,elements);flow_supports[j]=flow
                rows.append(np.r_[nodes,n.nn+flow])
            jobs.extend(columns[group] for group in coloring(rows))
    active_columns=[j for j in system.dynamic_indices if n.gamma_start<=j<n.operating_start or system.velocity_start<=j<system.frame_start]
    jobs += [np.array([j]) for j in active_columns if j not in supports]
    count=completed=0
    for columns in jobs:
        rate=zero.copy();rate[columns]=system.W
        plus,sp=probe(rate);minus,sm=probe(-rate);count+=2
        def delta(key):return (plus[key]-minus[key])/(2*system.W)
        forces,moments,ends=delta('force'),delta('moment'),delta('element_moments')
        flow=None if not n.ng else -(np.asarray(plus['aero']['circulation_residual'])
            -np.asarray(minus['aero']['circulation_residual']))/(2*system.W)
        for j in columns:
            df,dm,de=forces,moments,ends;column_flow=flow
            if j in supports:
                nodes,elements=supports[j]
                df=np.zeros_like(forces);df[nodes]=forces[nodes]
                dm=np.zeros_like(moments);dm[nodes]=moments[nodes]
                de=np.zeros_like(ends);de[elements]=ends[elements]
                if j in flow_supports:
                    column_flow=np.zeros_like(flow);indices=flow_supports[j]
                    column_flow[indices]=flow[indices]
                elif flow is not None and np.any(flow):
                    raise ValueError('Local acceleration unexpectedly changes circulation flow equations.')
            mass[force_rows,j]=-df.ravel()/n.F
            mass[moment_rows,j]=-dm.ravel()/(n.F*n.L)
            for rows,c,gradient,axis in hinges:
                mh=(-1 if c['end'] else 1)*(de[c['element'],int(c['end'])]@axis)
                mass[rows,j]=-gradient*mh
            if n.ng:mass[n.gamma_start:n.operating_start,j]=column_flow
            for k,constraint in enumerate(n.operating.constraints):
                group,axis=constraint.quantity.split('.')
                value=df.sum(axis=0) if group=='force' else (dm+np.cross(r-n.model.reference[1],df)).sum(axis=0)
                scale=n.F*(1 if group=='force' else n.L)
                mass[n.operating_start+k,j]=-value['xyz'.index(axis)]/scale
            if f is not None:
                sensed_rate[:,j]=[(sp[name]-sm[name])/(2*system.W) for name in signals]
        completed+=len(columns)
        if progress is not None:progress(size+completed,size+len(system.dynamic_indices))
    if progress is not None:progress(size+len(system.dynamic_indices),size+len(system.dynamic_indices))

    # Controller expressions may depend nonlinearly on accelerometers or load
    # traces. Differentiate their scalar measurement arguments locally, then
    # multiply by the physical measurement derivative. No large probe passes
    # through a saturation, branch, expression or gain schedule.
    active=[]
    if f is not None and f.needs_side_check:
        # Piecewise expressions need the original composite path. Perturbing
        # their measured arguments independently can reject a smooth cancellation
        # between coincident sensors, or miss a switch reached quadratically.
        baseline=system.residual(zero,zero)[system.feedback_start:]
        for j in system.dynamic_indices:
            h=step*system.W;rate=zero.copy();rate[j]=h
            values=[system.residual(zero,v*rate)[system.feedback_start:] for v in (1,-1,2,-2)]
            plus,minus,plus2,minus2=values
            check_sides(baseline,minus,plus,minus2,plus2,h)
            mass[system.feedback_start:,j]=-(8*(plus-minus)-(plus2-minus2))/(12*h)
        active=[name for k,name in enumerate(signals) if np.any(sensed_rate[k])]
    elif f is not None:
        derivatives=np.zeros(f.size)
        for k,name in enumerate(signals):
            if not np.any(sensed_rate[k]):continue
            active.append(name);h=step*f.signal_scales[name]
            def control(increment):
                return f.evaluate_measurements(state,data,{**sensed0,name:sensed0[name]+increment},derivatives)[0]
            plus,minus,plus2,minus2=(control(v*h) for v in (1,-1,2,-2))
            gradient=(8*(plus-minus)-(plus2-minus2))/(12*h)
            mass[system.feedback_start:]-=gradient[:,None]*sensed_rate[k]
    system.derivative_diagnostics=dict(method='physical load coefficient extraction and chain rule',
        load_probe_rate=system.W,load_polynomial_degree=2,load_evaluations=count,
        grouped_circulation_rate_columns=len(flow_supports),
        circulation_rate_groups=sum(any(j in flow_supports for j in group) for group in jobs),
        hinge_derivative='analytic Jangle slope and SO(3) logarithm derivative',
        controller_difference_order=4,controller_difference_step=step,rate_dependent_measurements=active,
        controller_method='composite directional differences with one-sided checks' if f is not None and f.needs_side_check else 'measurement chain rule',
        interpretation='Kinematic and controller-rate identities are exact. Fixed-state loads and measurements are at most quadratic in derivatives; symmetric physical probes extract their linear coefficient. No inertia threshold or matrix-entry snapping is applied.')
    return mass.tocsc() if sparse else mass
