"""Analytic cold-start rank certificate for scoped grounded rigid forests.

At zero homotopy load, eliminate six independent equations per rigid edge,
then five per coincident hinge. One full ground per tree removes its six rigid
motions; positive work-conjugate axial springs remove the remaining hinge
angles. The source equations have a separate, statics-first proof below.
Neither proof uses a finite-difference rank or claims loaded stability.
Unsupported contexts retain the numerical rank checks.
"""
import numpy as np


class _Forest:
    def __init__(self,size):self.parent=list(range(size))
    def root(self,i):
        while self.parent[i]!=i:
            self.parent[i]=self.parent[self.parent[i]];i=self.parent[i]
        return i
    def join(self,i,j):
        a,b=self.root(i),self.root(j)
        if a==b:return False
        self.parent[b]=a
        return True


def reject_redundant_rigid_constraints(net):
    """Detect closed paths of exact ties without treating beams as rigid."""
    from .aero import AnalysisError
    ground = net.nn
    forest = _Forest(ground + 1)
    counts = {'ground': 0, 'joint': 0}
    for constraint in net.constraints:
        kind = constraint['kind']
        counts[kind] += 1
        if constraint['type'] != 0:
            continue
        a, b = constraint['a'], constraint['b']
        if not forest.join(a, ground if b is None else b):
            raise AnalysisError(
                f'Constraints leave a mechanism or redundant reactions: {kind.title()} '
                f'{counts[kind]} closes a loop of rigid joints or full ground restraints. '
                'Check for a duplicate rigid joint or ground restraint.'
            )


def _source_rigid_scope(net):
    """Check the *source* constitutive law, without enabling midpoint tangents.

    For steady Eqs. 48/54 at equal endpoint frames and zero source compliance,
    the first variations in body displacement u and spatial rotation eta are

        du_b - du_a - ds/2 (deta_a + deta_b) cross (R e_s),
        R.T (deta_b - deta_a).

    The graph checks below first eliminate reaction/resultant increments by
    conservative wrench balance, peeling leaves toward the unique Ground.
    The isolated terminal hinge laws then leave equal rotations. Ground fixes
    these to zero; source translation compatibility fixes all displacements.
    This proves a trivial mechanical nullspace without equating ds to the
    actual chord or treating these equations as an energy Hessian. A nonzero
    cold translation defect is reported separately, never accepted as trim.
    """
    from .aero import AnalysisError
    from .source_discrete import (SourceDiscreteNetwork, SourceSectionNetwork,
        STRUCTURAL_POLICY, SECTION_POLICY, COUPLED_POLICY, angles_from_frame)
    from .source_coupled import SourceCoupledNetwork

    def decline(reason):
        return dict(certified=False, reason=reason)

    policies = {SourceDiscreteNetwork: STRUCTURAL_POLICY,
                SourceSectionNetwork: SECTION_POLICY,
                SourceCoupledNetwork: COUPLED_POLICY}
    if (type(net) not in policies or net.structural_operator != policies[type(net)]
            or getattr(net, 'source_dynamic', False) or getattr(net, 'source_moving', False)):
        return decline('unsupported source operator for the static rigid-tree proof')

    def rigid_array(name, shape):
        value = np.asarray(getattr(net, name, None))
        return (value.shape == shape and np.all(np.isfinite(value))
                and not np.any(value))

    if not rigid_array('source_compliance', (net.ne, 3, 3)):
        return decline('nonzero or invalid source bending/torsion compliance')
    if type(net) is SourceDiscreteNetwork:
        if not rigid_array('source_axial_compliance', (net.ne,)):
            return decline('nonzero or invalid source axial compliance')
    else:
        if not rigid_array('source_direct_compliance', (net.ne, 3)):
            return decline('nonzero or invalid source axial/shear compliance')
        transform = np.asarray(net.source_h)
        if transform.shape != (net.ne, 3, 3) or not np.all(np.isfinite(transform)):
            return decline('invalid source section-offset transform')
    if not rigid_array('source_jig_curvature', (net.ne, 3)):
        return decline('nonzero or invalid source jig curvature')
    try:
        angles = angles_from_frame(net.R0a, net.source_fuselage)
    except AnalysisError:
        return decline('source Euler chart is singular')
    periodic = np.where(net.source_fuselage[:, None], angles[:, 1:], angles[:, :2])
    if (not np.all(np.isfinite(angles)) or np.any(abs(periodic) >= np.pi)):
        return decline('source Euler chart lies on a principal branch cut')

    rest_defect = (net.rj[net.b]-net.rj[net.a]
                   - net.ds[:, None]*net.R0a[:, :, 1])
    return dict(certified=True, operator=net.structural_operator,
                proof='source conservative tree balance followed by rigid compatibility',
                source_compliance_exactly_zero=True,
                source_chart_smooth=True,
                maximum_cold_translation_defect=float(np.max(abs(rest_defect), initial=0.)),
                cold_equilibrium_claim=False, energy_hessian_claim=False)


