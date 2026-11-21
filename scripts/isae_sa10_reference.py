"""Read-only SA-10 source audit; original MATLAB/shell files are never executed."""
from pathlib import Path
import csv,hashlib,json,re,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
REVISION='f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE=ROOT/'.reference/isae-validation'/REVISION
FOLDER=next(CACHE.glob('1 - Aerodynamics/SA*/SA - 10 - *'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def repaired_source(source):
    """Only swap which root joint names beams 2 and 3; retain signed stations."""
    lines=source.splitlines(keepends=True);inside=False;changed=[]
    for i,line in enumerate(lines):
        if line.strip().lower()=='joint':inside=True;continue
        if inside and line.strip().lower()=='end':inside=False
        if not inside or line.lstrip().startswith(('#','!')):continue
        tokens=line.split()
        if len(tokens)==5 and tokens[:2] in [['1','2'],['1','3']]:
            old=int(tokens[1]);tokens[1]=str(5-old)
            lines[i]='      '+'      '.join(tokens)+'\n';changed.append(i+1)
    assert len(changed)==2
    return ''.join(lines),changed


def paired_csv(path,names,reverse=False):
    raw=list(csv.reader(path.open()));assert len(raw[0])==2*len(names)
    output={}
    for j,name in enumerate(names):
        values=[];missing=[]
        for i,row in enumerate(raw[2:],3):
            x,y=row[2*j:2*j+2]
            if not x and not y:missing.append(i);continue
            assert x and y,(path,i,j)
            pair=[float(x),float(y)]
            values.append(dict(row=i,xy=pair[::-1] if reverse else pair,raw_xy=pair))
        output[name]=dict(path=path.relative_to(CACHE).as_posix(),sha256=sha(path),header=raw[:2],values=values,missing_rows=missing,
            mapping='raw CD,CL reversed to CL,CD' if reverse else 'raw X,Y preserved')
    return output


def audit():
    manifest=json.loads((CACHE.parent/'manifest.json').read_text());sources={}
    for path in FOLDER.rglob('*'):
        if path.is_file():
            name=path.relative_to(CACHE).as_posix();pin=manifest['files'][name];assert sha(path)==pin['sha256'];sources[name]=pin
    models=[]
    for path in sorted(FOLDER.rglob('*.asw')):
        m=parse_asw(path.read_text());bodies=[]
        for b in m.beams:
            t=np.array(b.domain)
            bodies.append(dict(index=b.index,physical_index=b.physical_index,name=b.name,domain=t.tolist(),endpoints=b.position(t).tolist(),
                distributions={k:dict(t=d.t.tolist(),values=d.values.tolist()) for k,d in b.distributions.items()}))
        row=dict(name=path.stem,path=path.relative_to(CACHE).as_posix(),sha256=sha(path),source=path.read_text(),reference=m.reference.tolist(),
            constants=m.constants.tolist(),units=m.units.declarations,records={k:[r.tolist() for r in v] for k,v in m.records.items()},beams=bodies,
            diagnostics=m.diagnostics,setups=[])
        for panels in [25,50,100]:
            try:
                meshes=model_meshes(m,panels);row['setups'].append(dict(panels=panels,status='constructed',actual_intervals=sum(len(x.tm) for x in meshes)))
            except ValueError as exc:row['setups'].append(dict(panels=panels,status='rejected',error=str(exc)))
        data=np.loadtxt(path.with_suffix('.txt'),skiprows=3);assert data.shape==(27,82)
        assert np.all(data[:,72]==55) and np.all(data[:,73]==0)
        row['archived']=dict(path=path.with_suffix('.txt').relative_to(CACHE).as_posix(),sha256=sha(path.with_suffix('.txt')),
            columns={'index':0,'time':1,'converged':2,'stall':3,'speed':72,'beta':73,'alpha':74,'lift':75,'drag':76,'CL':77,'CD':78,'CDi':79,'Cm':80,'efficiency':81},rows=data.tolist(),
            duplicate_alpha_12_coefficient_difference=float(np.max(abs(data[12,75:]-data[13,75:]))))
        row['commands']=dict(path=path.with_suffix('.sh').relative_to(CACHE).as_posix(),text=path.with_suffix('.sh').read_text(),
            note='The final K/F command appears after the last solve. Startup PG and influence state are not recorded. Node I 100 appears only in the three single-beam scripts.')
        models.append(row)
    bad=next(r for r in models if r['name']=='TS_60_45_30');derived,changes=repaired_source(bad['source'])
    original=parse_asw(bad['source']);candidate=parse_asw(derived)
    for a,b in zip(original.beams,candidate.beams,strict=True):
        assert a.index==b.index and a.physical_index==b.physical_index and a.distributions.keys()==b.distributions.keys()
        for k,d in a.distributions.items():assert np.array_equal(d.t,b.distributions[k].t) and np.array_equal(d.values,b.distributions[k].values)
    for k,rows in original.records.items():
        if k!='joint':assert all(np.array_equal(a,b) for a,b in zip(rows,candidate.records[k],strict=True))
    a=np.array(original.records['joint']);b=np.array(candidate.records['joint']);assert np.array_equal(np.argwhere(a!=b),[[0,1],[1,1]])
    model_meshes(candidate,25)
    crossref_path=ROOT/'.reference/isae-sa10/crossref.json';crossref=json.loads(crossref_path.read_text())['message']
    primary=dict(doi='10.1115/1.2948372',title=crossref['title'][0],publisher=crossref['publisher'],
        metadata_url='https://api.crossref.org/works/10.1115/1.2948372',metadata_sha256=sha(crossref_path),article_url=crossref['resource']['primary']['URL'],
        full_text_recovered=False,access_failures=['Publisher PDF HTTP 403','Public issue mirror HTTP and HTTPS connection timeouts'],
        abstract_parameters=dict(winglet_aspect_ratio=4.6,effective_wing_aspect_ratio=6.29,Reynolds_number=600000),
        note='Only publisher-deposited bibliographic metadata/abstract recovered. Do not infer detailed geometry, force normalization or uncertainty from the abstract.')
    out=dict(status='SOURCE_AUDIT_WITH_LITERAL_ATTACHMENT_AND_SETUP_CONFLICTS',revision=REVISION,script_sha256=sha(Path(__file__)),sources=sources,models=models,
        primary=primary,derived=dict(name='TS_60_45_30_repaired_joints',parent=bad['name'],source=derived,sha256=hashlib.sha256(derived.encode()).hexdigest(),changed_lines=changes,
            changed_entries=[[0,1,2,3],[1,1,3,2]],meaning='Exchange beams 2/3 in the first two Joint rows so signed attachment stations lie on the named beam. No lifting geometry, section property or aerodynamic grouping changes.'),
        experimental_lift=paired_csv(FOLDER/'Experimental_Data/CL_VS_ALPHA.csv',['wing_alone','wing_extension','Louvered']),
        experimental_drag={**paired_csv(FOLDER/'Experimental_Data/CD_CL.csv',['wing_alone','wing_extension','Louvered'],True),**paired_csv(FOLDER/'Experimental_Data/CD_CL_tip_sail.csv',['TS_60_45_30'])},
        limitations=[
            'Experimental arrays are the ISAE digitizations, not independently extracted raw measurements. Full primary geometry, normalization, tunnel corrections and uncertainty remain unrecovered.',
            'TS_60_45_30 reverses beam 2/3 domains relative to its first two Joint rows; all literal mesh setups reject. A separately labeled two-entry joint reconstruction is retained.',
            'TS_60_40_80 and TS_80_60_40 use Bref=.559 rather than 1.118 and different dCLda/CLmax/Cdp from TS_60_45_30. These are not isolated cant-angle variations.',
            'Actual right-side tip angles ordered by increasing x are approximately [40,60,80] for the file named TS_60_40_80, [80,60,40] for TS_80_60_40 and [60,45,30] for TS_60_45_30.',
            'All seven tip-sail segments share physical index 1; same-physical-surface interactions use the unchanged zero-core convention. The documented close-junction behavior is not masked by changing core radius.',
            'The supplied schematic draws slots in the extension/louvered tips; their literal single-beam models instead use continuous full-chord surfaces. The archived tip-sail span/chord ratio is about 4.06 versus 4.6 in the primary abstract.',
            'Each archived polar repeats alpha=12 degrees. Repeated rows and convergence flags are retained; they are not independent samples.',
            'Only baseline, extension and louvered lift curves and baseline, extension, louvered and 60/45/30 drag curves are supplied. No experimental curve is reassigned to the other two tip-sail variants.',
            'Total CD is the near-field force projection; archived CDi and Trefftz diagnostics are kept separate. Drag comparisons require matching CL and retaining multiple or missing branches.',
            'The unexecuted scripts place a K/F command after the last solve; exact startup influence state and PG Mach remain unrecorded.' ])
    (ROOT/'docs/validation/isae-sa10-sources.json').write_text(json.dumps(out,indent=2)+'\n')
    print('Source audit complete:',len(models),'models,',sum(x['status']=='rejected' for r in models for x in r['setups']),'literal mesh rejections,',len(sources),'source files',flush=True)

if __name__=='__main__':audit()
