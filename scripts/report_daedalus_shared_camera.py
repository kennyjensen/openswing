"""Report fixed-camera motion ambiguity with explicit image-model limits."""
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT,read,pin
from daedalus_bounded_job import run
import check_daedalus_shared_camera as camera

TAGS=['free-0','current-yaw','native-yaw','current-roll-yaw','native-roll-yaw','synthetic-recovery']


def report(folder,args):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    records={};arrays={};receipts={};verified=0
    for tag in TAGS:
        source=camera.STUDY/tag;terminal=read(source/'terminal.json');plan=read(source/'plan.json')
        assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
        for path,sha in plan['inputs_sha256'].items():
            # Earlier jobs retain their actual runner before later optional
            # controls were added; do not relabel them as the latest driver.
            p=source/'runner.py' if Path(path)==Path(camera.__file__) else Path(path)
            assert pin(p)==sha,(tag,p);verified+=1
        records[tag]=read(source/'result.json');receipts[tag]=terminal
        assert records[tag]['optimizer_success']
        with np.load(source/'arrays.npz') as a:arrays[tag]={key:a[key] for key in ['target','predicted','phase']}
    synthetic=records['synthetic-recovery']
    recovery=float(np.max(abs(np.array(synthetic['inferred_linear_rate_amplitudes_deg_s_per_F3'])/
        synthetic['synthetic_expected_rate_amplitudes_deg_s_per_F3']-1)))
    assert recovery<1e-6 and synthetic['support_rms_px']<1e-5
    comparisons={}
    for name,first,second in [('yaw_only','current-yaw','native-yaw'),('roll_and_yaw','current-roll-yaw','native-roll-yaw')]:
        np.testing.assert_array_equal(arrays[first]['target'],arrays[second]['target'])
        d=arrays[first]['predicted']-arrays[second]['predicted']
        comparisons[name]=dict(predicted_support_change_rms_px=float(np.sqrt(np.mean(d*d))),
            predicted_support_change_max_px=float(abs(d).max()),
            fit_rms_difference_px=records[second]['support_rms_px']-records[first]['support_rms_px'])
    fig,axes=plt.subplots(1,2,figsize=(11.5,4.4),constrained_layout=True)
    for tag,label,color in [('free-0','Unconstrained image fit','#777777'),('current-roll-yaw','OpenSwing roll/yaw magnitudes','#c23d36'),
                            ('native-roll-yaw','Drela roll/yaw magnitudes','#3178ad')]:
        r=records[tag];axes[0].plot(np.array(r['frames'])/90,r['frame_support_rms_px'],'o-',ms=3,color=color,label=label)
    axes[0].set(xlabel='Time in the 1 Hz cycle (s)',ylabel='Outline fit RMS (pixels)',title='One fixed camera for each complete-cycle fit')
    delta=arrays['current-roll-yaw']['predicted']-arrays['native-roll-yaw']['predicted']
    for i,(label,color) in enumerate([('Fairing','#3066be'),('Propeller disk','#b1319a')]):
        axes[1].plot(arrays['current-roll-yaw']['phase']/(2*np.pi),np.sqrt(np.mean(delta[:,i]**2,axis=1)),'o-',ms=3,label=label,color=color)
    axes[1].set(xlabel='Time in the 1 Hz cycle (s)',ylabel='RMS outline-prediction change (pixels)',title='Changing both constrained Bode magnitudes')
    for ax in axes:ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.suptitle('Native GIF camera-profile diagnostic\nPhase, pitch and translation remain free; image agreement is not physical validation',fontsize=12)
    fig.savefig(folder/'comparison.png',dpi=140);fig.savefig(folder/'comparison.svg');plt.close(fig)
    return dict(records=records,comparisons=comparisons,synthetic_max_relative_rate_error=recovery,
        verified_source_pins=verified,receipts=receipts,
        qualification='Finite image-model profiles, not statistical confidence intervals. Shared camera removes independent per-frame camera freedom, but rigid calibration geometry, correlated raster errors and free pitch/translation remain. Neither complete physical response is validated.')


if __name__=='__main__':
    inputs=[Path(camera.__file__)]
    for tag in TAGS:inputs.extend(camera.STUDY/tag/name for name in ['plan.json','terminal.json','result.json','arrays.npz','runner.py'])
    run(camera.STUDY,'report',inputs,report,{},__file__)
