"""SA-12 source and primary-reference audit; no upstream code is executed."""
from pathlib import Path
import csv, hashlib, json, re, sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
REVISION='f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE=ROOT/'.reference/isae-validation'/REVISION
FOLDER=next(CACHE.glob('1 - Aerodynamics/SA*/SA - 12 - *'))
D=ROOT/'docs/validation';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
HEIGHTS={'05':.127,'2':.508,'inf':1000.}
FILES={'no_flap':'Rectangular_Wing_No_flap.asw','slotted_flap':'Rectangular_Wing_flap.asw'}


def paired_csv(path):
    rows=list(csv.reader(path.read_text().splitlines()))
    assert rows[0]==['h_c_05','','h_c_2','','h_c_inf','']
    assert rows[1]==['X','Y','X','Y','X','Y']
    result={}
    for j,label in enumerate(HEIGHTS):
        values=[];empty=[]
        for line,row in enumerate(rows[2:],3):
            a,b=row[2*j:2*j+2]
            assert bool(a.strip())==bool(b.strip())
            if not a.strip():empty.append(line);continue
            values.append(dict(row=line,xy=[float(a),float(b)]))
        assert all(np.isfinite(p['xy']).all() for p in values)
        result[label]=dict(path=path.relative_to(CACHE).as_posix(),sha256=sha(path),header=rows[0][2*j],
            columns=[2*j,2*j+1],values=values,empty_rows=empty,axes=['reported_alpha_deg','CL' if '_CL' in path.name else 'CD'])
    return result


