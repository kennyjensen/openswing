"""Independent retained-field CASE10 replay; stdlib only, no physical solve."""
from pathlib import Path
from decimal import Decimal
import hashlib
import itertools
import json
import math

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
FOLDER=ROOT/'artifacts/isae/sa1-historical-case10-diagnostic-20261027'
U,RHO,S,C,A0=47.9,1.2256,5.9,1.,6.28
QS=.5*RHO*U*U*S
MODEL_SHA='6f7060c7e8676fc0d105026f1c6be1dcf0a3f266f8f9d5209773d4eba1778e6a'


def pin(path):
    p=Path(path); data=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def wpair(y,a,b,d):
    u,v=y-a,y-b
    if u==0 or v==0:raise ValueError('Receiver on trailing filament')
    if d==0:return (1/v-1/u)/(4*math.pi)
    return ((1+math.hypot(d,v)/d)/v-(1+math.hypot(d,u)/d)/u)/(4*math.pi)


def leakage(cl):
    def softplus(z):return max(z,0)+math.log1p(math.exp(-abs(z)))
    return .05*(softplus((cl-1.2)/.05)-softplus((-1.2-cl)/.05))


def dot(a,b):return math.fsum(x*y for x,y in zip(a,b))


def total(vectors):return [math.fsum(v[k] for v in vectors) for k in range(3)]


def decimal_interval(token):
    d=Decimal(token);h=Decimal(5).scaleb(d.as_tuple().exponent-1)
    return d-h,d+h


def native_inference(fields):
    v={k:d['value'] for k,d in fields.items()}
    a=math.radians(v['alpha']);s,c=math.sin(a),math.cos(a)
    cli=(-4*v['Cm']-v['CDi']*s)/c
    if v['CDi']<=0 or v['efficiency']<=0:
        return dict(CLi_from_Cm=cli,CLi_from_efficiency=None,
            efficiency_unavailable_reason='The zero-row efficiency token is a native placeholder; 0/0 is not a defined span efficiency.',
            CLprofile=v['CL']-cli,CDprofile=v['CD']-v['CDi'],
            circulation_integral_from_Cm=cli*U*S/2,
            independent_route_rounding_compatible=None)
    clie=math.sqrt(math.pi*5.9*v['efficiency']*v['CDi'])
    bounds={k:tuple(float(x) for x in decimal_interval(d['token'])) for k,d in fields.items()}
    # Exact extrema of implied Cm over the positive e,CDi box and alpha interval.
    moments=[]
    alo,ahi=map(math.radians,bounds['alpha'])
    for d,e in itertools.product(bounds['CDi'],bounds['efficiency']):
        l=math.sqrt(math.pi*5.9*e*d);angles=[alo,ahi]
        stationary=math.atan2(d,l)
        if alo<=stationary<=ahi:angles.append(stationary)
        moments.extend(-.25*(l*math.cos(a)+d*math.sin(a)) for a in angles)
    return dict(CLi_from_Cm=cli,CLi_from_efficiency=clie,CLi_route_difference=cli-clie,
        circulation_integral_from_Cm=cli*U*S/2,circulation_integral_from_efficiency=clie*U*S/2,
        CLprofile=v['CL']-cli,CDprofile=v['CD']-v['CDi'],
        Cm_from_efficiency_interval=[min(moments),max(moments)],Cm_printed_interval=list(bounds['Cm']),
        independent_route_rounding_compatible=max(min(moments),bounds['Cm'][0])<=min(max(moments),bounds['Cm'][1]))


