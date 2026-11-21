"""Algebraic cold-start rank certificate for grounded source-beam forests.

At zero applied load, conservative tree
balance first makes every internal/reaction wrench vanish. Finite source
compliance then gives zero strain/curvature increments. A unique full ground,
beam compatibility and finite positive hinge laws remove all pose increments.
The circulation block must still pass its separate numerical rank check.
"""
import numpy as np


class _Forest:
    def __init__(self,n):self.parent=list(range(n))
    def root(self,i):
        while self.parent[i]!=i:
            self.parent[i]=self.parent[self.parent[i]];i=self.parent[i]
        return i
    def join(self,i,j):
        a,b=self.root(i),self.root(j)
        if a==b:return False
        self.parent[b]=a;return True


def source_tree_initial_certificate(net,x,factor):
    """Prove zero mechanical nullspace within the documented zero-load scope.

    This is an algebraic certificate, not a condition-number estimate.
    Unsupported geometry/operators retain the existing numerical checks.
    Callers must separately verify the circulation block and exact absence
    of force/circulation coupling before accepting the complete matrix.
    See docs/validation/source-flexible-tree-rank-20261107.md for the proof.
    """
    def decline(reason):return dict(certified=False,reason=reason)
    from .source_discrete import SourceSectionNetwork,SECTION_POLICY
    from .source_coupled import SourceCoupledNetwork,COUPLED_POLICY
    from .source_dynamics import SourceDynamicNetwork,SourceMovingNetwork,DYNAMIC_POLICY,MOVING_POLICY
    from .source_airflow import SourceAirflowNetwork,AIRFLOW_POLICY
    policies={SourceSectionNetwork:SECTION_POLICY,SourceCoupledNetwork:COUPLED_POLICY,
        SourceDynamicNetwork:DYNAMIC_POLICY,SourceMovingNetwork:MOVING_POLICY,SourceAirflowNetwork:AIRFLOW_POLICY}
    if type(net) not in policies or net.structural_operator!=policies[type(net)]:return decline('unsupported source operator')
    if getattr(net,'analytic_mechanics',True):return decline('source tangent policy changed')
    x=np.asarray(x)
    if factor!=0.:return decline('nonzero load factor')
    if x.shape!=(net.size,) or np.iscomplexobj(x) or not np.all(np.isfinite(x)):return decline('invalid state')
    if np.any(x[:net.gamma_start]):return decline('nonzero mechanical state')
    if net.operating.count or net.operating.constraints:return decline('operating variables or constraints')
    if net.operating_start!=net.gamma_start+net.ng or net.size!=net.operating_start+net.operating.count:return decline('uncovered state layout')
    if net.struts:return decline('struts')
    if net.quiescent_density is not None:return decline('quiescent fluid')
    if any(np.any(getattr(net.motion,k)) for k in ('rates','acceleration','angular_acceleration')):return decline('moving frame')
    if not np.isfinite(net.F) or not np.isfinite(net.L) or min(net.F,net.L)<=0:return decline('invalid equation scales')
    if net.nn<=0 or net.ne<=0 or net.gamma_start!=6*(net.nn+net.ne+len(net.constraints)):return decline('uncovered mechanical variables')
    for name,shape in [('source_compliance',(net.ne,3,3)),('source_direct_compliance',(net.ne,3)),
                       ('source_h',(net.ne,3,3)),('source_jig_curvature',(net.ne,3))]:
        a=np.asarray(getattr(net,name,None))
        if a.shape!=shape or not np.all(np.isfinite(a)):return decline('invalid '+name)
    if np.any(net.source_jig_curvature):return decline('nonzero jig curvature')
    ident=np.broadcast_to(np.eye(3),(net.ne,3,3))
    if not np.array_equal(net.R0a,ident) or not np.array_equal(net.R0b,ident):return decline('outside identity-frame scope')
    if np.any(net.offa) or np.any(net.offb):return decline('stepped axis')
    if not all(np.all(np.isfinite(a)) for a in (net.rj,net.offa,net.offb,net.ds)) or np.any(net.ds<=0):return decline('invalid source geometry')
    if net.ends.shape!=(net.ne,2) or net.ends.dtype.kind not in 'iu' or np.any(net.ends<0) or np.any(net.ends>=net.nn):return decline('invalid element graph')
    forest=_Forest(net.nn);degree=np.zeros(net.nn,int);attachments=np.zeros(net.nn,int)
    for a,b in net.ends:
        if not forest.join(int(a),int(b)):return decline('element cycle')
        degree[a]+=1;degree[b]+=1
    for c in net.constraints:
        attachments[c['a']]+=1
        if c['b'] is not None:attachments[c['b']]+=1
    grounds=[];hinges=[];rigid_joints=0
    for number,c in enumerate(net.constraints):
        a,b,typ=c['a'],c['b'],c['type'];sl=c['sl']
        if sl.start!=6*number or sl.stop!=6*(number+1) or sl.step not in (None,1):return decline('uncovered reaction layout')
        if b is None:
            if typ!=0:return decline('partial ground')
            grounds.append(a);continue
        if typ not in (0,3):return decline('released or unsupported joint')
        if not forest.join(a,b):return decline('joint cycle')
        if typ==0:
            rigid_joints+=1;continue
        e,end=c['element'],c['end']
        if degree[a]!=1 or attachments[a]!=1:return decline('parent hinge trace not isolated')
        if not 0<=e<net.ne or net.ends[e,1 if end else 0]!=a:return decline('invalid hinge trace')
        if not np.array_equal(net.rj[a],net.rj[b]):return decline('offset hinge')
        if c.get('angle_chart',0.)!=0.:return decline('nonzero hinge chart')
        law=c['law'];curve=np.asarray(law.curve)
        if curve.ndim!=2 or curve.shape[1]!=2 or not np.all(np.isfinite(curve)):return decline('invalid hinge curve')
        if not ((curve.shape==(2,2) and np.array_equal(curve[0],-curve[1])) or
                (np.any((curve[:,0]==0)&(curve[:,1]==0)) and law.angle(0.)==0.)):return decline('unproved zero hinge intercept')
        intercept=float(law.angle(0.))
        if not np.isfinite(intercept) or law.zero_angle!=intercept or law.angle(0.,factor=0.)!=0.:return decline('inconsistent hinge intercept')
        axis=np.asarray(law.axis)
        if axis.shape!=(3,) or not np.all(np.isfinite(axis)) or not np.any(axis):return decline('invalid hinge axis')
        slope=float(np.deg2rad(law.spline.evaluate(0.,derivative=1)))
        left=float(np.deg2rad(law.spline.evaluate(0.,side='left',derivative=1)))
        right=float(np.deg2rad(law.spline.evaluate(0.,side='right',derivative=1)))
        if not np.isfinite(slope) or slope==0 or slope!=left or slope!=right:return decline('invalid hinge slope')
        stiffness=(1 if end else -1)/slope
        if not np.isfinite(stiffness) or stiffness<=0:return decline('nonpositive effective hinge stiffness')
        hinges.append(dict(joint=law.index,slope=slope,effective_stiffness=stiffness))
    components={forest.root(i) for i in range(net.nn)};counts={i:0 for i in components}
    for node in grounds:counts[forest.root(node)]+=1
    if any(v!=1 for v in counts.values()):return decline('one full ground per tree required')
    defect=net.rj[net.b]-net.rj[net.a]-net.ds[:,None]*np.array([0.,1.,0.])
    return dict(certified=True,method='source conservative tree balance followed by finite-compliance compatibility',
        factor=0.,source_operator=net.structural_operator,
        trees=len(components),grounds=len(grounds),beam_edges=net.ne,rigid_joints=rigid_joints,hinges=hinges,
        finite_flexible_compliance_allowed=True,statics_unknowns=6*net.nn,pose_unknowns=6*net.nn,
        maximum_cold_translation_defect=float(np.max(abs(defect))),
        numerical_condition_bound=False,cold_equilibrium_claim=False,loaded_stability_claim=False,
        separate_circulation_rank_check_required=True)