def main():
    manifest=json.loads((ROOT/'.reference/isae-validation/manifest.json').read_text())
    assert manifest['revision']==REVISION
    files={}
    for path in sorted(p for p in FOLDER.rglob('*') if p.is_file()):
        name=path.relative_to(CACHE).as_posix();pin=manifest['files'][name];data=path.read_bytes()
        assert len(data)==pin['bytes'] and sha(path)==pin['sha256']
        assert hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()==pin['git_blob_sha1']
        files[name]=pin
    assert len(files)==28
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    models=[]
    for name,filename in FILES.items():
        path=FOLDER/'Aswing_Simulations'/filename;source=path.read_text();assert source.encode()==path.read_bytes()
        model=parse_asw(source);setups=[]
        for panels in [25,50,100]:
            meshes=model_meshes(model,panels)
            setups.append(dict(panels=panels,status='constructed',actual_strips=sum(len(m.tm) for m in meshes)))
        models.append(dict(name=name,model_name=model.name,path=path.relative_to(CACHE).as_posix(),source=source,sha256=sha(path),
            constants=model.constants.tolist(),reference=model.reference.tolist(),records={k:[r.tolist() for r in v] for k,v in model.records.items()},
            setups=setups,beams=[dict(index=b.index,physical_index=b.physical_index,domain=list(b.domain),
                endpoints=b.position(b.domain).tolist(),distributions={k:dict(t=v.t.tolist(),values=v.values.tolist()) for k,v in b.distributions.items()}) for b in model.beams]))
    commands=[];archived=[]
    for name in FILES:
        prefix='No_Flap' if name=='no_flap' else 'Flap'
        for label,height in HEIGHTS.items():
            path=FOLDER/'Aswing_Simulations'/f'Rectangular_Wing_{prefix}_hc_{label}.sh'
            source=path.read_text();angles=[float(v) for v in re.findall(r'^!A\s+([-+\d.]+)',source,re.M)]
            speeds=[float(v) for v in re.findall(r'^!V\s+([-+\d.]+)',source,re.M)]
            z=[float(v) for v in re.findall(r'^!Rz\s+([-+\d.]+)',source,re.M)]
            assert speeds==[35.76] and z==[height] and len(angles)==85
            command=dict(name=name,height_label=label,height=height,path=path.relative_to(CACHE).as_posix(),sha256=sha(path),source=source,
                speed=speeds[0],alpha=angles,anchored_defaults_explicit=bool(re.search(r'%\s+a\s+d',source)),
                node_command_argument=100,iteration_limit=25,freeze_toggle_present=True,explicit_pitch=False,explicit_pg=False,
                ground_flag=1,ground_normal=[0,0,1])
            assert 'NODE\nI \n100' in source and re.search(r'oper\s+k\s+I\s+25\s+F',source)
            assert re.search(r'\ng\n1\n0 0 1\n',source)
            commands.append(command)
            table=path.with_suffix('.txt');a=np.loadtxt(table);assert a.shape==(85,9)
            assert np.array_equal(a[:,0],np.arange(1,86)) and np.array_equal(a[:,1],a[:,0])
            assert np.all(a[:,2]==1) and np.array_equal(a[:,4],angles)
            missing=sorted(set(np.arange(-6,16.01,.25))-set(angles));assert missing==[11.25,11.5,11.75,12.]
            archived.append(dict(name=name,height_label=label,height=height,path=table.relative_to(CACHE).as_posix(),sha256=sha(table),
                headers=table.read_text().splitlines()[:3],rows=a.tolist(),all_convergence_flags_one=True,
                columns={'index':0,'t':1,'conv':2,'stall':3,'alpha':4,'CL':5,'CD':6,'CDi':7,'Cm':8},
                missing_quarter_degree_angles=missing,
                speed_and_height_source='Paired command script; the nine-column archive does not contain speed, height, attitude, density, area, PG setting or discretization.'))
    experimental={}
    for name,prefix in [('no_flap','No_flap'),('slotted_flap','Flap')]:
        experimental[name]={key:paired_csv(FOLDER/'Experimental_Data'/f'{prefix}_Rect_{suffix}.csv') for key,suffix in [('lift','CL'),('drag','CD')]}
    assert sum(len(v['values']) for case in experimental.values() for v in case['lift'].values())==75
    assert sum(len(v['values']) for case in experimental.values() for v in case['drag'].values())==71
    primary=[]
    for filename,identifier,pin in [
        ('naca-tn-705.pdf','19930081443','e93b43f67058556a7e732c319a134128d5e40ba5e218b15b3a7d695e8ccd65ac'),
        ('naca-tr-664.pdf','19930091739','b34a8ed7e710b9baaa4c3bd0a138ba025cbb5b411cc095bde8ad6c68560139f6')]:
        path=ROOT/'.reference/isae-sa12'/filename;assert sha(path)==pin
        primary.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=pin,url=f'https://ntrs.nasa.gov/citations/{identifier}'))
    review=ROOT/'.reference/isae-sa12/primary-review.json'
    primary_review=json.loads(review.read_text());assert primary_review['source_pdf_sha256']==primary[0]['sha256']
    notes=[
        'Both literal models parse and construct. The flapped input changes fixed section alpha, dCLda, CLmax and Cdf; its geometry and control derivatives do not represent a deflected flap. No input repairs are made.',
        'Ground in the asw file specifies a structural constraint. Solid-ground aerodynamic images are enabled separately in the six command scripts.',
        'The reference height is at the quarter chord. Source Xax=0.25 and x=0 place it at the body origin. Heights 0.127 and 0.508 m represent h/c=0.5 and 2; the nominal infinity script retains an image at Rz=1000 m.',
        'The tunnel flow is parallel to the ground board. The source scripts prescribe alpha and Rz but do not record Euler pitch; their nine-column archives cannot establish the actual pose. Pitch=alpha aligns freestream and board for the supplied input; zero pitch is a separate diagnostic.',
        'All scripts toggle K/F once. The documented default is frozen, but the actual startup state/settings files are unavailable. No exact archived mode count or PG setting is recorded.',
        'NODE I 100 is explicit, but node versus interval counting, feature stations and Fourier truncation require separate reconciliation. A request for 100 intervals is not proven to reproduce that mesh.',
        'The no-flap infinity script omits the explicit anchored-defaults command found in the other five scripts.',
        'All six source sweeps skip 11.25, 11.5, 11.75 and 12 degrees. Every stored row is retained; the missing reference data are not invented.',
        'ISAE describes plain-wing lift coordinates shifted to zero lift. The input section alpha is 0 although the report cites a physical section zero-lift angle of -1 degree. No fitted angle shift is introduced. The chord versus zero-lift datum needs reconciliation for pitch relative to the ground.',
        'Only the close-ground no-flap drag display replaces total CD by 0.01+CDi. The report describes disabled post-stall drag, but the command scripts do not record such a toggle. Raw total CD and this fixed display transformation remain separate.',
        'Plain-wing and slotted-flap section constants are described as obtained from two-dimensional experiments; the included XFOIL CSV is not the stated source of these constants.',
        'The literal flapped file is an equivalent single lifting line. It cannot resolve the slot, flap-ground interaction or changing section behavior with ground proximity.',
        'Both inputs set section Cm=0. The measured flap pitching-moment curves in the primary report are not represented by those properties, and no experimental Cm CSV is supplied. Agreement with the archived near-zero Cm would not validate the physical flap moment.',
        'The equivalent straight chord does not reproduce the actual deflected flap tip. Its computed geometric clearance is not the physical flapped-wing clearance.',
        'Primary estimated errors do not include CSV digitization uncertainty, source-property mismatch or all apparatus effects. They are not standard deviations.',
        'The primary uses Reynolds number 609,000, effective Reynolds number 974,000 and a stationary board. The two-dimensional section reference has different Reynolds and tunnel conditions. Parameter provenance alone does not establish agreement.']
    report=dict(status='SOURCE_AUDIT_NO_PHYSICAL_VALIDATION',revision=REVISION,script_sha256=sha(Path(__file__)),modules=modules,
        sources=files,models=models,commands=commands,archived=archived,experimental=experimental,primary=primary,
        primary_review=primary_review,primary_review_sha256=sha(review),limitations=notes,
        isae_report=dict(path='5 - Technical Reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.pdf',
            sha256=sha(CACHE/'5 - Technical Reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.pdf'),scope='SA-12A/B, Figure23, references36and46'),
        postprocessing=dict(path=(FOLDER/'Post_tratement.m').relative_to(CACHE).as_posix(),source=(FOLDER/'Post_tratement.m').read_text(),
            close_ground_no_flap_drag_expression='0.01 + archived CDi',applied_to_raw_predictions=False))
    (D/'isae-sa12-sources.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# SA-12 ground-effect source audit','',
        '**This source audit is not a validation pass.** Both original inputs construct unchanged. '+
        'The archive contains six 85-point polars, 75 digitized lift measurements and 71 digitized drag measurements. '+
        'All 28 upstream files pass their pinned Git blob, SHA-256 and byte-count checks.','',
        'The primary experiment is [Recant, NACA-TN-705](https://ntrs.nasa.gov/citations/19930081443). '+
        'Its flap geometry points to [Wenzinger and Harris, NACA-TR-664](https://ntrs.nasa.gov/citations/19930091739). '+
        'The rectangular NACA 23012 wing has span 1.524 m, chord 0.254 m and aspect ratio 6. The ground height is measured at its quarter chord. '+
        'The flapped model represents a full-span 40-degree slotted flap through fixed section properties.','',
        '| Input | Section alpha | dCL/da | CLmax | Cdf |',
        '| --- | ---: | ---: | ---: | ---: |']
    for m in models:
        props=m['beams'][0]['distributions']
        lines.append('| '+m['name']+' | '+' | '.join(f"{props[k]['values'][0]:g}" for k in ['alpha','dCLda','CLmax','Cdf'])+' |')
    lines+=['','The scripts prescribe 35.76 m/s, solid ground and heights 0.127, 0.508 and 1000 m. '+
        'They do not archive Euler pitch. A physically matched tunnel setup requires the freestream parallel to the board; '+
        'the supplied incidence datum and actual archived pose must be distinguished.','',
        'The primary precision table states estimated bounds: angle ±0.1 degree, CL ±0.001, CLmax ±0.005, CD ±0.001, '+
        'unflapped CDmin ±0.0005, Cm ±0.001, flap angle ±1 degree and height ±1/16 inch. '+
        'These bounds do not cover digitization or every setup/property error.','',
        'The no-flap close-ground drag plot uses `0.01 + CDi` in the original MATLAB postprocessing. '+
        'That display correction is not raw solver drag and is not applied silently here.','',
        'Outstanding source/setup issues:','']+['- '+n for n in notes]+['',
        'All originals, commands, CSV row mappings and primary pins are retained in [the source data](isae-sa12-sources.json). '+
        'The upstream shell and MATLAB programs have not been executed.','']
    (D/'isae-sa12-sources.md').write_text('\n'.join(lines))
    print('SA12 SOURCE AUDIT',len(files),'files;',len(models),'models;',len(archived),'polars;75lift/71dragpoints',flush=True)


if __name__=='__main__':main()
