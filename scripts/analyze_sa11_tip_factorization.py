"""Collect the verified factorization and all eight Fourier diagnostic outcomes."""
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/sa11-tip-factorization-20261108'
FOURIER=ROOT/'artifacts/isae/sa11-tip-fourier-r2-20261108'
LOCAL=ROOT/'artifacts/isae/sa11-tip-local-mesh-20261108'
BASE=ROOT/'artifacts/isae/sa11-same-mainwing-20261108'
UPPER=ROOT/'artifacts/isae/sa11-minimum-spacing-20261108'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(k)=='1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
pins={};factors=[];constraints=[];cases=[]


def pin(path):
    pins[str(path.relative_to(ROOT))]=sha(path)


for path in (OUT/'constraint-plan-r2.json',FOURIER/'plan.json'):
    plan=read(path)
    for name,digest in plan['pins'].items():assert sha(ROOT/name)==digest,name
    pins.update(plan['pins']);pin(path)
for number in (11,12):
    folder=OUT/f'a{number:02d}';r=read(folder/'report.json');v=read(folder/'constraint-verification.json')
    assert v['verified'] and v['parent_report_sha256']==sha(folder/'report.json')
    assert v['plan_sha256']==sha(OUT/'constraint-plan-r2.json')
    factors.append(r);constraints.append(v)
    pin(folder/'report.json');pin(folder/'constraint-verification.json')
plan=read(FOURIER/'plan.json')
for case in plan['cases']:
    folder=FOURIER/case['id'];row=read(folder/'report.json');raw=read(folder/'accepted.json')
    assert row['status']=='computed' and row['case']==case and row['plan_sha256']==sha(FOURIER/'plan.json')
    path=folder/'diagnostic-verification.json'
    if not path.exists():path=folder/'projection-verification.json'
    proof=read(path);assert proof['report_sha256']==sha(folder/'report.json')
    checker=ROOT/'scripts'/('check_sa11_tip_fourier_diagnostics.py' if 'diagnostic' in path.name else 'check_sa11_tip_fourier.py')
    assert proof['checker_sha256']==sha(checker)
    for name,digest in row['artifacts'].items():assert sha(folder/name)==digest;pin(folder/name)
    for path in (path,folder/'report.json',checker):pin(path)
    failed=[key for key,value in proof.get('checks',{}).items() if not value]
    assert proof['verified']==(not failed)
    # Both observed failures are retained; no diagnostic gate is loosened.
    assert not failed or (case['main_intervals']==32 and case['main_modes']==30 and set(failed)=={'circulation_reconstruction','conditional_gamma_relative'})
    cases.append(dict(id=case['id'],configuration=case['physical_configuration'],main_intervals=case['main_intervals'],
        main_modes=case['main_modes'],CL=raw['CL'],CD=raw['CD'],CDi=raw['CDi'],
        reference=case['reference'],errors_percent=row['errors_percent'],
        local_residual_max=proof['local_residual_max'],projected_residual_max=proof['projected_residual_max'],
        sampling_condition=proof['sampling_condition'],projected_matrix_condition=proof['projected_matrix_condition'],
        diagnostic_verified=proof['verified'],failed_diagnostic_checks=failed,
        independent_errors=proof['errors'],minimum_stall_margin_widths=row['minimum_stall_margin_widths'],
        maximum_normal_mach=row['maximum_normal_mach']))
controls=[]
for count in (32,46):
    for config in ('wing_alone','upper_winglet'):
        folder=(LOCAL/f'{config}-tip-local-m0_70-a12' if count==46 else
                BASE/'mainwing-control-m0_70-a12' if config=='wing_alone' else UPPER/'m0_70-a12')
        raw=read(folder/'accepted.json');row=read(folder/'report.json');reference=next(c['reference'] for c in cases if c['configuration']==config)
        for path in (folder/'accepted.json',folder/'report.json'):pin(path)
        controls.append(dict(configuration=config,main_intervals=count,main_modes=0,
            CL=raw['CL'],CD=raw['CD'],CDi=raw['CDi'],reference=reference,
            errors_percent={key:100*(raw[key]/reference[key]-1) for key in ('CL','CD','CDi')},
            local_residual_max=max(map(abs,raw['circulation_local_residual'])),projected_residual_max=raw['residual']))
