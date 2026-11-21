"""Bounded primary-source checks of Daedalus material and aerodynamic axes."""
import argparse
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-section-axes-20261114'
OLD=ROOT/'reference/st4-node-placement-20261109/drela-1989-wing-loads.pdf'
MODERN=ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf'


def inspect(folder,args):
    import pymupdf
    pages=[]
    for name,path,page in [('paper',OLD,2),('modern-section',MODERN,9),('modern-stiffness',MODERN,7)]:
        with pymupdf.open(path) as pdf:
            pdf[page].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save(str(folder/f'{name}.png'))
            (folder/f'{name}.txt').write_text(pdf[page].get_text())
            pages.append(dict(source=str(path.relative_to(ROOT)),pdf_page=page+1,image=f'{name}.png'))
    return dict(pages=pages,qualification='Original source pages; no drawing or parameter modification.')


def relations(folder,args):
    import pymupdf
    pages=[]
    for name,path,page in [('modern-relations',MODERN,10),('modern-mohr',MODERN,11),('paper-axes',OLD,1)]:
        with pymupdf.open(path) as pdf:
            pdf[page].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save(str(folder/f'{name}.png'))
            (folder/f'{name}.txt').write_text(pdf[page].get_text())
            pages.append(dict(source=str(path.relative_to(ROOT)),pdf_page=page+1,image=f'{name}.png'))
    return dict(pages=pages,qualification='Original transformation definitions and sign conventions; no reconstruction.')


def frame(theta):
    """Physical section basis: c points aft/down for positive incidence."""
    import numpy as np
    c,s=np.cos(theta),np.sin(theta)
    return np.array([[c,0.,s],[0.,1.,0.],[-s,0.,c]])


def fiber_stiffness(frames,outplane,inplane,torsion):
    """Integrate axial stress moments of four symmetric weighted fibers.

    epsilon = kappa dot (r cross span); M = sum(EA epsilon r cross span).
    These fictitious fibers realize the prescribed bending moments of area,
    not the aircraft's actual spar geometry, weight or axial compliance.
    """
    import numpy as np
    frames=np.asarray(frames);outplane=np.asarray(outplane);inplane=np.asarray(inplane)
    signs=np.array([[-1.,-1.],[-1.,1.],[1.,-1.],[1.,1.]])
    local=np.zeros((len(frames),4,3));local[:,:,0]=signs[:,0]
    local[:,:,2]=np.sqrt(outplane/inplane)[:,None]*signs[:,1]
    positions=np.einsum('nij,nfj->nfi',frames,local)
    span=frames[:,:,1];arms=np.cross(positions,span[:,None,:])
    return (np.einsum('nfi,nfj,n->nij',arms,arms,inplane/4)
            +np.einsum('ni,nj,n->nij',span,span,np.asarray(torsion)))


