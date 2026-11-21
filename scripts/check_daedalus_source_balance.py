"""Bounded current full-aircraft force/moment and load-transfer comparison."""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from check_daedalus_circulation_phase import restore,dump,REFERENCE
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-source-balance-20261114'
AERO=ROOT/'artifacts/daedalus-circulation-phase-20261114'
SAVED=ROOT/'artifacts/daedalus-load-sensitivity-20261113'
CASES={'slow':(.2,'slow-animation'),'dip':(1.15737773741517,'reference-dip')}


def capture(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from openswing.frequency_response import HarmonicInput
    system=dynamic();n=system.network;zero=np.zeros(system.size)
    assert not n.loads and not n.gravity_override and not n.tension_only and not n.hinges
    assert not np.any(n.offa) and not np.any(n.offb) and not np.any(n.damping_times)
    assert not np.any(system.Omega0) and not np.any(system.Udot0) and not np.any(system.Omegadot0)
    original=n.residual;latest={}
    def recorded(*a,**kw):
        detail=kw.pop('detail',False);res,data=original(*a,detail=True,**kw);latest['data']=data
        return (res,data) if detail else res
    def sample(z,dz,forcing):
        n.residual=recorded
        try:res,state,options=system.residual(z,dz,detail=True,forcing=forcing)
        finally:n.residual=original
        data=latest['data'];motion=data['motion']
        return dict(residual=res,force=data['force'],moment=data['moment'],gravity=data['gravity'],
            r=state.r,Q=state.Q,u=state.u,w=state.w,U=state.U,Omega=state.Omega,
            orientation=state.orientation,acceleration=motion.at(np.zeros(3),n.model.reference[2]),
            angular_acceleration=motion.angular_acceleration)
    base=sample(zero,zero,None);data=latest['data'];assert max(abs(base['residual']))<1e-9
    aero=restore(AERO/'capture-base/base.pkl')['fixture']
    np.testing.assert_array_equal(aero['loaded_base']['r'],system.r0)
    np.testing.assert_array_equal(aero['loaded_base']['Q'],system.Q0)
    r,Q,N,M,reactions,gamma=n.unpack(system.base)
    samples=[]
    for mesh in n.meshes:
        beam=mesh.beam;sl=n.beam_elements[beam.index]
        values={key:[] for key in ('a','b','node','frames','ds','weight_density','cg_local','icc_weight_density','inn_weight_density')}
        for prefix in ('','D'):
            for t,side,node,frame in [(mesh.t0,'right',n.a[sl],system.Q0[n.a[sl]]@n.R0a[sl]),
                (mesh.t1,'left',n.b[sl],system.Q0[n.b[sl]]@n.R0b[sl])]:
                row=dict(a=n.a[sl],b=n.b[sl],node=node,frames=frame,ds=mesh.length,
                    weight_density=beam.value(prefix+'mg',t,side=side),
                    cg_local=np.c_[beam.value(prefix+'Ccg',t,side=side),np.zeros(len(t)),beam.value(prefix+'Ncg',t,side=side)],
                    icc_weight_density=beam.value(prefix+'mgcc',t,side=side),inn_weight_density=beam.value(prefix+'mgnn',t,side=side))
                for key,value in row.items():values[key].append(value)
        entry={key:np.concatenate(value) for key,value in values.items()}
        entry.update(beam=beam.index,node_positions=r,gravity=base['gravity'],base_velocity=system.U0,
            g_constant=np.array(n.model.constants[0]),moment_reference=np.array(n.model.reference[1]))
        samples.append(entry)
    constraints=[dict(kind=c['kind'],type=c['type'],a=c['a'],b=c['b'],slice=[c['sl'].start,c['sl'].stop]) for c in n.constraints]
    assert all(c['type']==0 for c in constraints)
    fixture=dict(aero=aero,layout=read(SOURCE/'mass-6.7/layout.json'),mass_samples=samples,constraints=constraints,
        struts=[dict(row=row,node=n.node(*row[:2])) for row in n.struts],jig_positions=n.rj,
        acceleration_scale=system.Ascale,
        base=dict(r=r,Q=Q,N=N,M=M,reactions=reactions,U=system.U0,gravity=base['gravity'],attitude_deg=system.attitude))
    dump(folder/'fixture.pkl',fixture);np.savez_compressed(folder/'base-targets.npz',**base)
    frequency,tag=CASES[args['case']];omega=2*np.pi*frequency
    z=np.load(SAVED/tag/'arrays.npz')['state'];rate=1j*omega*z
    forcing,_=HarmonicInput(system,'control.3',0).at_frequency(omega)
    widths=[]
    for step in (1e-3,5e-4):
        out={key:np.zeros_like(value,dtype=complex) for key,value in base.items()}
        for part,component in enumerate((np.real,np.imag)):
            for offset,weight in [(-2,1),(-1,-8),(1,8),(2,-1)]:
                h=offset*step;value=sample(h*component(z),h*component(rate),forcing(part,h))
                for key in out:out[key]+=(weight/(12*step))*(1 if part==0 else 1j)*value[key]
        widths.append(out)
    errors={key:float(np.max(abs(widths[0][key]-widths[1][key]))) for key in base}
    assert max(errors.values())<2e-6,errors
    a,m=(sp.load_npz(SOURCE/'assembled-6.7'/name) for name in ('A.npz','M.npz'));maps=np.load(SOURCE/'assembled-6.7/maps.npz')
    action=a@z-m@rate+maps['B'][:,0]
    difference=float(max(abs(action-widths[-1]['residual'])));assert difference<2e-8,difference
    np.savez_compressed(folder/'arrays.npz',state=z,rate=rate,matrix_action=action,output=maps['C']@z,
        **{'wide_'+key:value for key,value in widths[0].items()},**{'fine_'+key:value for key,value in widths[1].items()})
    return dict(frequency_hz=frequency,base_residual=float(max(abs(base['residual']))),
        width_errors=errors,matrix_action_comparison=difference,full_matrix_residual=float(max(abs(action))),
        native_evaluations=17,scope='Current source force/moment, rigid constraints and kinematics. Beam compatibility is captured but not independently evaluated by this study.')


def compare(actual,expected,atol=2e-6,rtol=2e-7):
    import numpy as np
    a,b=np.asarray(actual),np.asarray(expected);assert a.shape==b.shape
    error=abs(a-b);gate=atol+rtol*abs(b)
    assert np.isfinite(error).all() and np.all(error<=gate),(float(error.max()),a.shape)
    return dict(max_absolute=float(np.max(error,initial=0)),max_gate_ratio=float(np.max(error/gate,initial=0)))


def analyze(folder,args):
    import numpy as np
    from daedalus_source_aero_reference import FullAeroReference
    from daedalus_source_balance_reference import chart,inertia,aerodynamic_transfer,mechanics,wrench,derivative_wrench
    from elastic_fin_kinematics import logarithm
    source=STUDY/('capture-'+args['case']);fixture=restore(source/'fixture.pkl');layout=fixture['layout']
    base=fixture['base'];saved=np.load(source/'arrays.npz');native_base=np.load(source/'base-targets.npz')
    z=saved['state'];frequency=CASES[args['case']][0];d=chart(fixture,z,frequency)
    checks={};checks['base_orientation']=compare(d['orientation'],native_base['orientation'],2e-12,2e-12)
    raw_chart=dict(r=d['dr'],Q=d['dQ'],u=d['u'],w=d['w'],U=d['U'],Omega=d['Omega'],
        gravity=d['dg'],acceleration=d['a'],angular_acceleration=d['alpha'])
    raw_chart['orientation']=d['orientation']@np.array([[0,-d['frame_angle'][2],d['frame_angle'][1]],
        [d['frame_angle'][2],0,-d['frame_angle'][0]],[-d['frame_angle'][1],d['frame_angle'][0],0]])
    for key,value in raw_chart.items():checks['chart_'+key]=compare(value,saved['fine_'+key],2e-8,2e-8)
    old=restore(AERO/'capture-base/base.pkl');ref=FullAeroReference(fixture['aero'],old['packet'],quadrature=32)
    base_air=ref.evaluate(ref.base);previous_base=dict(np.load(AERO/'source-base-q32/arrays.npz'))
    checks['saved_aero_base']=dict(max_absolute=max(float(np.max(abs(v-previous_base[k]))) for k,v in base_air.items()))
    assert checks['saved_aero_base']['max_absolute']<2e-10
    gs=layout['circulation']['start'];ng=layout['circulation']['width'];gamma=layout['circulation']['scale']*z[gs:gs+ng]
    controls=np.zeros(len(ref.control_ids),complex);controls[ref.control_ids.index(3)]=1
    aero_direction=dict(r=d['dr'],Q=d['dQ'],u=d['u'],w=d['w'],udot=1j*d['omega']*d['u'],
        wdot=1j*d['omega']*d['w'],gamma=gamma,gamma_dot=1j*d['omega']*gamma,
        U=d['U'],Omega=d['Omega'],acceleration=d['a'],angular_acceleration=d['alpha'],
        controls=controls,powers=np.zeros(len(ref.power_ids),complex))
    answers=[]
    for step in (1e-24,1e-20):
        answer={key:np.zeros_like(value,dtype=complex) for key,value in base_air.items()}
        for part,component in enumerate((np.real,np.imag)):
            physical={key:value.astype(complex)+1j*step*component(aero_direction[key]) for key,value in ref.base.items()}
            value=ref.evaluate(physical)
            for key in answer:answer[key]+=(1 if part==0 else 1j)*value[key].imag/step
        answers.append(answer)
    derivative_air=answers[-1]
    checks['aero_complex_width']=dict(max_absolute=max(float(np.max(abs(answers[0][k]-v))) for k,v in derivative_air.items()))
    assert checks['aero_complex_width']['max_absolute']<2e-10
    previous=[dict(np.load(AERO/('source-'+args['case']+'-'+part+'-q32')/'arrays.npz')) for part in ('real','imag')]
    checks['previous_chart_aero']=dict(max_absolute=max(float(np.max(abs(v-(previous[0][k]+1j*previous[1][k])))) for k,v in derivative_air.items()))
    assert checks['previous_chart_aero']['max_absolute']<2e-6
    mass=inertia(fixture,d);air=aerodynamic_transfer(fixture,d,base_air,derivative_air);mech=mechanics(fixture,d)
    r=base['r'];origin=fixture['aero']['reference'][1];nn=layout['nodes'];ne=layout['elements']
    F=layout['internal_loads']['force_scale'];ML=layout['internal_loads']['moment_scale'];L=ML/F
    wrench_scales=np.array([F]*3+[ML]*3)
    f0=air['base_force']+mass['base_force'].sum(axis=0);m0=air['base_moment']+mass['base_moment'].sum(axis=0)
    df=air['force']+mass['force'].sum(axis=0);dm=air['moment']+mass['moment'].sum(axis=0)
    checks['base_external_force']=compare(f0,native_base['force'])
    checks['base_external_moment']=compare(m0,native_base['moment'])
    for width in ('wide','fine'):
        checks[width+'_external_force']=compare(df,saved[width+'_force'])
        checks[width+'_external_moment']=compare(dm,saved[width+'_moment'])
    air_wrench=derivative_wrench(r,d['dr'],air['base_force'],air['force'],air['moment'],origin)
    checks['air_transfer_conservation']=compare(air_wrench,np.r_[derivative_air['total_force'],derivative_air['total_moment']],2e-10,2e-10)
    mass_wrench=derivative_wrench(r,d['dr'],mass['base_force'].sum(axis=0),mass['force'].sum(axis=0),mass['moment'].sum(axis=0),origin)
    checks['mass_partition_conservation']=compare(mass_wrench,mass['parts'].sum(axis=(0,1)),2e-10,2e-10)
    expected=np.zeros(len(z),complex);expected_base=np.zeros(len(z))
    force_rows=slice(6*ne,6*ne+3*nn);moment_rows=slice(6*ne+3*nn,6*(ne+nn))
    expected[force_rows]=(df+mech['force'].sum(axis=0)).ravel()/F
    expected[moment_rows]=(dm+mech['moment'].sum(axis=0)).ravel()/ML
    expected_base[force_rows]=(f0+mech['base_force'].sum(axis=0)).ravel()/F
    expected_base[moment_rows]=(m0+mech['base_moment'].sum(axis=0)).ravel()/ML
    cr=slice(layout['reactions']['start'],gs)
    expected[cr]=mech['constraints'];base_constraints=[]
    for c in fixture['constraints']:
        i,j=c['a'],c['b']
        if j is None:value=np.r_[(r[i]-fixture['jig_positions'][i])/L,logarithm(base['Q'][i])]
        else:value=np.r_[(r[j]-r[i]-base['Q'][i]@(fixture['jig_positions'][j]-fixture['jig_positions'][i]))/L,
                         logarithm(base['Q'][i].T@base['Q'][j])]
        base_constraints.append(value)
    expected_base[cr]=np.concatenate(base_constraints)
    expected[gs:gs+ng]=derivative_air['circulation_local_residual'];expected_base[gs:gs+ng]=base_air['circulation_local_residual']
    op=layout['operating']['start'];expected[op:op+6]=(air_wrench+mass_wrench)/wrench_scales
    expected_base[op:op+6]=wrench(r,f0,m0,origin)/wrench_scales
    expected[layout['network_size']:]=d['kinematics']
    selected=np.arange(6*ne,len(z));assert len(selected)==1426
    checks['base_selected_rows']=compare(expected_base[selected],native_base['residual'][selected],2e-8,2e-8)
    for width in ('wide','fine'):
        checks[width+'_selected_rows']=compare(expected[selected],saved[width+'_residual'][selected],2e-8,2e-8)
    checks['matrix_action']=compare(expected[selected],saved['matrix_action'][selected],2e-8,2e-8)
    checks['selected_harmonic_closure']=dict(max_absolute=float(max(abs(expected[selected]))))
    assert checks['selected_harmonic_closure']['max_absolute']<2e-8
    checks['beam_internal_conservation']=compare(mech['wrenches'][0]/wrench_scales,np.zeros(6),2e-10,0)
    checks['joint_internal_conservation']=compare(mech['wrenches'][1]/wrench_scales,np.zeros(6),2e-10,0)
    checks['strut_anchor_cancellation']=compare((mech['wrenches'][3]+mech['anchor_wrench'])/wrench_scales,np.zeros(6),2e-10,0)
    checks['ground_anchor_balance']=compare((mech['wrenches'][2]-mech['anchor_wrench'])/wrench_scales,np.zeros(6),2e-8,0)
    np.savez_compressed(folder/'arrays.npz',expected_residual=expected,expected_base_residual=expected_base,selected_rows=selected,
        external_force=df,external_moment=dm,base_external_force=f0,base_external_moment=m0,
        aerodynamic_wrench=air_wrench,real_inertia_wrench=mass_wrench,aero_group_wrenches=air['group_wrenches'],
        mass_equation_wrenches=mass['parts'],mechanical_wrenches=mech['wrenches'],anchor_wrench=mech['anchor_wrench'],
        mass_node_force=mass['force'],mass_node_moment=mass['moment'],air_node_force=air['force'],air_node_moment=air['moment'])
    def record(v):return dict(real=v.real.tolist(),imag=v.imag.tolist())
    result=dict(frequency_hz=frequency,checks=checks,checked_rows=1426,omitted_rows=618,
        omitted_scope='Beam constitutive/compatibility equations; this study checks their resulting internal-wrench conservation but does not independently evaluate curvature/strain compatibility.',
        independent_aero_evaluations=ref.evaluations,mass_groups=mass['labels'],aero_groups=air['labels'],mechanical_groups=mech['labels'],
        aerodynamic_wrench=record(air_wrench),inertia_gravity_wrench=record(mass_wrench),
        external_balance=record(air_wrench+mass_wrench),mechanical_wrenches=record(mech['wrenches']),
        mass_weight_lb=float(sum(np.sum(s['weight_density']*s['ds']/2) for s in fixture['mass_samples'])+
                             sum(row['row'][5] for row in fixture['aero']['attachments']['weight'])),
        qualification='Independent current-source external loads, conservative beam/joint/brace transfer, gravity/frame chart, nodal/free-flight balances and kinematic rows along supplied harmonic states. Parsed endpoint material, topology, source averaging, state and internal resultants remain inputs. Not a native-ASWING Bode match or independent aircraft response.')
    print(dict(frequency=frequency,checks=checks,external_balance=result['external_balance']),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['capture','analyze'])
    parser.add_argument('--case',choices=CASES,required=True);parser.add_argument('--tag',required=True)
    args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'scripts/check_daedalus_circulation_phase.py',ROOT/'scripts/wing_inertia_reference.py',
        ROOT/'scripts/daedalus_source_balance_reference.py',ROOT/'examples/dae.asw',
        ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',
        SOURCE/'mass-6.7/layout.json',SAVED/CASES[args['case']][1]/'arrays.npz',AERO/'capture-base/base.pkl',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz')]
    inputs += [ROOT/'scripts'/name for name in REFERENCE]+list((ROOT/'openswing').glob('*.py'))
    if args['stage']=='analyze':
        inputs += [STUDY/('capture-'+args['case'])/name for name in ('fixture.pkl','base-targets.npz','arrays.npz','result.json','terminal.json')]
        inputs += [AERO/'capture-base/base.pkl',AERO/'source-base-q32/arrays.npz']
        for part in ('real','imag'):inputs += [AERO/('source-'+args['case']+'-'+part+'-q32')/'arrays.npz']
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
