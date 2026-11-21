"""AE-3 native MM observables from the complete source equations.

Drela steady §§8.3–8.7: implicit elastic response, fixed base normalization,
and separately reported mass integrals. No fitted section properties or
alternative lifting-line operator. This module is imported only by workers.
"""
from copy import deepcopy
from dataclasses import replace
import numpy as np

from scripts.isae_suite_ae3 import OBSERVABLE_PARAMETERS as PARAMETERS,OBSERVABLE_GATES as GATES
SUFFIXES=('u','a','b','p','q','r','dF1')


def normalized_rates(condition,chord,span):
    from openswing.derivatives import stability_rotation
    rates=np.asarray(condition.rates,dtype=float)
    scale=np.array([span,chord,span])/(2*condition.speed)
    body=rates*scale;stability=(stability_rotation(condition.alpha)@rates)*scale
    names=('body_Wx_b_2V','body_Wy_c_2V','body_Wz_b_2V',
           'stability_p_b_2V','stability_q_c_2V','stability_r_b_2V')
    return dict(zip(names,map(float,np.r_[body,stability])))


def mass_outputs(network,data):
    """Map the report tensors, keeping the zero-real-mass convention explicit.

    Current AE-3 inputs have zero real mass AND zero section/point inertia.
    Verify this from the physical records before using MM's zero-centroid
    display convention. An undefined physical CG is not an apparent-mass CG.
    The apparent tensor is the §8.7 surface integral already reported by aero.
    """
    from openswing.inertia import apparent_properties
    if len(network.model.beams)!=1 or network.model.beams[0].index!=1:
        raise ValueError('AE-3 mass reporting requires its single native beam.')
    records=data['masses']
    if not records or any(np.any(record[key]) for record in records for key in ('mass','inertia','spin')):
        raise ValueError('AE-3 zero-real-inertia reporting requires verified zero physical mass/inertia records.')
    if any(np.any(network.model.beams[0].value(key,t))
           for key in ('mg','Dmg','mgcc','mgnn','Dmgcc','Dmgnn')
           for t in network.station_nodes[1][0]):
        raise ValueError('AE-3 real section inertia is nonzero; an explicit nonzero-mass reporting extension is required.')
    origin=np.zeros(3);centroid=np.zeros(3)
    rho=data['aero']['atmosphere']['density']
    properties=apparent_properties(data['meshes'],rho,origin,network.condition.body_added_mass_factor)
    matrix=np.asarray(properties['spatial_matrix'])
    values={f'{prefix}_{axis}':0. for prefix in ('mass_centroid','center_of_mass','jig_center_of_mass') for axis in 'xyz'}
    for axis in ('xx','yy','zz'):values['real_mass_'+axis]=0.
    entries=[('xx',0,0),('xy',0,1),('xz',0,2),('yy',1,1),('yz',1,2),('zz',2,2)]
    for name,i,j in entries:
        values['apparent_mass_'+name]=float(matrix[i,j])
        for about in ('origin','centroid'):
            values[f'real_inertia_{about}_{name}']=0.
            values[f'apparent_inertia_{about}_{name}']=float(matrix[i+3,j+3])
    return values,dict(origin=origin.tolist(),reported_real_centroid=centroid.tolist(),
        physical_real_centroid=None,zero_real_mass_verified=True,
        real_record_maxima=[{key:float(np.max(abs(record[key]),initial=0)) for key in ('mass','inertia','spin')} for record in records],
        centroid_convention='MM prints the origin for this zero-real-mass model; no physical or apparent CG is inferred.',
        apparent_spatial_matrix=matrix.tolist(),apparent_reference=properties['reference'],
        method='Drela steady Eqs.237–256; actual deformed section normals, midchord arms and current interval lengths.')