def replay(path):
    packet=json.loads(path.read_text());job=packet['job'];r=packet['result'];condition=job['condition']
    assert packet['status']=='computed'
    assert condition['mach']==condition['beta']==0 and condition['freeze_influences'] is False
    assert condition['speed']==U and condition['density']==RHO
    assert condition['stall'] is True and condition['stall_factor']==40 and condition['stall_width']==.05
    n=job['panels'];raw=r['strips'];nodes=[x['t'] for x in r['mesh_discretization']['beams'][0]['nodes']]
    assert len(raw)==n and len(nodes)==n+1 and nodes[0]==-2.95 and nodes[-1]==2.95
    assert len(r['circulation_local_residual'])==len(r['circulation_residual'])==n
    alpha=math.radians(condition['alpha']);sa,ca=math.sin(alpha),math.cos(alpha)
    e=[ca,0.,sa];ell=[-sa,0.,ca];gamma=[s['circulation'] for s in raw]
    force=[];moment=[];profile=[];lift=[];residual=[];whs=[]
    errors={k:[] for k in ('velocity','cl','strip_force','strip_moment','geometry','trefftz_velocity','trefftz_strip_drag')}
    for i,s in enumerate(raw):
        y=s['t'];ds=nodes[i+1]-nodes[i]
        wh=math.fsum(g*wpair(y,a,b,0.) for g,a,b in zip(gamma,nodes,nodes[1:]))
        wc=math.fsum(g*wpair(y,a,b,C*A0/(4*math.pi)) for g,a,b in zip(gamma,nodes,nodes[1:]))
        speed=math.hypot(U,wh);cl=2*gamma[i]/(C*speed);vn=U*sa+wc*ca
        residual.append((vn-speed/A0*40*leakage(cl))/U)
        v=[U*e[k]+wh*ell[k] for k in range(3)]
        fl=[RHO*gamma[i]*(U*ell[k]-wh*e[k])*ds for k in range(3)]
        scale=RHO*C*(.5*(.00352562+.00771413)*speed+2*vn*vn/speed)*ds
        fp=[scale*x for x in v];f=[x+y for x,y in zip(fl,fp)];my=-.25*fl[2]
        force.append(f);moment.append([y*f[2],my,-y*f[0]]);profile.append(fp);lift.append(fl);whs.append(wh)
        errors['velocity'].extend(abs(a-b) for a,b in zip(v,s['relative_velocity']))
        errors['cl'].append(abs(cl-s['cl']))
        errors['strip_force'].extend(abs(a-b) for a,b in zip(f,s['force']))
        errors['strip_moment'].append(abs(my-s['moment'][1]))
        errors['geometry'].extend(abs(a-b) for a,b in zip(s['velocity_position'],[.25*ca,y,.25*sa]))
        errors['geometry'].append(abs(ds-s['length']))
        errors['trefftz_velocity'].extend(abs(2*wh*x-y) for x,y in zip(ell,r['trefftz']['velocity_body'][i]))
        errors['trefftz_strip_drag'].append(abs(-RHO*gamma[i]*wh*ds-r['trefftz']['strip_induced_drag'][i]))
    f,m,fp,fl=map(total,[force,moment,profile,lift])
    G=math.fsum(g*(b-a) for g,a,b in zip(gamma,nodes,nodes[1:]))
    cli=2*G/(U*S);cdi=-2*math.fsum(g*w*(b-a) for g,w,a,b in zip(gamma,whs,nodes,nodes[1:]))/(U*U*S)
    values=dict(lift=dot(f,ell),drag=dot(f,e),CL=dot(f,ell)/QS,CD=dot(f,e)/QS,
        CLi=cli,CDi=cdi,CDi_near=dot(fl,e)/QS,CDp=dot(fp,e)/QS,Cm=m[1]/QS,
        efficiency=cli*cli/(math.pi*5.9*cdi) if cdi>0 else None)
    differences={k:max(v,default=0.) for k,v in errors.items()}
    differences.update(local_residual=max(abs(a-b) for a,b in zip(residual,r['circulation_local_residual'])),
        projected_residual=max(abs(a-b) for a,b in zip(residual,r['circulation_residual'])),
        integrated_force=max(abs(a-b) for a,b in zip(f,r['force'])),integrated_moment=max(abs(a-b) for a,b in zip(m,r['moment'])))
    comparisons={}
    for key,pred in values.items():
        retained=dot(r['force'],ell if key=='lift' else e) if key in ('lift','drag') else r[key]
        comparisons[key]=dict(oracle=pred,retained=retained,absolute_difference=abs(pred-retained) if pred is not None and retained is not None else None,
            both_undefined=pred is None and retained is None)
    fields=job['reference_row']['fields']
    def reference_checks(predictions):
        checks=[]
        for key in ('lift','drag','CL','CD','CDi','Cm','efficiency'):
            expected=Decimal(fields[key]['token']);bounds=decimal_interval(fields[key]['token']);pred=predictions[key]
            available=pred is not None
            error=abs(Decimal(str(pred))-expected) if available else None
            tol=(bounds[1]-bounds[0])/2
            checks.append(dict(name=key,predicted=pred,expected_token=fields[key]['token'],absolute_error_decimal=str(error) if available else None,
                tolerance_decimal=str(tol),available=available,passed=bool(available and error<=tol),
                unavailable_reason=None if available else 'Zero-lift/zero-induced-drag efficiency is undefined. Native token retained without fabricating a prediction.'))
        return checks
    checks=reference_checks({k:v['retained'] for k,v in comparisons.items()})
    oracle_checks=reference_checks(values)
    native=native_inference(fields)
    current_inference=dict(circulation_integral=G,CLprofile=values['CL']-cli,CDprofile=values['CD']-cdi,
        CLi_relative_difference=cli/native['CLi_from_Cm']-1 if native['CLi_from_Cm'] else None,
        CDi_relative_difference=cdi/fields['CDi']['value']-1 if fields['CDi']['value'] else None,
        profile_lift_difference=(values['CL']-cli)-native['CLprofile'],
        profile_drag_difference=(values['CD']-cdi)-native['CDprofile'],
        uniform_theta_Fourier_endpoint_integral_factor=math.cos(math.pi/(2*n)),
        uniform_theta_Fourier_endpoint_Cli=cli*math.cos(math.pi/(2*n)))
    return dict(source=pin(path),job=job,values=comparisons,maximum_absolute_differences=differences,
        native_inference=native,current_inference=current_inference,independent_reference_checks=checks,
        oracle_reference_checks=oracle_checks)


