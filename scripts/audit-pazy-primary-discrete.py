"""Independent check of the original-mesh, shear-rigid midpoint beam rank."""
from pathlib import Path
import json
import numpy as np
from scipy.linalg import eigh, null_space
from pazy_primary import ROOT, source, projection, sha
from pazy_primary_reference import matrices


def main():
    native_path=ROOT/'docs/validation/pazy-primary-mapping.json'
    native=json.loads(native_path.read_text());rows=[]
    for skin in [0,1]:
        data=source(skin);n=len(data['coordinates']);k=np.zeros((6*n,6*n));c=[]
        for j,original in enumerate(data['stiffness']):
            length=data['coordinates'][j+1,1]-data['coordinates'][j,1]
            _,section,_=projection(original)
            # Primary strain order: span extension, span torsion,
            # leading-edge-axis curvature, upward-axis curvature.
            b=np.zeros((4,12))
            for row,col,sign in [(0,1,1),(1,4,1),(2,3,-1),(3,5,1)]:
                b[row,col]=-sign/length;b[row,col+6]=sign/length
            ids=np.arange(6*j,6*j+12)
            k[np.ix_(ids,ids)]+=length*b.T@section@b
            # Zero transverse shear: du/ds = theta_mid cross e_span.
            for displacement,rotation,sign in [(0,5,1),(2,3,-1)]:
                constraint=np.zeros(6*n)
                constraint[6*j+displacement]=-1/length
                constraint[6*(j+1)+displacement]=1/length
                constraint[6*j+rotation]=constraint[6*(j+1)+rotation]=sign/2
                c.append(constraint)
        _,mass=matrices(data,True)
        c=np.array(c)[:,6:];z=null_space(c)
        assert c.shape==(30,90) and z.shape==(90,60)
        k=z.T@k[6:,6:]@z;mass=z.T@mass[6:,6:]@z
        # Reciprocal problem gives the most accurate lowest frequencies.
        mu,v=eigh(mass,k,subset_by_index=[52,59])
        frequencies=1/np.sqrt(mu[::-1])/(2*np.pi)
        row=next(r for r in native['runs'] if r['specification']==dict(skin=skin,orientation='horizontal',refinement=1))
        path=ROOT/row['cache'];assert sha(path)==row['sha256'];run=json.loads(path.read_text())
        before=np.array([m['frequency_Hz'] for m in run['modes']])
        error=abs(frequencies-before)
        assert run['diagnostics']['finite_dimension']==2*z.shape[1]==120
        assert max(error)<2e-6,(skin,error)
        rows.append(dict(skin=skin,displacement_coordinates_after_clamp=90,
            independent_shear_constraints=30,dynamic_coordinates=60,finite_first_order_dimension=120,
            frequencies_Hz=frequencies.tolist(),native_difference_Hz=(before-frequencies).tolist(),
            max_frequency_difference_Hz=float(max(error))))
    out=dict(status='PASS_INDEPENDENT_COARSE_DISCRETIZATION',script_sha256=sha(__file__),
        native_sha256=sha(native_path),rows=rows,
        explanation='At one midpoint interval per pair of massive nodes, 30 zero-shear constraints reduce 90 free coordinates to 60, giving 120 first-order finite states. Subdivision adds massless internal coordinates; the refined pencil retains all 90 massive coordinates and has 180 finite states. This is a discretization effect, not a deleted low mode or a continuum-spectrum claim.')
    path=ROOT/'docs/validation/pazy-primary-discrete.json';path.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))


if __name__=='__main__':main()
