"""Pinned legacy type-5 inputs, analytic fields/loads and unit-invariant encounter."""
import hashlib,json,platform,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.integrate import quad
from openswing.gust_file import import_gust,export_legacy_gust
from openswing.gust import gust_field
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,solve_rigid
from openswing.time_integration import solve_time


def profile(x,x0,H,W):
    d=(x0-np.asarray(x))/H
    return np.where((d>=0)&(d<=2),W*np.sin(np.pi*d/2)**2,0.)


def probe_source(source,units):
    L,T,F=units
    return (source.replace('L 1 m\nT 1 s\nF 1 N',f'L {L:.17g} m\nT {T:.17g} s\nF {F:.17g} N')
        .replace('9.81 1.2 340',f'{9.81*T*T/L:.17g} {1.2*L**4/(F*T*T):.17g} {340*T/L:.17g}')
        .replace('2 1 2',f'{2/L**2:.17g} {1/L:.17g} {2/L:.17g}')
        .replace('1 0 0 0 0 0 .4 0',f'1 0 0 0 0 0 {.4/L**2:.17g} 0')
        .replace('1 1 0 0 0 0 0',f'1 {1/L:.17g} 0 0 0 0 0'))


def compute(source,text,spec):
    imported=import_gust(text);field=gust_field(imported['gust'])
    exported=export_legacy_gust(imported['gust']);again=gust_field(import_gust(exported['text'])['gust'])
    if spec['kind']=='profile':
        x0,H,W=spec['reference']
        x=np.linspace(x0-2.5*H,x0+.5*H,301)
        points=np.column_stack((x,7*np.sin(x),3*np.cos(x)))
        actual=field.velocity(points,123.)
        expected=np.zeros_like(actual);expected[:,2]=profile(x,x0,H,W)
        error=float(np.max(abs(actual-expected)))
        assert error<2e-13
        np.testing.assert_array_equal(actual,again.velocity(points,-91.))
        integral=quad(lambda x:field.velocity([x,0,0])[2],x0-2*H,x0,epsabs=1e-10)[0]
        assert abs(integral-W*H)<2e-11
        return dict(kind='profile',sample_x=x.tolist(),velocity=actual.tolist(),maximum_error=error,
                    integral=float(integral),expected_integral=W*H,canonical_export=exported['text'])
    units=spec.get('units',[1.,1.,1.]);L,T,F=units
    model=parse_asw(probe_source(source,units));assert not model.diagnostics
    if spec['kind']=='steady':
        x0,H,W=spec['reference'];bank=spec.get('bank',0.)
        result=solve_rigid(model,FlightCondition(speed=10*T/L,alpha=0,mach=0,attitude=(bank,0,0),
             position_earth=((x0-H)/L,7/L,-4/L),gust=imported['gust']),4)
        # ASWING bank is rotation about the aft-pointing body X axis: Earth up
        # becomes body -Y at +90 degrees and +Y at -90 degrees.
        c,s=np.cos(np.deg2rad(bank)),np.sin(np.deg2rad(bank))
        velocity=np.array([10.,-W*s,W*c])
        expected=.5*1.2*.4*np.linalg.norm(velocity)*velocity
        force=np.array(result['force'])*F
        np.testing.assert_allclose(force,expected,rtol=2e-13,atol=2e-11)
        assert np.max(np.abs(result['moment']))*F*L<2e-11
        return dict(kind='steady',force_N=force.tolist(),expected_force_N=expected.tolist(),residual=result['residual'])
    if spec['kind']=='time':
        c=FlightCondition(speed=10*T/L,alpha=0,mach=0,gust=imported['gust'])
        r=solve_time(model,c,4,duration=.06/T,dt=.06/T,gravity=[0,0,0],tolerance=1e-10)
        samples=[]
        for snap in r['snapshots']:
            t=snap['time']*T;w=float(profile(-10*t,-.2,.1,1.))
            v=np.array([10.,0.,w]);expected=.5*1.2*.4*np.linalg.norm(v)*v
            actual=np.array(snap['force'])*F
            np.testing.assert_allclose(actual,expected,rtol=2e-11,atol=2e-10)
            samples.append(dict(time_s=t,force_N=actual.tolist(),expected_force_N=expected.tolist(),residual=snap['residual']))
        assert r['gust_resolution_retries']>0
        assert max(s['force_N'][2] for s in samples)>.95*(.5*1.2*.4*np.hypot(10,1))
        assert max(s['step']*T for s in r['snapshots']) <= .1/10/8*(1+1e-9)
        return dict(kind='time',samples=samples,accepted_steps=r['accepted_steps'],gust_resolution_retries=r['gust_resolution_retries'])
    raise ValueError('Unknown study case')


def physical(result):
    if result['kind']=='profile':return np.r_[np.ravel(result['velocity']),result['integral']]
    if result['kind']=='steady':return np.array(result['force_N'])
    return np.array([[s['time_s'],*s['force_N']] for s in result['samples']]).ravel()


def legacy(x0,H,W,units):
    L,T,F=units
    return f'5\n{x0/L:.17g}\n0\n{H/L:.17g}\n{W*T/L:.17g}\n0\n'


def main():
    source=(ROOT/'examples/gust-probe.asw').read_text()
    provenance=json.loads((ROOT/'docs/validation/legacy-gust-sources.json').read_text())
    cases=[]
    def run(name,text,**spec):
        result=compute(source,text,spec);cases.append(dict(name=name,text=text,specification=spec,result=result))
        print(name,result['kind'],'verified',flush=True)
        return result
    # Literal external comments are not copied into the distributed study.
    for name,reference in [('wingloop.gust',[-15.,15.,3.]),('avoni.gust',[0.,24.,3.])]:
        raw=(ROOT/'.reference/legacy-gust'/name).read_bytes();entry=provenance['files'][name]
        assert hashlib.sha256(raw).hexdigest()==entry['sha256']
        parsed=import_gust(raw.decode())
        text=export_legacy_gust(parsed['gust'])['text']
        # Compare unchanged external parsing with the original canonical output.
        assert import_gust(text)['gust']==parsed['gust']
        run(name+'/profile',text,kind='profile',reference=reference)
        for bank in [-90.,0.,90.]:run(name+f'/bank/{bank}',text,kind='steady',reference=reference,bank=bank)
    for units in [[1.,1.,1.],[.3048,.1,4.4482216152605],[1000.,60.,1000.]]:
        run('scaled/steady/'+str(units),legacy(-15.,15.,3.,units),kind='steady',reference=[-15.,15.,3.],units=units)
        run('scaled/time/'+str(units),legacy(-.2,.1,1.,units),kind='time',units=units)
    files=sorted(ROOT.glob('openswing/*.py'))+[Path(__file__),ROOT/'examples/gust-probe.asw',ROOT/'examples/vertical-pulse.gust',ROOT/'tests/test_gust_file.py',ROOT/'docs/validation/legacy-gust-sources.json']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    report=dict(scope='Verified straight type-5 input mapping, fields and analytical point-drag encounter; not full catalog or ASWING executable parity.',
                versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
                source_sha256=hashes,provenance=provenance,cases=cases)
    (ROOT/'docs/validation/legacy-gust.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(len(cases),'verified cases',flush=True)
if __name__=='__main__':main()