def audit(folder,args):
    import numpy as np
    from types import SimpleNamespace
    from scipy.spatial.transform import Rotation,Slerp
    from openswing.structure import Section
    from openswing.structured_static import IterationFields
    from openswing.frequency_response import HarmonicInput
    from check_daedalus_structural_resolution import dynamic
    from check_daedalus_paper_properties import literal_wing_tables
    literal=literal_wing_tables((ROOT/'examples/dae.asw').read_text())
    theta=np.deg2rad(literal['twist'][0][1]);alpha=np.deg2rad(literal['alpha'][0][1])
    assert all(r[1]==8.2 for r in literal['twist'])
    root_out=literal['EIcc'][0][1];root_in=literal['EInn'][0][1];root_gj=literal['GJ'][0][1]
    root_R=frame(theta)
    root_K=fiber_stiffness(root_R[None],[root_out],[root_in],[root_gj])[0]
    # Paper Eq.1: positive fore/aft deflection slope phi means physical
    # kappa_n = -phi'. Its conjugate generalized moment is -physical M_n.
    old=np.array([[root_out*np.cos(theta)**2+root_in*np.sin(theta)**2,
        (root_out-root_in)*np.sin(theta)*np.cos(theta)],
        [(root_out-root_in)*np.sin(theta)*np.cos(theta),
         root_in*np.cos(theta)**2+root_out*np.sin(theta)**2]])
    D=np.diag([1.,-1.]);old_from_stress=D@root_K[np.ix_([0,2],[0,2])]@D
    old_error=float(max(abs(old_from_stress-old).ravel()))
    assert old_error<1e-9
    # Evaluate the literal modern printed Eq.43 separately from direct stress
    # integration and Eqs.24-26; do not silently change its printed sign.
    e43=.5*np.arctan(-2*root_K[0,2]/(root_K[2,2]-root_K[0,0]))
    passive=frame(e43)@root_K@frame(e43).T
    applied_as_twist=frame(e43).T@root_K@frame(e43)
    correct=frame(-e43).T@root_K@frame(-e43)
    np.testing.assert_allclose(correct,np.diag([root_out,root_gj,root_in]),atol=2e-9,rtol=0)
    assert abs(passive[0,2])<1e-9 and abs(applied_as_twist[0,2])>1e5
    # Independent stress integration versus the actual Section input contract,
    # including nonzero EIcn, at several finite axis orientations.
    covariance=[]
    for deg in (-25.,-8.2,0.,8.2,31.):
        R=frame(np.deg2rad(deg));K=fiber_stiffness(R[None],[root_out],[root_in],[root_gj])[0]
        section=Section(EIcc=K[0,0],GJ=K[1,1],EInn=K[2,2],EIcn=K[0,2])
        observed=section.compliance()[3:,3:]
        expected=R@np.diag([1/root_out,1/root_gj,1/root_in])@R.T
        error=float(max(abs(observed-expected).ravel()));assert error<2e-18
        covariance.append(dict(axis_angle_deg=deg,maximum_compliance_error=error))
    system=dynamic(SimpleNamespace(seed=SOURCE/'trim-6.7-1/state.json'));n=system.network
    assert system.size==2044 and not np.any(n.damping_times)
    mesh=n.meshes[0];assert mesh.beam.index==1
    sl=n.beam_elements[1];indices=np.arange(n.ne)[sl];count=len(indices);assert count==28
    # Independently average literal endpoint values, matching the declared
    # source-discrete material quadrature rather than the aerodynamic midpoint.
    outplane=(mesh.beam.value('EIcc',mesh.t0,side='right')+mesh.beam.value('EIcc',mesh.t1,side='left'))/2
    inplane=(mesh.beam.value('EInn',mesh.t0,side='right')+mesh.beam.value('EInn',mesh.t1,side='left'))/2
    torsion=(mesh.beam.value('GJ',mesh.t0,side='right')+mesh.beam.value('GJ',mesh.t1,side='left'))/2
    for e in indices:
        sec=n.source_sections[e]
        assert all(getattr(sec,k)==0 for k in ('EIcn','EIcs','EIsn','Cea','Nea','Cta','Nta'))
    with np.load(ROOT/'artifacts/daedalus-wing-peak-mass-20261114/dip/arrays.npz') as saved:z=saved['original_state']
    with np.load(SOURCE/'assembled-6.7/maps.npz') as saved:c=saved['C']
    assert abs(abs(c@z)[0]-.07421777263945611)<2e-12
    omega=2*np.pi*1.15737773741517;zero=np.zeros(system.size)
    forcing,_=HarmonicInput(system,'control.3',0).at_frequency(omega)
    rows=[];curvatures=[];normal_rows=[];wrong_errors=[]
    probes=[('mean',0,0.)]+[(name,part,h) for name,part in [('real',0),('imag',1)] for h in (-.001,.001)]
    for name,part,h in probes:
        component=np.real if part==0 else np.imag
        state,_,options=system.physical_state(h*component(z),h*component(1j*omega*z),forcing(part,h))
        fields=IterationFields();fields.capture_circulation=True
        n.iteration_fields=fields;n.aero_key=None
        try:residual,data=n.residual(state.x,detail=True,**options)
        finally:n.iteration_fields=None;n.aero_key=None
        if h==0:assert max(abs(residual))<1e-9
        geometry=n.geometry(data['r'],data['Q']);Ra,Rb=geometry[2][sl],geometry[3][sl]
        Qa=data['Q'][n.a[sl]];Qb=data['Q'][n.b[sl]]
        np.testing.assert_allclose(Ra,Qa@root_R,atol=2e-15,rtol=0)
        np.testing.assert_allclose(Rb,Qb@root_R,atol=2e-15,rtol=0)
        values=[];wrong=[]
        for R,Q in ((Ra,Qa),(Rb,Qb)):
            stiffness=fiber_stiffness(R,outplane,inplane,torsion)
            global_curvature=np.linalg.solve(stiffness,data['M'][sl,:,None])[...,0]
            values.append(np.einsum('nji,nj->ni',R,global_curvature))
            # Negative control: omit the declared initial principal-axis twist.
            wrong_stiffness=fiber_stiffness(Q,outplane,inplane,torsion)
            wrong_global=np.linalg.solve(wrong_stiffness,data['M'][sl,:,None])[...,0]
            wrong.append(np.einsum('nji,nj->ni',R,wrong_global))
        expected=(values[0]+values[1])/2;actual=data['source_discrete']['curvature_change'][sl]
        difference=float(max(abs(actual-expected).ravel()))
        relative=float(np.linalg.norm(actual-expected)/np.linalg.norm(actual));assert relative<2e-12
        wrong_relative=float(np.linalg.norm((wrong[0]+wrong[1])/2-actual)/np.linalg.norm(actual))
        assert wrong_relative>.01;wrong_errors.append(wrong_relative)
        p=fields.circulation_aero['p'];mask=p['beam']==1
        np.testing.assert_array_equal(p['t'][mask],mesh.tm)
        elastic=np.array([Slerp([0.,1.],Rotation.from_matrix(np.array([a,b])))([f]).as_matrix()[0]
            for a,b,f in zip(Qa,Qb,n.fractions[1])])
        aero_angle=np.deg2rad(mesh.beam.value('alpha',mesh.tm))
        for control,value in options['condition_override'].controls.items():
            aero_angle+=value*mesh.beam.value(f'dCLdF{control}',mesh.tm)/mesh.beam.value('dCLda',mesh.tm)
        jig=np.c_[np.sin(theta+aero_angle),np.zeros(count),np.cos(theta+aero_angle)]
        expected_normal=np.einsum('nij,nj->ni',elastic,jig)
        normal_error=float(max(abs(expected_normal-p['normal'][mask]).ravel()));assert normal_error<3e-14
        normal_rows.append([expected_normal,p['normal'][mask]])
        curvatures.append([expected,actual])
        rows.append(dict(probe=name,amplitude=h,curvature_maximum_error=difference,curvature_relative_error=relative,
            zero_lift_normal_maximum_error=normal_error,missing_twist_negative_control_relative_error=wrong_relative))
    curvatures=np.array(curvatures);normal_rows=np.array(normal_rows)
    derivatives=[]
    for name,lo,hi in [('real',1,2),('imag',3,4)]:
        material=(curvatures[hi]-curvatures[lo])/.002
        aero=(normal_rows[hi]-normal_rows[lo])/.002
        error=float(np.linalg.norm(material[0]-material[1])/np.linalg.norm(material[1]));assert error<1e-8
        normal_error=float(max(abs(aero[0]-aero[1]).ravel()));assert normal_error<1e-10
        derivatives.append(dict(direction=name,curvature_derivative_relative_error=error,normal_derivative_maximum_error=normal_error))
    np.savez_compressed(folder/'arrays.npz',root_stiffness=root_K,paper_signed_stiffness=old,
        paper_stiffness_from_stress=old_from_stress,curvatures=curvatures,normals=normal_rows,
        printed_conversion_stiffness=applied_as_twist,passive_conversion_stiffness=passive,
        opposite_angle_stiffness=correct,original_harmonic_state=z)
    return dict(root_twist_deg=float(np.rad2deg(theta)),root_alpha_offset_deg=float(np.rad2deg(alpha)),
        root_zero_lift_line_angle_deg=float(np.rad2deg(theta+alpha)),root_inplane_lb_ft2=root_in,root_outplane_lb_ft2=root_out,
        root_global_stiffness=root_K.tolist(),old_equations_12_14_maximum_error=old_error,
        printed_eq43_angle_deg=float(np.rad2deg(e43)),physical_twist_increment_deg=float(np.rad2deg(-e43)),
        printed_eq43_as_twist_offdiagonal_lb_ft2=float(applied_as_twist[0,2]),
        printed_eq43_passive_offdiagonal_lb_ft2=float(passive[0,2]),covariance_checks=covariance,
        states=rows,direction_checks=derivatives,wing_intervals=count,complete_residual_evaluations=len(probes),
        qualification='Independent fiber stress integration and zero-lift orientation audit on the literal aircraft. Eq43 is diagonalizing as a passive transform; using it as the twist increment in Eq30 has the opposite sign. No native-ASWING behavior or Bode improvement is inferred.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['inspect','relations','audit']);parser.add_argument('--tag',required=True)
    args=vars(parser.parse_args())
    inputs=[OLD,MODERN,ROOT/'reference/aswing_doc.txt',ROOT/'examples/dae.asw',ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'docs/validation/isae-st4-node-placement-sources-20261109.json']
    inputs += list((ROOT/'openswing').glob('*.py'))
    if args['stage']=='audit':
        inputs += [ROOT/'scripts'/name for name in ('check_daedalus_structural_resolution.py','check_daedalus_source_operator.py',
            'check_daedalus_paper_properties.py')]
        inputs += [SOURCE/'trim-6.7-1/state.json',SOURCE/'assembled-6.7/maps.npz',
            ROOT/'examples/dae-cruise-physical-mesh-project.json',
            ROOT/'artifacts/daedalus-wing-peak-mass-20261114/dip/arrays.npz']
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
