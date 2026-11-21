"""Audit and plot saved generalized winglet fields without new field calls."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True)
    args=parser.parse_args();folder=args.study
    verification=json.loads((folder/'verification.json').read_text())
    plan=json.loads((folder/'plan.json').read_text());rows=json.loads((folder/'results.json').read_text())
    assert all(sha(folder/p)==pin for p,pin in verification['artifacts'].items())
    assert all(sha(ROOT/p)==pin for p,pin in plan['unchanged_pins'].items())
    assert [r['request'] for r in rows]==plan['requests'] and len(rows)==9
    data_by_key={};max_force_error=0.;gap_locations=[]
    for row in rows:
        path=folder/row['artifact']['path'];assert sha(path)==row['artifact']['sha256']
        with np.load(path) as stored:data={k:stored[k] for k in stored.files}
        key=(row['request']['main_intervals'],row['request']['mode']);data_by_key[key]=data
        v=data['velocity'];g=data['gamma'];dl=data['physical_b']-data['physical_a']
        force=1.225*g[:,None]*np.column_stack((v[:,1]*dl[:,2]-v[:,2]*dl[:,1],
            v[:,2]*dl[:,0]-v[:,0]*dl[:,2],v[:,0]*dl[:,1]-v[:,1]*dl[:,0]))
        np.testing.assert_allclose(force,data['forces'],atol=3e-13,rtol=3e-12)
        max_force_error=max(max_force_error,float(np.max(abs(force-data['forces']))))
        np.testing.assert_allclose(v,data['bound_induced']+data['joint_induced']+data['ray_induced']+[1.,0.,0.],atol=3e-12,rtol=3e-12)
        assert abs(np.max(np.linalg.norm(v,axis=1))-row['maximum_speed'])<2e-14
        assert abs(force[:,2].sum()/.06125-row['diagnostic_CL'])<2e-13
        assert row['source_cutoff_activations']==0 and row['minimum_ray_denominator']>1e-13
        assert row['maximum_source_tensor_difference']<1e-12
        actual=np.linalg.norm(data['joint_b'][:,:-1]-data['joint_a'][:,1:],axis=-1)
        np.testing.assert_array_equal(actual,data['joint_connection_gaps'])
        if key[1]=='connected':
            i,j=np.unravel_index(np.argmax(actual),actual.shape)
            gap_locations.append(dict(main_intervals=key[0],receiver_station=float(data['physical_stations'][i]),
                physical_connection=data['physical_b'][j].tolist(),joint_gap_m=float(actual[i,j]),
                upstream_joint=data['joint_b'][i,j].tolist(),downstream_joint=data['joint_a'][i,j+1].tolist()))
    for n in (50,100,200):
        for mode in ('connected','separate-groups'):
            for k in ('gamma','points','physical_a','physical_b'):
                np.testing.assert_array_equal(data_by_key[(n,mode)][k],data_by_key[(n,'raw')][k])
    plt.rcParams.update({'font.size':9,'axes.grid':True,'grid.alpha':.25})
    fig=plt.figure(figsize=(10.5,8.2),constrained_layout=True)
    ax=fig.add_subplot(221);gap=fig.add_subplot(222)
    colors={'raw':'#0072B2','connected':'#009E73','separate-groups':'#D55E00'}
    labels={'raw':'Original horseshoes','connected':'Generalized, connected','separate-groups':'Generalized, separate groups'}
    for mode in colors:
        selected=[r for r in rows if r['request']['mode']==mode]
        ns=[r['request']['main_intervals'] for r in selected]
        ax.plot(ns,[r['maximum_speed'] for r in selected],'o-',color=colors[mode],label=labels[mode])
        gap.plot(ns,[1000*r['maximum_joint_connection_gap'] for r in selected],'o-',color=colors[mode])
    ax.set_xlabel('Main-wing span intervals');ax.set_ylabel('Peak speed / freestream')
    ax.set_title('Fixed circulation: connectivity changes the field')
    ax.legend(fontsize=8)
    gap.set_xlabel('Main-wing span intervals');gap.set_ylabel('Maximum adjacent joint gap [mm]')
    gap.set_title('Shared bound nodes do not imply shared wake joints')
    data=data_by_key[(100,'connected')]
    for subplot,station in ((223,.495),(224,.505)):
        view=fig.add_subplot(subplot,projection='3d')
        i=int(np.argmin(abs(data['physical_stations']-station)))
        mask=(data['physical_stations']>.35)&(data['physical_stations']<.65)
        for names,color,label in ((('physical_a','physical_b'),'.25','Physical bound line'),
            (('effective_a','effective_b'),'#009E73','Receiver-specific bound line')):
            a,b=[data[name][i,mask] if data[name].ndim==3 else data[name][mask] for name in names]
            vertices=np.vstack([a[0],b])
            view.plot(vertices[:,0],vertices[:,1],vertices[:,2],color=color,label=label,linewidth=2)
        for j in np.flatnonzero(mask)[::2]:
            for bound,joint in (('effective_a','joint_a'),('effective_b','joint_b')):
                line=np.vstack([data[bound][i,j],data[joint][i,j]])
                view.plot(line[:,0],line[:,1],line[:,2],color='#D55E00',linewidth=.8,alpha=.7)
        p=data['points'][i]
        view.scatter(*p,color='#CC0000',s=28,label='Receiver')
        view.set_xlabel('x [m]');view.set_ylabel('y [m]');view.set_zlabel('z [m]')
        view.set_title(f'Effective geometry for receiver s={data["physical_stations"][i]:.3f} m')
        view.view_init(elev=24,azim=-62)
        if subplot==223:view.legend(fontsize=7,loc='upper left')
    fig.suptitle('Connected generalized lifting-line geometry — prescribed-field diagnostic\n'
                 'No generalized circulation solve and no ASWING validation claim',fontsize=12)
    for ext in ('png','svg'):fig.savefig(folder/('generalized-field-comparison.'+ext),dpi=160)
    plt.close(fig)
    summary=dict(utc=datetime.now(timezone.utc).isoformat(),raw_artifact_pins_verified=True,
        production_status_scope_pins_unchanged=True,identical_prescribed_gamma_and_physical_geometry_verified=True,
        maximum_force_reconstruction_error=max_force_error,
        maximum_source_tensor_difference=max(r['maximum_source_tensor_difference'] for r in rows),
        maximum_geometry_equation_difference=max(r['maximum_geometry_equation_defect'] for r in rows),
        minimum_ray_denominator=min(r['minimum_ray_denominator'] for r in rows),
        source_cutoff_activations=sum(r['source_cutoff_activations'] for r in rows),
        largest_connected_gaps=gap_locations,scientific_solves=0,
        analysis_driver_sha256=sha(Path(__file__)),plots={p.name:sha(p) for p in folder.glob('generalized-field-comparison.*')})
    (folder/'analysis.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
