"""Independent source/doublet line integration for SA-14 wing/body fields."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
from scipy.integrate import quad_vec
from scipy.interpolate import CubicSpline

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.volume import VolumeField
D=ROOT/'docs/validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    source_path=D/'isae-sa14-sources.json';sources=json.loads(source_path.read_text())
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')};assert modules==sources['modules']
    eta=np.array([.101,.15,.3,.55,.75,.9]);y=sources['primary']['wing']['span_m']/2*eta
    targets=np.c_[42.2*.0254+(105.83-42.2)/63.6*y,y,np.full(len(y),3.18*.0254)]
    rows=[]
    for name in ['wing_body','infinite_body']:
        case=next(c for c in sources['models'] if c['name']==name);model=parse_asw(case['source'])
        beam=next(b for b in case['beams'] if not b['lifting']);table=beam['distributions']['radius']
        # Axis is x=t in both literal models. Reconstruct the supplied radius
        # spline directly; production quadrature/influence helpers are not used
        # by the reference integrand.
        x=beam['distributions']['x'];assert np.array_equal(x['t'],x['values'])
        radius=CubicSpline(table['t'],table['values'],bc_type='natural')
        for alpha in [0.,8.8]:
            a=np.deg2rad(alpha);direction=np.array([np.cos(a),0.,np.sin(a)])
            def integrand(s):
                r=float(radius(s));dr=float(radius(s,1));delta=targets-np.array([s,0.,0.])
                squared=np.sum(delta*delta,axis=1);den=squared+(r/2)**2
                sigma=2*np.pi*r*dr*np.cos(a)
                doublet=np.array([0.,0.,2*np.pi*r*r*np.sin(a)])
                numerator=doublet*squared[:,None]-3*(delta@doublet)[:,None]*delta
                return 70./(4*np.pi)*(sigma*delta/den[:,None]**1.5+numerator/den[:,None]**2.5)
            reference,error,info=quad_vec(integrand,radius.x[0],radius.x[-1],points=radius.x[1:-1],
                                        epsabs=1e-10,epsrel=1e-11,limit=5000,full_output=True)
            assert info.success and error<1e-8
            for panels in [25,50,100]:
                field=VolumeField(model,model_meshes(model,panels),direction,np.eye(3))
                assert not field.shoulders and not any(field.is_image)
                actual=70.*field.velocity(targets)
                difference=float(np.max(abs(actual-reference)))
                rows.append(dict(case=name,alpha=alpha,panels=panels,positions=targets.tolist(),normalized_y=eta.tolist(),
                    independent_body_velocity=reference.tolist(),production_body_velocity=actual.tolist(),
                    maximum_component_difference=difference,adaptive_error_bound=float(error),evaluations=info.neval))
                print(name,alpha,panels,difference,flush=True)
    report=dict(status='INDEPENDENT_BODY_FIELD_DIAGNOSTIC_COMPLETE',modules=modules,
        source_sha256=sha(source_path),script_sha256=sha(Path(__file__)),rows=rows,
        method='Adaptive source and vector-doublet integrals, split at all radius knots; actual literal body geometry, zero PG, source core R/2, speed70.',
        limitations=['This verifies the implemented regularized body field, not an impermeable solid boundary or experimental agreement.',
            'No lifting circulation is included in this component check. The combined wake/body boundary interaction requires separate validation.',
            'The nominal infinite body is the supplied25.4m finite constant-radius line; no infinite-length limit is assumed.',
            'The same radius table and natural cubic interpolation are used; geometry uncertainty remains.'])
    (D/'isae-sa14-volume.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
