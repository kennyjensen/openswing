"""Map the pinned primary Pazy nodal-mass/section data to documented ASW fields.

The source's intrinsic extension/torsion K12 is not expressible by those fields.
Its explicit removal is quantified; it is never silently folded into a fit.
No OpenSwing imports: this module is also used by the independent reference.
"""
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import hashlib
import json
import numpy as np
from scipy.linalg import eigvalsh

ROOT=Path(__file__).resolve().parents[1]
REVISION='396710a19a80004c65c767e9955fe60d59565c39'
CACHE=ROOT/'.reference/pazy-primary'/REVISION
FOLDER='00_Models/01_Pazy_Technion/02_Models_Beam'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def table(path):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(path) as z:
        strings=[''.join(t.itertext()) for t in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
        rows=[]
        for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//s:row',ns):
            values={}
            for c in row.findall('s:c',ns):
                v=c.find('s:v',ns)
                if v is not None:values[''.join(k for k in c.get('r') if k.isalpha())]=strings[int(v.text)] if c.get('t')=='s' else float(v.text)
            rows.append(values)
    header=rows[0]
    return [{label:row[col] for col,label in header.items()} for row in rows[1:] if 'A' in row]


def source(skin):
    assert skin in [0,1]
    names=[FOLDER+'/README.txt',FOLDER+'/01_Coordinates/coordinates.txt',
           FOLDER+f'/02_Inertia_Distributions/inertia_skin{skin}.xlsx',
           FOLDER+f'/03_Stiffness_Distributions/stiffness_skin{skin}.xlsx']
    manifest=json.loads((CACHE.parent/'manifest.json').read_text())
    for name in names:assert sha(CACHE/name)==manifest['files'][name]['sha256']
    coordinates=np.loadtxt(CACHE/names[1],delimiter=',',skiprows=1)
    inertia=table(CACHE/names[2]);stiffness=table(CACHE/names[3])
    assert len(coordinates)==len(inertia)==16 and len(stiffness)==15
    assert np.max(abs(coordinates[:,[0,2]]))==0 and np.all(np.diff(coordinates[:,1])>0)
    mass=np.array([r['mass'] for r in inertia]);offset=np.array([[r[k] for k in ['cgx','cgy','cgz']] for r in inertia])
    tensors=[]
    for r in inertia:
        # README labels these as matrix entries, unlike ASWING's signed products.
        tensors.append([[r['Ixx'],r['Ixy'],r['Ixz']],[r['Ixy'],r['Iyy'],r['Iyz']],[r['Ixz'],r['Iyz'],r['Izz']]])
    matrices=[]
    for r in stiffness:
        k=np.zeros((4,4))
        for i in range(4):
            for j in range(i,4):k[i,j]=k[j,i]=r[f'K{i+1}{j+1}']
        assert np.min(np.linalg.eigvalsh(k))>0
        matrices.append(k)
    tensors=np.array(tensors);assert np.min(np.linalg.eigvalsh(tensors))>0 and np.min(mass)>0
    return dict(skin=skin,coordinates=coordinates,mass=mass,offset=offset,inertia=tensors,stiffness=np.array(matrices),
                sources={name:manifest['files'][name] for name in names})


def projection(matrix):
    k=np.array(matrix,copy=True);k[0,1]=k[1,0]=0
    # Rayleigh quotient bound valid for every section strain vector.
    error=eigvalsh(k-matrix,matrix)
    # Native reduced order is [eps_s,kappa_s,kappa_c,kappa_n].
    signs=np.diag([1.,1.,-1.,1.]);native=signs@k@signs
    ea=native[0,0];cross=native[0,1:];b=native[1:,1:]-np.outer(cross,cross)/ea
    b=b[np.ix_([1,0,2],[1,0,2])]
    section=dict(EA=ea,EIcc=b[0,0],GJ=b[1,1],EInn=b[2,2],EIcs=b[0,1],EIcn=b[0,2],EIsn=b[1,2],
                 Nta=-native[0,2]/ea,Cta=native[0,3]/ea,Cea=0.,Nea=0.)
    return section,k,float(np.max(abs(error)))


def model(skin,orientation='horizontal'):
    data=source(skin);assert orientation in ['horizontal','upright']
    rotation=np.eye(3) if orientation=='horizontal' else np.array([[1.,0.,0.],[0.,0.,-1.],[0.,1.,0.]])
    xyz=data['coordinates']@rotation.T;offset=data['offset']@rotation.T
    tensors=rotation@data['inertia']@rotation.T
    # Positive arbitrary t labels avoid ASWING's implicit mirror convention.
    stations=1+data['coordinates'][:,1];length=data['coordinates'][-1,1]
    rows=['! Explicit primary-data reconstruction, not an original ISAE input.',
          '! Only intrinsic axial-torsion K12 is removed; see pazy-primary-mapping.json.',
          '! Lumped masses and full centroidal tensors are retained. No distributed mass.',
          '! Reference x/c=.441 follows the paper; README rounds this to .44.',
          'Name',f'Pazy primary skin{skin} {orientation} - explicit K12 projection','End',
          'Unit','L 1 m','T 1 s','F 1 N','End','Constant','9.81 1.225 340','End',
          'Reference',f'{.1*length:.17g} .1 {length:.17g}','End','Ground','1 1 0','End','Weight']
    def line(values):return ' '.join(format(float(v),'.17g') for v in values)
    for t,pos,off,m,j in zip(stations,xyz,offset,data['mass'],tensors):
        rows.append(line([1,t,*(pos+off),9.81*m,0,0,0,0,0,*(9.81*np.array([j[0,0],j[1,1],j[2,2],-j[0,1],-j[0,2],-j[1,2]]))]))
    rows+=['End','Beam 1','Primary Pazy reference axis','t x y z chord Xax',
           line([stations[0],*xyz[0],.1,.441]),line([stations[-1],*xyz[-1],.1,.441])]
    mapped=[projection(k)[0] for k in data['stiffness']];keys=list(mapped[0])
    rows+=['t '+' '.join(keys)]
    for i,section in enumerate(mapped):
        values=[section[k] for k in keys]
        rows+=[line([stations[i],*values]),line([stations[i+1],*values])]
    rows+=['End']
    return '\n'.join(rows)+'\n',data


def mesh(data,refinement):
    assert refinement in [1,2,4,8,16]
    stations=1+data['coordinates'][:,1]
    nodes=np.unique(np.concatenate([np.linspace(a,b,refinement+1) for a,b in zip(stations[:-1],stations[1:])]))
    return dict(default=15,beams={'1':dict(nodes=nodes.tolist())})