batches=[read(p) for p in sorted(FOURIER.glob('batch-*.json'))];assert sum(b['count'] for b in batches)==8
for path in (Path(__file__),ROOT/'scripts/audit_sa11_tip_factorization.py',ROOT/'scripts/check_sa11_tip_factorization.py',
             OUT/'plan.json',OUT/'constraint-check-first.json',OUT/'constraint-checker-first.py',
             ROOT/'artifacts/isae/sa11-tip-fourier-20261108/preflight-failure.json'):
    pin(path)
summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(),analysis_verified=True,pins=pins,
    factorization=factors,constraint_checks=constraints,fourier_cases=cases,pointwise_controls=controls,
    factorization_summary=dict(
        receiver_total_share_percent=[r['attribution_percent']['receiver_quadrature']['total'] for r in factors],
        main_step_total_share_percent=[r['attribution_percent']['main_circulation_steps']['total'] for r in factors],
        winglet_total_share_percent=[r['attribution_percent']['winglet_circulation']['total'] for r in factors],
        source_geometry_total_share_percent=[r['attribution_percent']['source_geometry']['total'] for r in factors],
        source_endpoint_roundoff_m=max(v['source_endpoint_roundoff_m'] for v in constraints)),
    fourier_summary=dict(physical_calls=8,computed=8,rejected=0,
        full_diagnostic_checks_passed=sum(c['diagnostic_verified'] for c in cases),full_diagnostic_checks_required=8,
        failed_cases=[c['id'] for c in cases if not c['diagnostic_verified']],
        maximum_normal_mach=max(c['maximum_normal_mach'] for c in cases),
        minimum_stall_margin_widths=min(c['minimum_stall_margin_widths'] for c in cases),
        maximum_batch_seconds=max(b['seconds'] for b in batches),peak_rss_kib=max(b['peak_rss_kib'] for b in batches)),
    primary_count=dict(passed=21,required=48,changed=False),original_count=dict(passed=1060,required=9184,changed=False),
    conclusion='Full cross-beam force sensitivity is~99%main-circulation step distribution and winglet-circulation response,~1%receiver quadrature. Large separated finite-origin receiver terms cancel with half-wake terms. Conditional winglet equations verify the response,dominated by outer-main forcing with negligible stall. Main-only Fourier20/30 does not stabilize this mesh comparison and cannot justify a default change.',
    limitations='Factorization at alpha2.75/3 covers cross-beam vortex drag,not all drag terms or the different equal-CL interpolation. Main-step attribution includes discretization of circulation jumps,not solely amplitude changes. Fourier conditional replay holds saved stall leakage fixed. Native producing input/mesh/modes remain unknown.',
    preparation_notes=['First conditional audit required bitwise endpoint identity and stopped at1.11e-16m roundoff; original checker/receipt retained. New check records the difference.',
        'Initial Fourier plan lacked recorder preflight and stopped before physical calls; retained first plan/receipt. All8physical calls are in the r2plan.',
        'The older configuration checker rejected diagnostic configuration names before execution; a dedicated independent checker verifies both fields and Fourier projection.',
        'Strict Fourier audit stopped at mode30/main32 reconstruction error. Complete diagnostics preserve that gate and also record conditional linear replay failure. A NumPy boolean JSON serialization failure was fixed; partial output and source retained. No physical solve was repeated or discarded.'])
serialized=json.dumps(summary,indent=2,allow_nan=False)+'\n'
with (OUT/'analysis.json').open('x') as f:f.write(serialized)
signal.alarm(0);print(json.dumps(dict(analysis_verified=True,pins=len(pins),factorization=summary['factorization_summary'],fourier=summary['fourier_summary']),indent=2))
