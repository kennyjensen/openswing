"""Source-equation stiffness contributions to verified Daedalus zeros.

All comparisons preserve the accepted mean state with an explicit affine
offset; these are local diagnostics, not retrimmed aircraft predictions.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from check_daedalus_transmission_zeros import STUDY,CHANNELS
from daedalus_bounded_job import run

FIXTURE=ROOT/'artifacts/daedalus-source-strain-20261114/capture/fixture.pkl'


def literal(folder,args):
    import pickle
    import numpy as np
    from openswing.asw import parse_asw
    model=parse_asw((ROOT/'examples/dae.asw').read_text(),beam_interpolation='drela-segspl-v1')
    beam=next(b for b in model.beams if b.index==4)
    stations=np.array([0.,.625,1.25,1.875,2.5])
    # Direct interpolation of the two literal endpoint rows, independently
    # of the parser's spline machinery and the historical report's summary.
    expected=5000*(10+10*(stations+6.5)/10.5)
    values={key:beam.value(key,stations) for key in ('EIcc','EInn','GJ')}
    for key in ('EIcc','EInn'):np.testing.assert_allclose(values[key],expected,rtol=2e-14,atol=1e-9)
    np.testing.assert_allclose(values['GJ'],25000,rtol=2e-14,atol=1e-9)
    with FIXTURE.open('rb') as stream:fixture=pickle.load(stream)
    mask=(fixture['beam']==4)&(fixture['station']>=0)&(fixture['station']<2.5)
    endpoints={key:fixture['material'][key][mask].tolist() for key in ('EIcc','EInn','GJ')}
    for key in ('EIcc','EInn'):
        assert abs(np.min(endpoints[key])-expected[0])<1e-8
        assert abs(np.max(endpoints[key])-expected[-1])<1e-8
    result=dict(stations_ft=stations.tolist(),literal_linear_bending_stiffness=expected.tolist(),
        parsed_stiffness={key:value.tolist() for key,value in values.items()},
        saved_full_model_endpoint_stiffness=endpoints,
        qualification='The earlier mounting-path Markdown table incorrectly stated constant EI=100000 over 0..2.5 ft. The parsed model and saved solver fixtures already use the varying literal values. This is a documentation correction, not a solver or aircraft-property change.')
    print(result,flush=True);return result


def analyze(folder,args):
    import pickle
    import numpy as np
    import scipy.sparse as sp
    from daedalus_source_strain_reference import Compatibility,GENERATORS
    with FIXTURE.open('rb') as stream:fixture=pickle.load(stream)
    ref=Compatibility(fixture);nn=len(fixture['positions']);ne=len(fixture['ends'])
    assert nn==108 and ne==103 and fixture['size']==2044
    assert max(abs(ref.residual()))<1e-9
    for key in ('EIcs','EIcn','EIsn','Cea','Nea','Cta','Nta'):
        assert np.max(abs(fixture['material'][key]))==0
    assert np.max(abs(ref.law-np.eye(6)[None,:,:]*ref.law))==0
    a=sp.load_npz(SOURCE/'assembled-6.7/A.npz')
    m=sp.load_npz(SOURCE/'assembled-6.7/M.npz')
    models=[]
    for tag in ('yaw-verify','roll-verify'):
        metadata=read(STUDY/tag/'result.json');value=complex(*metadata['zero'])
        with np.load(STUDY/tag/'arrays.npz') as saved:z=saved['state'];left=saved['left']
        pose=z[:6*nn].reshape(nn,6);internal=z[6*nn:6*(nn+ne)].reshape(ne,6)
        dr=fixture['L']*pose[:,:3];theta=pose[:,3:]
        dn=fixture['F']*internal[:,:3];dm=fixture['ML']*internal[:,3:]
        compatibility,_=ref.tangent(dr,theta,dn,dm)
        assert max(abs(compatibility-a[:6*ne]@z))<2e-8
        frames=np.einsum('nej,jkl->nekl',theta[[ref.a,ref.b]].transpose(1,0,2),GENERATORS)@ref.frame
        local_moment=np.einsum('nji,nj->ni',frames.mean(axis=1),ref.moment)+np.einsum('nji,nj->ni',ref.mean_frame,dm)
        material=.25*fixture['length'][:,None]*abs(local_moment)**2*np.diagonal(ref.law[:,3:,3:],axis1=1,axis2=2)
        beam=fixture['beam'];station=fixture['station']
        groups={'wing':beam==1,'stabilizer':beam==2,'fin':beam==3,
                'forward_boom':(beam==4)&(station<2.5),'aft_boom':(beam==4)&(station>=2.5),'fairing':beam==5}
        fractions={key:float(material[mask].sum()/material.sum()) for key,mask in groups.items()}
        models.append(dict(tag=tag,value=value,z=z,left=left,overlap=left@(m@z),
            arguments=(dr,theta,dn,dm),compatibility=compatibility,material_fractions=fractions))
    regions={'wing':fixture['beam']==1,'fin':fixture['beam']==3,
        'forward_boom':(fixture['beam']==4)&(fixture['station']<2.5),
        'nose_boom':(fixture['beam']==4)&(fixture['station']<0),
        'mount_span':(fixture['beam']==4)&(fixture['station']>=0)&(fixture['station']<2.5),
        'aft_boom':(fixture['beam']==4)&(fixture['station']>=2.5),
        'fairing':fixture['beam']==5}
    all_rows=[];maximum_action_error=0.;maximum_parameter_stencil_error=0.
    for region,mask in regions.items():
        for axis,property_name in enumerate(('EIcc','GJ','EInn')):
            # R_rot = geometric curvature - ds*C*M_local. Increasing one
            # stiffness changes C to C/(1+epsilon), hence
            # A(epsilon) = A + epsilon/(1+epsilon)*D exactly at this base.
            matrix=sp.lil_matrix((2044,2044))
            for i in np.flatnonzero(mask):
                coefficient=fixture['length'][i]*ref.law[i,3+axis,3+axis]
                row=6*i+3+axis
                matrix[row,6*nn+6*i+3:6*nn+6*i+6]=coefficient*fixture['ML']*ref.mean_frame[i,:,axis]
                skew=np.einsum('j,jkl->kl',ref.moment[i],GENERATORS)
                for end,node in enumerate(fixture['ends'][i]):
                    matrix[row,6*node+3:6*node+6]=.5*coefficient*(ref.frame[i,end,:,axis]@skew)
            matrix=matrix.tocsc();label=region+'-'+property_name
            sp.save_npz(folder/(label+'.npz'),matrix)
            for model in models:
                action=matrix@model['z'];original_law=ref.law.copy()
                ref.law[mask,3+axis,3+axis]=0
                changed,_=ref.tangent(*model['arguments']);ref.law=original_law
                expected=changed-model['compatibility']
                error=float(max(abs(action[:6*ne]-expected)))
                assert error<2e-10,(label,error)
                maximum_action_error=max(maximum_action_error,error)
                estimates=[]
                for step in (1e-3,5e-4):
                    variations=[]
                    for epsilon in (-step,step):
                        ref.law=original_law.copy();ref.law[mask,3+axis,3+axis]/=1+epsilon
                        tangent,_=ref.tangent(*model['arguments']);variations.append(tangent)
                    ref.law=original_law
                    estimate=(variations[1]-variations[0])/(2*step)
                    relative=float(np.linalg.norm(estimate-action[:6*ne])/max(np.linalg.norm(action[:6*ne]),1e-30))
                    estimates.append(relative)
                assert max(estimates)<2e-6,(label,estimates)
                maximum_parameter_stencil_error=max(maximum_parameter_stencil_error,max(estimates))
                derivative=model['left']@action/model['overlap']
                all_rows.append(dict(component=label,channel=model['tag'].split('-')[0],
                    zero_derivative=[float(derivative.real),float(derivative.imag)],
                    real_part_change_per_1_percent=float(.01*derivative.real),
                    frequency_hz_change_per_1_percent=float(.01*derivative.imag/(2*np.pi)),
                    independent_action_error=error,centered_parameter_derivative_errors=estimates))
    split_checks=[]
    for property_name in ('EIcc','GJ','EInn'):
        total=sp.load_npz(folder/('forward_boom-'+property_name+'.npz'))
        first=sp.load_npz(folder/('nose_boom-'+property_name+'.npz'))
        second=sp.load_npz(folder/('mount_span-'+property_name+'.npz'))
        difference=total-first-second;difference.eliminate_zeros();assert difference.nnz==0
        split_checks.append(property_name)
    result=dict(components=all_rows,material_strain_fractions={model['tag']:model['material_fractions'] for model in models},
        exact_forward_boom_partitions=split_checks,
        maximum_independent_action_error=maximum_action_error,maximum_centered_parameter_derivative_error=maximum_parameter_stencil_error,
        qualification='Exact partial stiffness changes in current source compatibility at a fixed mean state. Each varying stiffness retains a compensating affine residual offset. The positive material-strain quadratic excludes geometric/brace/fluid/inertial terms and is not modal energy. These are forced exponential zero states, not natural modes.')
    print('material fractions',result['material_strain_fractions'],flush=True)
    for tag in ('yaw','roll'):
        print(tag,sorted([r for r in all_rows if r['channel']==tag],key=lambda r:abs(complex(*r['zero_derivative'])),reverse=True)[:7],flush=True)
    return result


def perturb(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from scipy.sparse.linalg import LinearOperator,onenormest
    from openswing.harmonic_structure import ReusableBeamStructure
    source=read(STUDY/(args['zero']+'-verify')/'result.json');value=complex(*source['zero'])
    row=next(r for r in read(STUDY/'stiffness/result.json')['components']
             if r['channel']==args['zero'] and r['component']==args['component'])
    derivative=complex(*row['zero_derivative'])
    a,m=(sp.load_npz(SOURCE/'assembled-6.7'/name).tocsc() for name in ('A.npz','M.npz'))
    with np.load(SOURCE/'assembled-6.7/maps.npz') as saved:b=saved['B'][:,0];c=saved['C'][0 if args['zero']=='yaw' else 1]
    increment=sp.load_npz(STUDY/'stiffness'/(args['component']+'.npz'))
    for data in (m.data,m.indices,m.indptr):data.flags.writeable=False
    roots=[];slopes=[]
    for step in (1e-3,5e-4):
        pair=[]
        for epsilon in (-step,step):
            modified=(a+epsilon/(1+epsilon)*increment).tocsc()
            for data in (modified.data,modified.indices,modified.indptr):data.flags.writeable=False
            structure=ReusableBeamStructure(modified,m,np.r_[np.arange(618),np.arange(1266,1296)],
                np.arange(1266),np.arange(1384,2032),np.arange(1384,2032))
            s=value+epsilon*derivative;history=[]
            for iteration in range(5):
                k=(s*m-modified).tocsc();rows=np.maximum(abs(k).max(axis=1).toarray().ravel(),1e-30)
                rowed=sp.diags(1/rows)@k;columns=np.maximum(abs(rowed).max(axis=0).toarray().ravel(),1e-30)
                norm=float(abs(rowed@sp.diags(1/columns)).sum(axis=0).max());del rowed
                factor=structure.factor(modified,m,s,rows,columns)
                z=factor.solve(b/rows)/columns;dz=-factor.solve((m@z)/rows)/columns
                h=c@z;hp=c@dz;correction=h/hp
                inverse=LinearOperator(k.shape,matvec=factor.solve,matmat=factor.solve,
                    rmatvec=lambda x:factor.solve(x,trans='H'),rmatmat=lambda x:factor.solve(x,trans='H'),dtype=complex)
                reciprocal=1/(norm*onenormest(inverse,t=1));assert reciprocal>1e-12
                residual=float(max(abs(k@z-b)/rows));assert residual<1e-8
                history.append(dict(zero=[s.real,s.imag],output_magnitude=float(abs(h)),
                    newton_correction_magnitude=float(abs(correction)),reciprocal_condition=float(reciprocal),scaled_residual=residual))
                if abs(h)<2e-13 and abs(correction)<2e-10:break
                s-=correction
                assert s.imag>0 and abs(s-value)<.1
            else:raise AssertionError(history)
            pair.append(s);roots.append(dict(epsilon=epsilon,zero=[s.real,s.imag],history=history))
        slopes.append((pair[1]-pair[0])/(2*step))
    errors=[float(abs(s-derivative)/(1+abs(derivative))) for s in slopes]
    assert max(errors)<1e-4,errors
    result=dict(channel=args['zero'],component=args['component'],zero=[value.real,value.imag],
        predicted_derivative=[derivative.real,derivative.imag],centered_derivatives=[[s.real,s.imag] for s in slopes],
        normalized_centered_derivative_errors=errors,perturbed_zeros=roots,
        qualification='Four fresh full-descriptor transfer zeros at predetermined +/-0.1% and +/-0.05% stiffness changes, with exact compliance scaling and a fixed-equilibrium affine offset. Numerical derivative verification, not a physical parameter fit or a retrimmed aircraft.')
    print(result,flush=True);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['analyze','perturb','literal']);p.add_argument('--tag',required=True)
    p.add_argument('--zero',choices=['yaw','roll'],default='yaw');p.add_argument('--component',default='wing-EInn')
    args=vars(p.parse_args())
    inputs=[FIXTURE,ROOT/'examples/dae.asw',ROOT/'scripts/daedalus_source_strain_reference.py',ROOT/'scripts/check_daedalus_transmission_zeros.py',
        ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz')]
    for tag in ('yaw-verify','roll-verify'):inputs += [STUDY/tag/name for name in ('result.json','arrays.npz','terminal.json')]
    if args['stage']=='perturb':inputs += [STUDY/'stiffness'/name for name in ('result.json','terminal.json',args['component']+'.npz')]
    inputs += list((ROOT/'openswing').glob('*.py'))
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
