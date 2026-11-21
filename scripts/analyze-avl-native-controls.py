"""Audit retained native AVL controls and report mesh/angle sensitivity."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'artifacts/isae/avl-native-build-20261108'
BASE=ROOT/'artifacts/isae/avl-native-controls-20261108'
EXTRA=ROOT/'artifacts/isae/avl-native-controls-20261108-refinement'
OUT=ROOT/'artifacts/isae/avl-native-controls-20261108-review'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()


def main():
    assert not OUT.exists(),OUT
    build=json.loads((BUILD/'plan.json').read_text())
    verification=json.loads((BUILD/'verification.json').read_text())
    for name,pin in build['source_build_pins'].items():assert sha(BUILD/'source'/name)==pin,name
    for name,pin in build['unchanged_pins'].items():assert sha(ROOT/name)==pin,name
    assert sha(BUILD/'avl')==verification['binary_sha256']
    cases={};pins={}
    for folder in [BASE,EXTRA]:
        plan=json.loads((folder/'plan.json').read_text());pins[str(folder.relative_to(ROOT)/'plan.json')]=sha(folder/'plan.json')
        for c in plan['cases']:
            f=folder/c['id']/'result.json';d=json.loads(f.read_text());assert d['case']==c
            pins[str(f.relative_to(ROOT))]=sha(f)
            for name,pin in d['artifacts'].items():assert sha(f.parent/name)==pin,(f,name)
            assert json.loads((f.parent/'process.json').read_text())['returncode']==0
            assert d['vortices']<=768
            cases[c['id']]=d
    assert len(cases)==29
    def cf(name):return cases[name]['coefficients']
    checks={}
    keys=['CXtot','CYtot','CZtot','Cltot','Cmtot','Cntot']
    checks['zero_incidence_force_moment_max']=max(abs(cf('rectangle-zero')[k]) for k in keys)
    assert checks['zero_incidence_force_moment_max']==0.
    signs=dict(CXtot=1,CYtot=-1,CZtot=1,Cltot=-1,Cmtot=1,Cntot=-1,CLtot=1,CDind=1,CDff=1)
    checks['sweep_reflection_max_error']=max(abs(cf('swept-reflected')[k]-v*cf('swept-c8-s32')[k]) for k,v in signs.items())
    assert checks['sweep_reflection_max_error']<1e-10
    a5=math.radians(5);a1=math.radians(1)
    odd=math.sin(a1)*math.cos(a1)/(math.sin(a5)*math.cos(a5))
    even=(math.sin(a1)/math.sin(a5))**2
    angle_errors=[]
    # For these planar, flat, fixed-x-wake fixtures, Gamma is proportional to
    # sin(alpha). The six geometric-axis loads have the stated exact factors.
    for shape in ['rectangle','swept']:
        factors={'CXtot':even,'CYtot':even,'CZtot':odd,'Cltot':odd,'Cmtot':odd,'Cntot':even,'CDff':even}
        for k,factor in factors.items():angle_errors.append(abs(cf(shape+'-alpha1')[k]-factor*cf(shape+'-c8-s32')[k]))
    # Nonplanar geometry has both sin(alpha)cos(alpha) and sin(alpha)^2 terms.
    # +/-5-degree output determines them; +/-1-degree runs are independent
    # predictions of this source-derived homogeneity, not production tuning.
    for k in keys:
        plus=cf('winglets-c8-s32')[k];minus=cf('winglets-negative')[k]
        for name,sign in [('winglets-alpha1',1),('winglets-alpha-minus1',-1)]:
            predicted=sign*odd*(plus-minus)/2+even*(plus+minus)/2
            angle_errors.append(abs(cf(name)[k]-predicted))
    for name in ['winglets-alpha1','winglets-alpha-minus1']:
        angle_errors.append(abs(cf(name)['CDff']-even*cf('winglets-c8-s32')['CDff']))
    checks['angle_homogeneity_max_error']=max(angle_errors)
    assert checks['angle_homogeneity_max_error']<1e-10
    checks['rounded_strip_force_moment_reconstruction_max_error']=max(d['rounded_strip_reconstruction_max_error'] for d in cases.values())
    assert checks['rounded_strip_force_moment_reconstruction_max_error']<2e-5
    meshes=[(1,16),(2,16),(4,16),(8,16),(8,32),(8,64),(16,32)]
    tables={};refinements={}
    for shape in ['rectangle','swept','winglets']:
        rows=[]
        for nc,ns in meshes:
            d=cases[f'{shape}-c{nc}-s{ns}'];c=d['coefficients']
            peak=max(d['strip_data'],key=lambda a:abs(a[14]))
            rows.append(dict(nchord=nc,nspan=ns,**{k:c[k] for k in ['CLtot','CDind','CDff','Cmtot']},
                near_far_percent=d['near_far_drag_difference_percent'],
                drag_ratio_after_cosine_projection_percent=(c['CDind']/math.cos(a5)/c['CDff']-1)*100,
                max_abs_strip_cn=d['max_abs_strip_normal_coefficient'],
                max_abs_strip_cm=d['max_abs_strip_pitch_coefficient'],
                max_cn_location=dict(zip(d['body_strips'],peak))))
        tables[shape]=rows
        baseline=cases[shape+'-c8-s32'];refinements[shape]={}
        for tag,suffix in [('span','c8-s64'),('chord','c16-s32')]:
            other=cases[shape+'-'+suffix]
            refinements[shape][tag]={k:(other['coefficients'][k]/baseline['coefficients'][k]-1)*100 for k in ['CLtot','CDind','CDff','Cmtot']}
            refinements[shape][tag]['peak_cn_percent']=(other['max_abs_strip_normal_coefficient']/baseline['max_abs_strip_normal_coefficient']-1)*100
    leg_change={k:cf('swept-leg-forces')[k]-cf('swept-c8-s32')[k] for k in cf('swept-c8-s32')}
    result=dict(observed_utc=utc(),scope='Independent native AVL controls; no ISAE pass or production aerodynamic changes',
        previous_goal_turn='progress: authoritative report acquisition and guidance',
        binary_sha256=sha(BUILD/'avl'),cases=len(cases),max_vortices=max(d['vortices'] for d in cases.values()),
        native_seconds=sum(d['seconds'] for d in cases.values()),
        native_seconds_range=[min(d['seconds'] for d in cases.values()),max(d['seconds'] for d in cases.values())],
        source_build_files_verified=len(build['source_build_pins']),unchanged_pin_count=len(build['unchanged_pins']),
        checks=checks,tables=tables,refinement_percent=refinements,optional_trailing_leg_force_change=leg_change,
        recorded_input_pins=pins,
        limits=['AVLs fixed-body-x wake differs from current-wind ASWING and the preceding local-chord attached-wake controls.',
                'Tiny same-component native core is retained: 0.0001 of strip width.',
                'Stable integrated loads do not prove local junction fields converge; span-only refinement raises peak winglet strip normal force.',
                'No actual SA-11 geometry, local Mach or ASWING executable is evaluated by these native AVL controls.'])
    OUT.mkdir();shutil.copyfile(__file__,OUT/'driver-used.py')
    (OUT/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    render_plot(OUT,cases,tables)
    print(json.dumps({k:result[k] for k in ['cases','native_seconds','native_seconds_range','checks','refinement_percent']},indent=2))


def render_plot(out,cases,tables,stem='native-controls'):
    source=(ROOT/'web/plot-colors.js').read_text()
    palette=re.findall(r"#[0-9a-fA-F]{6}",source.split('export const plotColors')[1].split(']);')[0])
    assert len(palette)==8
    fig,axes=plt.subplots(2,3,figsize=(13,7.2),layout='constrained')
    for j,shape in enumerate(['rectangle','swept','winglets']):
        rows=tables[shape];x=np.arange(len(rows));ax=axes[0,j]
        ax.plot(x,[r['near_far_percent'] for r in rows],'o-',color=palette[0],label='Native near-field / Trefftz')
        ax.axhline(0,color='.5',lw=.7);ax.set_xticks(x,[f"{r['nchord']}/{r['nspan']}" for r in rows],rotation=35)
        ax.set_title(shape.title());ax.set_xlabel('Chord rows / horizontal span strips')
        ax.set_ylabel('Drag difference (%)');ax.grid(alpha=.25)
        ax=axes[1,j]
        for color,(suffix,style) in zip(palette,[('c4-s16','--'),('c8-s32','-'),('c8-s64',':'),('c16-s32','-.')]):
            d=cases[shape+'-'+suffix];a=np.array(d['strip_data']);s=np.cumsum(a[:,5]/a[:,4])-.5*a[:,5]/a[:,4]
            ax.plot(s,a[:,14],style,color=color,lw=2,label=suffix)
        ax.set_xlabel('Arc distance from first tip (m)');ax.set_ylabel('Strip normal-force coefficient');ax.grid(alpha=.25);ax.legend(fontsize=8)
        if shape=='winglets':
            for at in [1,11]:ax.axvline(at,color='.55',lw=.7)
    fig.suptitle('Native AVL 3.52: finite-chord controls at 5°\nIntegrated drag and local strip loads require separate checks')
    fig.savefig(out/(stem+'.svg'));fig.savefig(out/(stem+'.png'),dpi=160);plt.close(fig)


if __name__=='__main__':main()