def rigid_tree_initial_certificate(net,x,factor):
    """Return an explicit scope decision; never weaken the numerical fallback."""
    def decline(reason):return dict(certified=False,reason=reason)
    from .source_discrete import SourceDiscreteNetwork
    source = isinstance(net, SourceDiscreteNetwork)
    if source and getattr(net, 'analytic_mechanics', True):
        return decline('source operator must retain its source-specific tangent')
    if not source and not getattr(net, 'analytic_mechanics', True):
        return decline('operator has no certified midpoint rigid-tree compliance')
    x=np.asarray(x)
    if factor!=0:return decline('homotopy load is not exactly zero')
    if x.shape!=(net.size,) or not np.all(np.isfinite(x)):
        return decline('invalid state')
    if np.any(x[:net.gamma_start]):return decline('nonzero mechanical state or preload')
    if net.operating.count or net.operating.constraints:
        return decline('operating variables or constraints')
    if net.struts:return decline('struts are outside the rigid-tree proof')
    if any(np.any(getattr(net.motion,k)) for k in ('rates','acceleration','angular_acceleration')):
        return decline('moving-frame state')
    if not np.isfinite(net.F) or not np.isfinite(net.L) or min(net.F,net.L)<=0:
        return decline('invalid equation scales')
    if not source and (not np.all(np.isfinite(net.S)) or np.any(net.S)):
        return decline('nonzero assembled strain compliance')
    if np.any(net.ds<=0) or not np.all(np.isfinite(net.ds)):
        return decline('nonpositive element length')
    if not np.array_equal(net.R0a,net.R0b):
        return decline('unequal endpoint section frames')
    frames=net.R0a
    if not np.all(np.isfinite(frames)) or not np.array_equal(
            np.swapaxes(frames,-1,-2)@frames,np.broadcast_to(np.eye(3),frames.shape)):
        return decline('section frames are outside the exact orthonormal scope')
    if not np.all(np.linalg.det(frames)>0):return decline('improper section frame')
    if not all(np.all(np.isfinite(v)) for v in (net.rj,net.offa,net.offb)):
        return decline('nonfinite rigid geometry')
    if np.any(net.offa) or np.any(net.offb):
        return decline('section geometry offsets are outside the initial proof')
    source_scope = None
    if source:
        source_scope = _source_rigid_scope(net)
        if not source_scope['certified']:
            return source_scope
    else:
        rest=np.einsum('nji,nj->ni',frames,net.rj[net.b]-net.rj[net.a])
        if np.any(net.k0) or not np.array_equal(net.v0,rest):
            return decline('nonzero or inconsistent rest strain')
    rigid=_Forest(net.nn);degree=np.zeros(net.nn,dtype=int)
    for i,j in net.ends:
        if not rigid.join(int(i),int(j)):return decline('redundant element cycle')
        degree[i]+=1;degree[j]+=1
    attachments=np.zeros(net.nn,dtype=int);grounds=[];hinges=[];rigid_joints=0
    for c in net.constraints:
        i,j,typ=c['a'],c['b'],c['type']
        attachments[i]+=1
        if j is not None:attachments[j]+=1
        if c['sl'].stop-c['sl'].start!=6:return decline('partial constraint')
        if j is None:
            if typ!=0:return decline('partial ground')
            grounds.append(i)
        elif typ==0:
            if not rigid.join(i,j):return decline('redundant rigid-joint cycle')
            rigid_joints+=1
        elif typ==3:hinges.append(c)
        else:return decline('unsupported joint freedom')
    body_ids=sorted({rigid.root(i) for i in range(net.nn)})
    index={v:i for i,v in enumerate(body_ids)}
    body=np.array([index[rigid.root(i)] for i in range(net.nn)])
    forest=_Forest(len(body_ids));spring_report=[]
    for c in hinges:
        i,j,e,end=c['a'],c['b'],c['element'],c['end']
        if body[i]==body[j] or not forest.join(int(body[i]),int(body[j])):
            return decline('redundant hinge cycle')
        if degree[i]!=1 or attachments[i]!=1:
            return decline('parent hinge trace is not an isolated terminal endpoint')
        if e<0 or e>=net.ne or net.ends[e,1 if end else 0]!=i:
            return decline('parent hinge trace element does not match endpoint')
        if not np.array_equal(net.rj[i],net.rj[j]):
            return decline('offset hinge is outside the proof')
        if c.get('angle_chart',0.)!=0:return decline('nonzero hinge chart')
        law=c['law']
        curve=np.asarray(law.curve)
        if curve.ndim!=2 or curve.shape[1]!=2 or not np.all(np.isfinite(curve)):
            return decline('invalid hinge source curve')
        if curve.shape==(2,2) and np.array_equal(curve[0],-curve[1]):
            intercept_proof='exact antisymmetric two-point source curve'
        elif np.any((curve[:,0]==0)&(curve[:,1]==0)) and law.angle(0.)==0:
            intercept_proof='explicit zero-angle source knot at zero moment'
        else:return decline('source curve does not certify zero hinge intercept')
        evaluated_intercept=float(law.angle(0.))
        if (not np.isfinite(evaluated_intercept) or law.zero_angle!=evaluated_intercept
                or law.angle(0.,factor=0.)!=0):
            return decline('zero-load hinge angle or intercept cache is inconsistent')
        axis=np.asarray(law.axis)
        if axis.shape!=(3,) or not np.all(np.isfinite(axis)) or not np.any(axis):
            return decline('invalid hinge axis')
        slope=float(np.deg2rad(law.spline.evaluate(0.,derivative=1)))
        left=float(np.deg2rad(law.spline.evaluate(0.,side='left',derivative=1)))
        right=float(np.deg2rad(law.spline.evaluate(0.,side='right',derivative=1)))
        if not np.isfinite(slope) or slope==0 or slope!=left or slope!=right:
            return decline('nonfinite, zero or ambiguous hinge slope')
        sign=1 if end else -1
        stiffness=sign/slope
        if not np.isfinite(stiffness) or stiffness<=0:
            return decline('nonpositive or unrepresentable effective hinge stiffness')
        spring_report.append(dict(joint=law.index,parent_node=int(i),child_node=int(j),
            parent_body=int(body[i]),child_body=int(body[j]),parent_trace_sign=sign,
            slope_rad_per_moment=slope,effective_stiffness=stiffness,
            zero_intercept_proof=intercept_proof,evaluated_intercept_rad=evaluated_intercept))
    components={forest.root(i) for i in range(len(body_ids))}
    ground_counts={i:0 for i in components}
    for node in grounds:ground_counts[forest.root(int(body[node]))]+=1
    if any(count!=1 for count in ground_counts.values()):
        return decline('each rigid tree requires exactly one full ground')
    report = dict(certified=True,method=('source grounded rigid-tree initial rank' if source
                  else 'analytic grounded rigid-tree initial rank'),
        factor=0.,rigid_bodies=len(body_ids),trees=len(components),grounds=len(grounds),
        rigid_element_edges=net.ne,rigid_joint_edges=rigid_joints,hinges=spring_report,
        eliminated_rigid_edge_equations=6*(net.ne+rigid_joints),
        constrained_body_dofs=6*len(grounds)+5*len(hinges),positive_spring_dofs=len(hinges),
        numerical_condition_bound=False,loaded_stability_claim=False)
    if source:
        report['source_scope'] = source_scope
    return report
