"""Bounded native AVL check of all four loaded Daedalus lifting surfaces.

No new trim or unsteady solve. Distinct physical components, native core law,
source core law and surface/force conventions remain explicitly separate.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT,SOURCE,read,write
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-coupled-avl-20261114'
AVL=ROOT/'artifacts/isae/avl-matched-fields-r1-20261108/avl-fields'


def analyze(folder,args):
    import importlib.util,subprocess,time
    from dataclasses import replace
    import numpy as np
    from check_daedalus_wing_paper import dynamic
    from openswing.aero import FlightCondition,evaluate_aerodynamics
    from openswing.frozen_influence import lifting_geometry
    from avl_vorvelc_reference import matrix as native_matrix
    spec=importlib.util.spec_from_file_location('_coupled_avl_fields',ROOT/'scripts/verify-avl-matched-fields.py')
    matched=importlib.util.module_from_spec(spec);spec.loader.exec_module(matched)
    system=dynamic();n=system.network;zero=np.zeros(system.size)
    state,_,options=system.physical_state(zero,zero,None)
    residual,data=n.residual(state.x,detail=True,**options);assert max(abs(residual))<1e-9
    meshes=[m for m in data['meshes'] if m.beam.lifting]
    assert [m.beam.index for m in meshes]==[1,2,3,5]
    model=replace(n.model,beams=[m.beam for m in meshes],records={});refs=model.reference
    np.testing.assert_array_equal(refs[1],refs[3])
    g=lifting_geometry(meshes,np.array([1.,0.,0.]))
    lines=['Daedalus loaded interacting surfaces','0','0 0 0',
        ' '.join(map(str,refs[0])),' '.join(map(str,refs[1])),'0']
    counts=[];normals=[];span=[];locations=[];beam_ids=[]
    for mesh in meshes:
        beam=mesh.beam;local=lifting_geometry([mesh],np.array([1.,0.,0.]))
        counts.append(len(mesh.tm));beam_ids.extend([beam.index]*len(mesh.tm))
        stations=np.r_[mesh.t0,mesh.t1[-1]]
        frames=np.concatenate([mesh.frame0,mesh.frame1[-1:]])
        quarters=np.concatenate([local['a'],local['b'][-1:]])
        lines+=['SURFACE',f'Loaded beam {beam.index}','1 0','COMPONENT',str(beam.physical_index)]
        def alpha(t):
            value=np.deg2rad(beam.value('alpha',t))
            for k,control in data['condition'].controls.items():value+=control*beam.value(f'dCLdF{k}',t)/beam.value('dCLda',t)
            return value
        for t,frame,quarter in zip(stations,frames,quarters):
            c,s,normal=frame.T;across=np.linalg.norm(np.cross([1.,0.,0.],s));chord=beam.value('chord',t)/across
            angle=alpha(t);normal=np.sin(angle)*c+np.cos(angle)*normal
            n0=np.cross([1.,0.,0.],s)/across;incidence=np.rad2deg(np.arctan2(normal[0],normal@n0))
            leading=quarter-[.25*chord,0.,0.]
            lines+=['SECTION',' '.join(f'{v:.17g}' for v in (*leading,chord,incidence))+' 1 0',
                'CLAF',f'{beam.value("dCLda",t)/(2*np.pi):.17g}']
        angle=alpha(mesh.tm)
        normals.extend(np.sin(angle)[:,None]*mesh.frames[:,:,0]+np.cos(angle)[:,None]*mesh.frames[:,:,2])
        span.extend(mesh.length[:,None]*mesh.frames[:,:,1])
        locations.extend(mesh.rm+((.25-beam.value('Xax',mesh.tm))*beam.value('chord',mesh.tm))[:,None]*mesh.frames[:,:,0])
    (folder/'model.avl').write_text('\n'.join(lines)+'\n')
    axis={'x':0,'y':1,'z':2}[args['axis']];rates=np.zeros(3);rates[axis]=args['rate']
    scale=refs[0,1] if axis==1 else refs[0,2];command={'x':'R','y':'P','z':'Y'}[args['axis']]
    alpha,beta=data['condition'].alpha,data['condition'].beta
    # Explicitly retain native defaults for different-component cores. The
    # kernel and radius differences are isolated in the subsequent replay.
    commands=f'LOAD model.avl\nOPER\nO\nA\nR\nCC 0\nCW 2\n\nA A {alpha:.17g}\nB B {beta:.17g}\n{command} {command} {args["rate"]*scale/2:.17g}\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n'
    (folder/'commands.txt').write_text(commands);started=time.monotonic()
    process=subprocess.run([str(AVL)],input=commands,text=True,capture_output=True,cwd=folder,timeout=8)
    (folder/'native-stdout.txt').write_text(process.stdout);(folder/'native-stderr.txt').write_text(process.stderr)
    write(folder/'native-terminal.json',dict(returncode=process.returncode,process_reaped=True,wall_seconds=time.monotonic()-started))
    assert process.returncode==0,process.stderr
    f=matched.read_fields(folder/'elements.txt');assert len(f['GAM'])==82==sum(counts)
    np.savez_compressed(folder/'native-fields.npz',**f)
    wind=data['condition'].vectors()[0]
    condition=FlightCondition(speed=1.,alpha=0.,beta=0.,mach=0.,density=1.,rates=tuple(rates),
        stall=False,freeze_influences=False,controls=data['condition'].controls,
        gust=dict(type='uniform',velocity=(wind-[1.,0.,0.]).tolist()))
    result=evaluate_aerodynamics(model,condition,meshes);write(folder/'openswing.json',result)
    np.testing.assert_allclose(f['VINF'],np.broadcast_to(wind,f['VINF'].shape),atol=2e-13,rtol=2e-13)
    for name,native in [('a','RV1'),('b','RV2')]:np.testing.assert_allclose(g[name],f[native],atol=2e-12,rtol=0)
    physical=g['physical'];fraction=np.where(physical[:,None]==physical[None,:],.0001,2.)
    cp=native_matrix(f['RC'],f['RV1'],f['RV2'],0.,core_fraction=fraction)
    hv=native_matrix(f['RV'],f['RV1'],f['RV2'],0.,core_fraction=fraction,exclude_self=True)
    free=f['VINF']+np.cross(f['RC']-refs[3],rates)
    operator=np.einsum('ijk,ik->ij',cp,f['ENC'])
    gamma=np.linalg.solve(operator,-np.sum(free*f['ENC'],axis=1));ngamma=f['GAM'].ravel()
    gamma_error=float(max(abs(gamma-ngamma))/max(abs(ngamma)))
    induced=np.einsum('ijk,j->ik',hv,ngamma);field_error=float(np.max(abs(induced-f['VV'])))
    assert gamma_error<1e-6 and field_error<1e-6,(gamma_error,field_error)
    velocity=f['VINF']+np.cross(f['RV']-refs[3],rates)+f['VV']
    force=ngamma[:,None]*np.cross(velocity,f['RV2']-f['RV1']);moment=np.cross(f['RV']-refs[1],force)
    labels=matched.NATIVE.labeled(folder/'total.txt')
    labels={name:value for key,values in labels.items() for name,value in zip(key.removeprefix('Trefftz Plane: ').split(', '),values)}
    coefficient=np.r_[force.sum(axis=0)*2/refs[0,0],moment.sum(axis=0)*2/refs[0,0]/refs[0,[2,1,2]]]
    expected=np.array([labels[k] for k in ('CXtot','CYtot','CZtot','Cltot','Cmtot','Cntot')])
    force_error=float(max(abs(coefficient-expected)));assert force_error<1e-10,force_error
    strips=result['strips'];pgamma=np.array([s['circulation'] for s in strips]);pv=np.array([s['relative_velocity'] for s in strips])
    pforce=pgamma[:,None]*np.cross(pv,np.array(span));pmoment=np.cross(np.array(locations)-refs[1],pforce)
    beam_ids=np.array(beam_ids);surfaces=[]
    for beam in (1,2,3,5):
        ids=beam_ids==beam
        surfaces.append(dict(beam=beam,native_wrench=np.r_[force[ids].sum(axis=0),moment[ids].sum(axis=0)].tolist(),
            openswing_wrench=np.r_[pforce[ids].sum(axis=0),pmoment[ids].sum(axis=0)].tolist()))
    np.savez_compressed(folder/'geometry.npz',**g,beam=beam_ids,normal=np.array(normals),force_vector=np.array(span),
        moment_location=np.array(locations),reference=refs,rates=rates,native_core_fraction=fraction)
    output=dict(axis=args['axis'],rate_rad_per_length=args['rate'],alpha_deg=alpha,beta_deg=beta,counts=counts,
        surfaces=surfaces,native_circulatory_wrench=np.r_[force.sum(axis=0),moment.sum(axis=0)].tolist(),
        openswing_circulatory_wrench=np.r_[pforce.sum(axis=0),pmoment.sum(axis=0)].tolist(),
        matched_coordinate_relative_gamma_error=gamma_error,matched_coordinate_max_field_error=field_error,
        native_force_reconstruction_error=force_error,
        geometry_max_errors={k:float(np.max(abs(g[k]-f[v]))) for k,v in [('a','RV1'),('b','RV2'),('hv','RV'),('cp','RC')]},
        qualifications=[
            'All four loaded lifting surfaces, distinct physical components, Mach zero, unit speed/density and fixed body-x wake. Bodies and engines omitted from both.',
            'Native cross-component core is two transverse strip widths with quartic regularization; source core is max(normal chord/4, material interval length) with Eq161 regularization.',
            'Native endpoint, receiver and normal export verifies its own operator. Source receiver, normal and force conventions remain separate.',
            'Rigid prescribed-rate aerodynamic comparison, not a full-aircraft trim, unsteady Bode solve, native ASWING pass or parameter fit.'])
    print(output,flush=True);return output


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True)
    parser.add_argument('--axis',choices=['x','y','z'],default='z');parser.add_argument('--rate',type=float,default=0.)
    args=vars(parser.parse_args())
    inputs=[AVL,ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'scripts/verify-avl-matched-fields.py',ROOT/'scripts/verify-avl-native-controls.py',ROOT/'scripts/avl_vorvelc_reference.py',
        ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',
        ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf']
    inputs += [ROOT/'reference/avl-native-20261108/source/AVL3.52rel09032025/src'/name for name in ('aic.f','aoper.f','avl.f')]
    inputs += list((ROOT/'openswing').glob('*.py'))
    run(STUDY,args['tag'],inputs,analyze,args,__file__)


if __name__=='__main__':main()
