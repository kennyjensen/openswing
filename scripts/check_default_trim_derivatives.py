"""Serial checks for reusing full derivative blocks in steady trim."""
import argparse
import time
from daedalus_bounded_job import run
from check_daedalus_load_sensitivity import ROOT, read, write, LIMITS

STUDY=ROOT/'artifacts/default-steady-trim-20261115'


def check(folder,args):
    if args['stage']=='tests':
        import pytest
        suffix=('::test_other_operating_targets_retain_complete_residual_fallback' if args['case']=='fallback'
                else '::test_full_trim_border_and_all_matrix_columns_match_complete_residual['+args['case']+']' if args['case'] else '')
        selection='tests/test_trim_derivative_blocks.py'+suffix
        code=pytest.main(['-q','-p','no:cacheprovider',selection])
        assert code==0
        return {'selection':selection,'pytest_exit_code':int(code)}

    import numpy as np
    from unittest.mock import patch
    from openswing.bridge import dispatch
    from openswing.aero import evaluate_aerodynamics
    holder=[]
    def capture(net,tolerance,continuation_steps,initial_state,progress,**kwargs):
        assert initial_state is None
        holder.append(net)
        return {'captured_network':True}
    with patch('openswing.source_discrete._solve_source_network',side_effect=capture):
        dispatch(read(STUDY/'request.json'))
    assert len(holder)==1
    n=holder[0];x=np.zeros(n.size)
    initial=evaluate_aerodynamics(n.model,n.condition,n.meshes,frozen_influences=n.frozen_influences)
    physical=np.array([s['circulation'] for s in initial['strips'] if s['lifting']])
    x[n.gamma_start:n.operating_start]=n.circulation_basis.encode(physical)/n.gamma_scale
    if args['state']=='deflected':
        from openswing.equilibrium_state import restore
        x=restore(n,read(ROOT/'artifacts/daedalus-regular-mesh-20261114/trim-1/state.json'))
    factor=args['factor'];baseline=n.residual(x,factor).copy()
    np.testing.assert_allclose(n.residual(x,factor,detail=True)[0],baseline,rtol=1e-13,atol=1e-13)
    before=n.nfev;started=time.process_time()
    if args['stencil']=='fourth':
        import openswing.geometry_tangent as geometry
        original=geometry.geometry_columns
        def fourth_geometry(*values,**options):
            values=list(values)
            if len(values)>4:values[4]=3e-6
            else:options['step']=3e-6
            options['difference_order']=4
            return original(*values,**options)
        with patch.object(geometry,'geometry_columns',side_effect=fourth_geometry):
            matrix=n.jacobian(x,factor,_direct_geometry=True)
    else:matrix=n.jacobian(x,factor,_direct_geometry=True)
    elapsed=time.process_time()-started;calls=n.nfev-before
    assert n.geometry_derivative_diagnostics['geometry_columns']==6*n.nn
    assert n.circulation_derivative_diagnostics['method']=='direct fixed-geometry blocks'
    columns=sorted(set([6*i+j for i in range(0,n.nn,max(1,n.nn//12)) for j in (0,4)]
                       +list(range(6*(n.nn-1),6*n.nn))
                       +list(range(n.gamma_start,n.operating_start,max(1,n.ng//5)))
                       +list(range(n.operating_start,n.size))))
    if args['column'] is not None:columns=[args['column']]
    errors=[];fourth_errors=[];fourth_details=[];forward_errors=[];operating_forward_errors=[]
    full_baseline=n.residual(x,factor,detail=True)[0]
    for j in columns:
        h=3e-6*max(1.,abs(x[j]));p,m=x.copy(),x.copy();p[j]+=h;m[j]-=h
        rp,rm=n.residual(p,factor,detail=True)[0],n.residual(m,factor,detail=True)[0]
        expected=(rp-rm)/(2*h)
        errors.append(float(np.max(abs(matrix[:,j]-expected)/(1+abs(expected)))))
        if j<n.operating_start:
            pp,mm=x.copy(),x.copy();pp[j]+=2*h;mm[j]-=2*h
            fourth=(8*(rp-rm)-(n.residual(pp,factor,detail=True)[0]-n.residual(mm,factor,detail=True)[0]))/(12*h)
            fourth_errors.append(float(np.max(abs(matrix[:,j]-fourth)/(1+abs(fourth)))))
            row=int(np.argmax(abs(matrix[:,j]-fourth)/(1+abs(fourth))))
            fourth_details.append(dict(column=j,row=row,actual=float(matrix[row,j]),reference=float(fourth[row])))
        # Production Newton uses a forward local-geometry stencil and retains
        # its original operating-variable stencil. Compare against that exact
        # full-residual construction separately from higher-order derivatives.
        h=1e-6*max(1.,abs(x[j]));p=x.copy();p[j]+=h
        forward=(n.residual(p,factor,detail=True)[0]-full_baseline)/h
        forward_errors.append(float(np.max(abs(matrix[:,j]-forward)/(1+abs(forward)))))
        if j>=n.operating_start:operating_forward_errors.append(forward_errors[-1])
    direction_errors=[]
    for seed in ([] if args['column'] is not None else range(3)):
        direction=np.zeros(n.size);direction[:6*n.nn]=np.random.default_rng(seed).normal(size=6*n.nn)
        predicted=matrix@direction
        for h in (3e-6,1e-6):
            p,m,pp,mm=[n.residual(x+k*h*direction,factor,detail=True)[0] for k in (1,-1,2,-2)]
            expected=(8*(p-m)-(pp-mm))/(12*h)
            direction_errors.append(float(np.max(abs(predicted-expected)/(1+abs(expected)))))
    write(folder/'column-errors.json',dict(columns=columns,centered_errors=errors,
        changed_column_fourth_order_errors=fourth_errors,
        changed_column_details=fourth_details,geometry_diagnostics=n.geometry_derivative_diagnostics,
        full_forward_stencil_errors=forward_errors,
        unchanged_operating_forward_errors=operating_forward_errors,geometry_direction_errors=direction_errors))
    if args['stencil']=='fourth':
        assert max(fourth_errors)<2e-6,max(fourth_errors)
        assert max(direction_errors,default=0.)<2e-6,direction_errors
    else:assert max(forward_errors)<2e-6,max(forward_errors)
    assert max(operating_forward_errors,default=0.)<2e-6,operating_forward_errors
    np.testing.assert_array_equal(n.residual(x,factor),baseline)
    assert n.iteration_fields is None and n.tangent_influences is None
    return dict(factor=factor,state=args['state'],size=n.size,nodes=n.nn,assembly_cpu_seconds=elapsed,
        assembly_residual_calls=calls,checked_columns=columns,stencil=args['stencil'],
        maximum_forward_stencil_error=max(forward_errors),maximum_changed_column_error=max(fourth_errors),
        maximum_operating_forward_error=max(operating_forward_errors,default=0.),maximum_operating_centered_difference=max(errors),
        maximum_geometry_direction_error=max(direction_errors,default=0.),
        geometry=n.geometry_derivative_diagnostics,circulation=n.circulation_derivative_diagnostics,
        qualification='Actual default request at the stated jig or previously saved deformed trial state. Production mode requires agreement with full-residual forward stencils. Fourth mode requires fourth-order sampled geometry/circulation columns and three all-geometry directions at two steps. Unchanged operating columns retain their original forward stencil. All other differences are reported without being acceptance gates. No equilibrium solve.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag',required=True)
    parser.add_argument('--stage',choices=['tests','matrix'],required=True)
    parser.add_argument('--case',choices=['False','True','fallback'])
    parser.add_argument('--factor',type=float,choices=[0.,1.],default=0.)
    parser.add_argument('--column',type=int)
    parser.add_argument('--stencil',choices=['production','fourth'],default='production')
    parser.add_argument('--state',choices=['jig','deflected'],default='jig')
    args=vars(parser.parse_args())
    if args['stage']=='matrix':LIMITS.update(cpu_seconds=25,wall_seconds=45)
    else:LIMITS.update(wall_seconds=45)  # Keep the 15-CPU-second cap under variable host scheduling.
    inputs=[STUDY/'request.json',ROOT/'tests/test_trim_derivative_blocks.py',
        ROOT/'artifacts/daedalus-regular-mesh-20261114/trim-1/state.json',
        *[ROOT/'tests'/name for name in ['test_source_static_mechanical_tangent.py',
          'test_source_joints.py','test_source_coupled.py','test_source_fuselage.py']],
        *sorted((ROOT/'openswing').glob('*.py'))]
    run(STUDY,args['tag'],inputs,check,args,__file__)
