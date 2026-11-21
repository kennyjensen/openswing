"""Isolated ST5 zero-offset source-discrete solve; never a production policy.

Use the existing mixed unknown layout, conservative node assembly, constraints,
and sparse Newton machinery. Replace constitutive rows with Eqs48/54 and static
distributed loads with endpoint-average density, half at each endpoint. Both
Newton paths explicitly differentiate this residual instead of reusing the
production analytic mechanics. All caller results must be diagnostic-sealed.
"""
from contextlib import contextmanager
import hashlib
import numpy as np
from openswing.network import StaticNetwork, equilibrate, network_result
from openswing.equilibrium_state import capture
from isae_drela_discrete_diagnostic import angles_from_frame, angle_matrix

SOURCE_SHA='4ae68c3970b38a3ed4656620cc048fba00c1d788bf141e79c22b385add4736ec'
POLICY='diagnostic-st5-source-discrete-v1; Eqs48/54; inverse-average-stiffness; endpoint-weight; ds=unloaded-arc'


class DiscreteNetwork(StaticNetwork):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        assert hashlib.sha256(self.model.dumps().encode()).hexdigest()==SOURCE_SHA
        assert self.condition is None and not self.loads and not self.weights and not self.struts and not self.engines
        assert not self.operating.count and not self.ng and not self.quiescent_density
        assert all(c['type']==0 for c in self.constraints)
        assert not np.any(self.offa) and not np.any(self.offb)
        self.source_Ea=[];self.source_EAa=[];self.source_weights=[]
        for mesh in self.meshes:
            b=mesh.beam
            for name in ['Cea','Nea','Cta','Nta','Ccg','Ncg','DCcg','DNcg','EIcs','EIcn','EIsn']:
                assert not np.any(b.value(name,mesh.t0,side='right')) and not np.any(b.value(name,mesh.t1,side='left'))
            def average(name):
                return (b.value(name,mesh.t0,side='right')+b.value(name,mesh.t1,side='left'))/2
            self.source_Ea.extend(np.array([np.diag(v) for v in np.stack([average(k) for k in ['EIcc','GJ','EInn']],axis=1)]))
            self.source_EAa.extend(average('EA'))
            weights=(average('mg')+average('Dmg'))*mesh.length
            self.source_weights.extend(weights)
            # Reporting bookkeeping must use the same integrated weights.
            entries=[]
            for prefix,entry in zip(['','D'],self.inertia_model.data[b.index]):
                entries.append((average(prefix+'mg')*mesh.length/self.model.constants[0],*entry[1:]))
            self.inertia_model.data[b.index]=entries
        self.source_Ea=np.array(self.source_Ea);self.source_EAa=np.array(self.source_EAa)
        self.source_weights=np.array(self.source_weights)
        self.source_q0a=np.array([angles_from_frame(r) for r in self.R0a])
        self.source_q0b=np.array([angles_from_frame(r) for r in self.R0b])
        self.source_K0a=(np.array([angle_matrix(q) for q in self.source_q0a])+np.array([angle_matrix(q) for q in self.source_q0b]))/2
        self.source_jig_curvature=np.einsum('nij,nj->ni',self.source_K0a,self.source_q0b-self.source_q0a)
        assert np.all(self.source_EAa>0) and np.all(np.linalg.eigvalsh(self.source_Ea)>0)

    def external(self,r,Q,meshes,gamma,condition,motion,operating_key,*,local_motion=None,circulation_rate=None,gravity=None,_loads_only=False):
        assert condition is None and not len(gamma) and circulation_rate is None
        assert not np.any(motion.rates) and not np.any(motion.acceleration) and not np.any(motion.angular_acceleration)
        gravity=self.gravity if gravity is None else np.asarray(gravity)
        element=self.source_weights[:,None]*gravity[None,:]/self.model.constants[0]
        ends=np.repeat((element/2)[:,None,:],2,axis=1)
        couples=np.zeros_like(ends);force=np.zeros_like(r);moment=np.zeros_like(r)
        np.add.at(force,self.a,ends[:,0]);np.add.at(force,self.b,ends[:,1])
        masses=self.inertia_model.elements(meshes)
        self.mass_cached=(force,moment,masses,couples,ends)
        return force,moment,None,masses,couples,ends

    def residual(self,x,factor=1.,detail=False,**kwargs):
        assert kwargs.get('elastic_motion') is None and kwargs.get('circulation_rate') is None
        residual,data=super().residual(x,factor,detail=True,**kwargs)
        pa,pb,Ra,Rb,*_=self.geometry(data['r'],data['Q'])
        qa=np.array([angles_from_frame(r) for r in Ra]);qb=np.array([angles_from_frame(r) for r in Rb])
        assert np.max(abs(qb-qa))<np.pi
        Ta=(Ra.transpose(0,2,1)+Rb.transpose(0,2,1))/2
        Ka=(np.array([angle_matrix(q) for q in qa])+np.array([angle_matrix(q) for q in qb]))/2
        H,J=data['element_forces'],data['element_moments']
        Fbar=data['N']+factor*(H[:,0]-H[:,1])/2
        Mbar=data['M']+factor*(J[:,0]-J[:,1])/2
        Flocal=np.einsum('nij,nj->ni',Ta,Fbar);Mlocal=np.einsum('nij,nj->ni',Ta,Mbar)
        tangent=np.zeros_like(Flocal);tangent[:,1]=1+Flocal[:,1]/self.source_EAa
        translation=(pb-pa-np.einsum('nji,nj->ni',Ta,tangent)*self.ds[:,None])/self.L
        bend=np.linalg.solve(self.source_Ea,Mlocal[...,None])[...,0]*self.ds[:,None]
        rotation=np.einsum('nij,nj->ni',Ka,qb-qa)-self.source_jig_curvature-bend
        residual[:6*self.ne]=np.c_[translation,rotation].ravel()
        if detail:
            data['diagnostic_discrete_policy']=POLICY
            data['source_translation_defect']=translation*self.L
            data['source_rotation_defect']=rotation
            return residual,data
        return residual

    def jacobian(self,x,factor,**kwargs):
        kwargs['_direct_mechanics']=False;kwargs['_direct_geometry']=False
        return super().jacobian(x,factor,**kwargs)


@contextmanager
def source_newton():
    """Process-local diagnostic hook; restored even on failure."""
    import openswing.structured_static as structured
    original=structured.jacobian
    def jacobian(*args,**kwargs):
        kwargs['direct_mechanics']=False
        return original(*args,**kwargs)
    structured.jacobian=jacobian
    try:yield
    finally:structured.jacobian=original


def solve_candidate(model,panels,progress=None):
    net=DiscreteNetwork(model,panels,None,None,[],allow_signed_point_weights=True,allow_signed_distributed_weights=True)
    with source_newton():
        x,steps=equilibrate(net,progress=progress)
    result=network_result(net,x)
    result['continuation_steps']=steps
    result['equilibrium_state']=capture(net,x,residual=result['residual'],include_launch=False)
    result['diagnostic_discrete_policy']=POLICY
    result['diagnostic_output_scope']={
        'accepted_comparison_channels':'Endpoint positions/frames, conservative one-sided resultants, and endpoint shell recovery in the separate comparison.json.',
        'inherited_channels':'elements/structure midpoint Section recovery and SO(3) metadata are inherited production diagnostics, not the candidate Eq54 strain law.',
        'not_a_production_restart':True}
    result['limitations'].append('Diagnostic source equations for this zero-offset ST5 static case only; ds set to unloaded spline arc. Not a production restart or dynamic formulation.')
    return result