def complete_observables(network,state,data,base_values,*,derivatives=True):
    from scipy.sparse import hstack
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.geometry_tangent import geometry_columns
    from openswing.derivative_controls import capture_control_columns
    from openswing.derivatives import perturb_condition,stability_rotation
    from openswing.operating import OperatingSystem
    from openswing.sparse_newton import memory_bounded_newton_factor
    from scripts.isae_suite_ae3 import coefficients,NAMES

    checks=[]
    def check(name,value,gate):
        value=float(value)
        item=dict(name=name,metric=value,gate=float(gate),passed=bool(np.isfinite(value) and value<=gate))
        checks.append(item)
        if not item['passed']:raise ValueError(f'AE-3 observable check failed: {item}')
    def relative(a,b):
        a,b=np.asarray(a),np.asarray(b)
        return float(np.max(abs(a-b),initial=0)/max(1.,np.max(abs(b),initial=0)))

    condition=network.condition;model=network.model;x=np.asarray(state).copy()
    flow=SourceAirflowNetwork(model,network.panels,condition,network.gravity,(),steady_trim=True)
    if flow.size!=network.size or any(not np.array_equal(flow.station_nodes[k][0],v[0]) for k,v in network.station_nodes.items()):
        raise ValueError('AE-3 observable transfer changed the actual node layout.')
    qS=.5*condition.density*condition.speed**2*model.reference[0,0]
    def mapped(packet):
        result=coefficients(packet['distributed_aero_force'],packet['distributed_aero_moment'],
                            condition.alpha,qS,model.reference[0,1],model.reference[0,2])
        return np.array([result[name] for name in NAMES])
    def at(z,c=condition,detail=False):
        flow.operating=OperatingSystem(model,c,c.motion(),[],flow.L,flow.F)
        flow.aero_key=flow.aero_cached=None
        return flow.residual(z,detail=detail)
    base_residual,base=at(x,detail=True)
    check('base_residual',np.max(abs(base_residual)),GATES['base_residual'])
    check('base_operator_parity',relative(base_residual,network.residual(x)),GATES['operator_parity'])
    check('base_output_parity',relative(mapped(base['aero']),[base_values[k] for k in NAMES]),GATES['operator_parity'])
    rng=np.random.default_rng(3101);directions=[]
    for i in range(2):
        direction=rng.standard_normal(flow.size);direction/=max(abs(direction));directions.append(direction)
        check(f'off_state_operator_parity_{i}',relative(at(x+1e-6*direction),network.residual(x+1e-6*direction)),GATES['operator_parity'])
    at(x)

    values=normalized_rates(condition,model.reference[0,1],model.reference[0,2])
    masses,mass_report=mass_outputs(flow,base);values.update(masses)
    # Independently recover every apparent spatial-mass column from the actual
    # accelerating-frame loads, with geometry/circulation held at the base.
    recovered=[]
    for j in range(6):
        samples=[]
        for sign in (1.,-1.):
            motion=np.zeros(6);motion[j]=sign
            c=replace(condition,acceleration=motion[:3].tolist(),angular_acceleration=motion[3:].tolist())
            _,sample=at(x,c,True);a=sample['aero']
            samples.append(np.r_[a['apparent_force'],a['apparent_moment']])
        recovered.append(-(samples[0]-samples[1])/2)
    mass_report['acceleration_recovered_apparent_spatial_matrix']=np.array(recovered).T.tolist()
    check('apparent_mass_acceleration_recovery',relative(np.array(recovered).T,mass_report['apparent_spatial_matrix']),GATES['mass_recovery'])
    at(x)
    if not derivatives:
        return dict(values=values,checks=checks,numerical_gates=deepcopy(GATES),
            method='Drela §8.7 mass integrals and body/stability rate transforms, checked against actual acceleration loads.',
            source_operator=flow.structural_operator,base_operator=network.structural_operator,
            mass_properties=mass_report,base_coefficients=dict(base_values),
            factorization_count=0,response_columns=0,residual_evaluations=flow.nfev,
            historical_settings_recovered=False)

    matrix=flow.jacobian(x,1.,_direct_geometry=True,_sparse=True)
    fourth,geometry=geometry_columns(flow,lambda d:at(x+d),lambda d:x+d,np.maximum(1.,abs(x)),
        step=1e-5,factor=1.,difference_order=4,_nodewise_state=True,_direct_vortex=True,
        _direct_volume=True,_direct_geometry=True,_direct_structural=False)
    matrix=hstack([fourth,matrix[:,6*flow.nn:]],format='csc');del fourth
    matrix.sum_duplicates();matrix.eliminate_zeros();matrix.sort_indices()
    # Keep the original derivative rank gate; a sparse LU success by itself
    # does not certify a sufficiently conditioned coupled response.
    norms=np.maximum(np.sqrt(np.asarray(matrix.power(2).sum(axis=0))).ravel(),1e-30)
    scaled=matrix.toarray();scaled/=norms
    singular=np.linalg.svd(scaled,compute_uv=False);del scaled
    reciprocal=float(singular[-1]/singular[0])
    check('reciprocal_condition_gate',GATES['reciprocal_condition']/max(reciprocal,1e-300),1.)
    for i,d in enumerate(directions):
        h=1e-6
        check(f'full_tangent_direction_{i}',relative(matrix@d,(at(x+h*d)-at(x-h*d))/(2*h)),GATES['directional_tangent'])
    at(x)
    audit={};control=capture_control_columns(flow,x,flow.residual,base_residual,controls=[1],
        response='fixed_acceleration',feedback=None,step=1e-5,report=audit)
    if control is None or not audit['enabled']:raise ValueError('AE-3 analytic control partial unavailable.')
    partials=[]
    for parameter in PARAMETERS:
        estimates=[]
        for h in (1e-4,5e-5):
            samples=[at(x,perturb_condition(condition,parameter,m*h,model)) for m in (1.,-1.,2.,-2.)]
            estimates.append((8*(samples[0]-samples[1])-(samples[2]-samples[3]))/(12*h))
        check('input_refinement_'+parameter,relative(*estimates),GATES['input_refinement'])
        partial=estimates[1]
        if parameter=='control.1':
            check('analytic_control_partial',relative(control[:,0],partial),GATES['input_refinement']);partial=control[:,0]
        partials.append(partial)
    at(x)
    factor=memory_bounded_newton_factor(flow,matrix);responses=[];derivatives=[]
    for parameter,partial in zip(PARAMETERS,partials):
        dx=factor.solve(-partial);responses.append(dx)
        check('linear_residual_'+parameter,relative(matrix@dx,-partial),GATES['linear_residual'])
        estimates=[];width=min(1e-4,1e-4/max(1.,np.max(abs(dx))))
        for h in (width,width/2):
            _,plus=at(x+h*dx,perturb_condition(condition,parameter,h,model),True)
            _,minus=at(x-h*dx,perturb_condition(condition,parameter,-h,model),True)
            estimates.append((mapped(plus['aero'])-mapped(minus['aero']))/(2*h))
        check('output_refinement_'+parameter,relative(*estimates),GATES['output_refinement']);derivatives.append(estimates[1])
    derivatives=np.array(derivatives).T
    values.update({name+suffix:float(derivatives[i,j]) for i,name in enumerate(NAMES) for j,suffix in enumerate(SUFFIXES)})
    at(x)
    return dict(values=values,checks=checks,numerical_gates=deepcopy(GATES),
        method='Complete implicit source response: analytic mechanical/circulation/control blocks, fourth-order local geometry and other input partials; refined directional output derivatives.',
        source_operator=flow.structural_operator,base_operator=network.structural_operator,
        response='fixed_acceleration',axes='stability',parameters=list(PARAMETERS),coefficient_rows=list(NAMES),
        coefficient_derivatives=derivatives.tolist(),base_coefficients=dict(base_values),
        normalization=dict(qS=qS,chord=float(model.reference[0,1]),span=float(model.reference[0,2]),
            axes='fixed base stability axes',angles='radians',rates='p b/2V, q c/2V, r b/2V',control='file F1 units'),
        mass_properties=mass_report,reciprocal_condition=reciprocal,factor=factor.report,
        factorization_count=1,response_columns=7,geometry=geometry,control_partial=audit,
        residual_evaluations=flow.nfev,system_size=flow.size,matrix_nonzeros=matrix.nnz,
        historical_settings_recovered=False,
        qualifications=['Native MM response convention remains conditional; fixed accelerations are declared explicitly.',
            'Moving-airflow input partials use the same zero-rate source base, checked at equilibrium and off-equilibrium.',
            'The reported apparent tensor is not substituted for a structural descriptor mass matrix.'])