def main():
    protocol=json.loads((FOLDER/'protocol.json').read_text());summary=json.loads((FOLDER/'summary.json').read_text())
    assert len(summary)==len(protocol['jobs'])==22
    for record in protocol['sources']+[protocol['parser_pin']]:assert pin(ROOT/record['path'])==record
    assert protocol['sources'][0]['sha256']==MODEL_SHA
    for path,sha in protocol['kernel_sha256'].items():assert pin(ROOT/path)['sha256']==sha
    cases=[replay(FOLDER/(job['id']+'.json')) for job in protocol['jobs']]
    assert {(c['job']['reference_row']['row_index'],c['job']['panels']) for c in cases}=={(i,n) for i in range(11) for n in (40,80)}
    text=(ROOT/protocol['sources'][2]['path']).read_text().splitlines()
    for case in cases:
        row=case['job']['reference_row'];assert text[row['line_number']-1].split()==row['tokens']
        assert case['job']==next(j for j in protocol['jobs'] if j['id']==case['job']['id'])
    checks=[v for c in cases for v in c['independent_reference_checks']]
    accounting=dict(slots=len(checks),finite=sum(c['available'] for c in checks),matches=sum(c['passed'] for c in checks),
        finite_failures=sum(c['available'] and not c['passed'] for c in checks),unavailable=sum(not c['available'] for c in checks))
    assert accounting==dict(slots=154,finite=152,matches=12,finite_failures=140,unavailable=2)
    oracle_checks=[v for c in cases for v in c['oracle_reference_checks']]
    oracle_accounting=dict(slots=len(oracle_checks),finite=sum(c['available'] for c in oracle_checks),matches=sum(c['passed'] for c in oracle_checks),
        finite_failures=sum(c['available'] and not c['passed'] for c in oracle_checks),unavailable=sum(not c['available'] for c in oracle_checks))
    assert oracle_accounting==dict(slots=154,finite=152,matches=10,finite_failures=142,unavailable=2)
    boundary_differences=[dict(job=c['job']['id'],retained=a,oracle=b) for c in cases for a,b in zip(c['independent_reference_checks'],c['oracle_reference_checks']) if a['passed']!=b['passed']]
    assert len(boundary_differences)==2 and all(d['retained']['name']=='CD' for d in boundary_differences)
    assert all(c['native_inference']['independent_route_rounding_compatible'] for c in cases if c['job']['condition']['alpha']!=0)
    original=ROOT/'docs/validation/sa1-load-consistency-20261027/report.json'
    prior=json.loads(original.read_text());low=prior['rows'][1]['meshes'][1]
    new=next(c for c in cases if c['job']['id']=='row001-n40')
    old_bias=low['CLi_relative_difference'];new_bias=new['current_inference']['CLi_relative_difference']
    paths=[FOLDER/n for n in ('protocol.json','summary.json','driver.py','driver-resume.py')]+sorted((FOLDER/'initial-errors').glob('*.json'))
    report=dict(status='COMPLETE_SAVED_FIELD_REPLAY_NO_CONFIRMED_OPERATOR_DEFECT',
        scope=dict(original_SA1_registered_comparison_unchanged='19/154',historical_filename_paired_rows=11,historical_mesh_jobs=22,
            native_scalar_targets=77,new_physical_solves_by_this_audit=0,production_imports=0,production_changes=0,
            literal_slope=A0,control_point_offset=C*A0/(4*math.pi)),
        source_pins=protocol['sources'],evidence_pins=[pin(p) for p in paths]+[pin(Path(__file__)),pin(original),pin(ROOT/'.reference/asw_theory.txt'),pin(HERE/'initial-oracle.py'),pin(HERE/'initial-attempt.json')],
        source_kernel_validation=dict(all_original_source_pins_match=True,parser_pin_matches=True,kernel_pins_match=True,kernel_files=len(protocol['kernel_sha256']),
            all_22_job_declarations_and_original_rows_preserved=True),
        historical_execution_accounting=dict(original_physical_calls=22,successful_nonzero_packets_reused=20,zero_packets_rerun=2,total_physical_calls=24,
            zero_packet_first_failure='Diagnostic float(None) serialization of legitimate undefined efficiency; original error packets and both driver versions retained.',
            root_reported_initial_exit=1,root_reported_resume_exit=0,root_reported_resume_terminal_chunk='b113f2',
            qualification='Process totals/terminal handles are root-reported. This saved-field audit independently verifies retained packets and arithmetic, not OS process lifecycle.'),
        independent_diagnostic_accounting=accounting,oracle_reference_accounting=oracle_accounting,
        roundoff_boundary_differences=boundary_differences,
        exact_zero_profile_drag=dict(decimal_sum=str(Decimal('0.00352562')+Decimal('0.00771413')),
            original_token='0.112398E-01',absolute_error_decimal='5E-8',original_tolerance_decimal='5E-8',
            inclusive_boundary_match=True,scope='Analytical source-law diagnostic only; does not replace either retained or independently summed floating-point value.'),
        cases=cases,
        maximum_absolute_differences={k:max(c['maximum_absolute_differences'][k] for c in cases) for k in cases[0]['maximum_absolute_differences']},
        maximum_coefficient_difference=max(v['absolute_difference'] for c in cases for k,v in c['values'].items() if k not in ('lift','drag') and v['absolute_difference'] is not None),
        low_incidence_cross_archive_diagnostic=dict(historical_CASE10_requested_nodes=40,original_SA1_requested_nodes=200,
            historical_CASE10_slope=6.28,original_SA1_slope=6.2832,historical_alpha=1.,original_alpha=1.9971,
            CASE10_Cli_relative_error_at_40_intervals=new_bias,original_SA1_Cli_relative_error_at_400_intervals=old_bias,
            error_ratio=new_bias/old_bias,node_count_ratio=5.,
            qualification='Each relative error compares its own literal model/table pairing. Different historical models, startup, basis and actual node arrays prevent treating the ratio as an identified convergence law.'),
        qualifications=[
            'The scalar replay uses actual wind-aligned horseshoes and h=6.28/(4*pi), retaining the historical model byte-for-byte.',
            'The native zero-incidence efficiency token0 is retained, but the current/oracle ratio0/0 is unavailable; it is not snapped to zero or counted as a match.',
            'Independent floating-point aggregation straddles the native half-place CD boundary at both zero rows. Retained scalar comparisons give12 matches; oracle aggregation gives10. Both are preserved; exact decimal Cdf+Cdp lies on the inclusive boundary. No comparison tolerance is expanded.',
            'All10 nonzero native moment/efficiency/CDi identities are compatible with printed intervals. Native Gamma and local force arrays remain unrecorded.',
            'The stronger low-angle CLi bias associated with NODE/I40 is consistent with a resolution-dependent historical integration/discretization effect, but does not identify force quadrature rather than circulation representation or mesh placement.',
            'The simple uniform-theta Fourier endpoint alternative multiplies circulation lift by cos(pi/(2*N)); it is a derived diagnostic, not an adopted historical force rule.',
            'NODE requests nodes, whereas40/80 are prospectively declared current interval reconstructions; exact historical arrays and defaults are not recovered.',
            'This historical diagnostic never changes the original SA1 model, registry denominator or19/154 result.'
        ])
    target=HERE/'report.json'
    if target.exists():raise FileExistsError('Existing diagnostic receipt is immutable.')
    target.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(output=str(target),accounting=accounting,maximum_absolute_differences=report['maximum_absolute_differences'],maximum_coefficient_difference=report['maximum_coefficient_difference']),indent=2))


if __name__=='__main__':main()
