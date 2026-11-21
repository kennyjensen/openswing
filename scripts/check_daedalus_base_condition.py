"""Re-evaluate the saved Daedalus base and extract its display diagnostics.

No trim, matrix assembly or frequency solve. The original physical mesh is
preserved explicitly; this does not validate browser defaults or a GIF setup.
"""
import argparse
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, SOURCE, write
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-base-condition-20261114'


def inspect(folder,args):
    import numpy as np
    import check_daedalus_source_operator as source
    source.imports()
    system=source.dynamic(SimpleNamespace(speed=6.7,seed=SOURCE/'trim-6.7-1/state.json',
        frozen=False,no_lag=False,no_plume=False,fourier=0))
    base=system.base_report()
    assert base['modal_base']['kinematically_steady']
    assert base['modal_base']['continuous_residual']<1e-9
    assert abs(base['earth_state']['flight_path'])<1e-7
    assert np.linalg.norm(base['modal_base']['attitude_rates_rad'])<1e-7
    weight=base['mass_properties']['mass']*np.linalg.norm(base['gravity_body'])
    assert abs(weight-233.30193323081556)<1e-7
    fields=('modal_base','mass_properties','gravity_body','gravity_source',
        'reference_flow','earth_state','atmosphere','operating_values','force','engines')
    result=dict(frame_mode='free',base={key:base[key] for key in fields},
        model_metadata=dict(units=system.network.model.units.declarations))
    stations,indices=system.network.station_nodes[1]
    # Reuse the saved physical wing positions, never infer bending from a camera.
    from check_daedalus_load_sensitivity import read
    saved=read(SOURCE/'trim-6.7-1/state.json')
    wing=np.array(saved['positions'])[indices]
    root=int(np.flatnonzero(stations==0)[0])
    heights=(wing[[0,-1],2]-wing[root,2]).tolist()
    write(folder/'display-fixture.json',result)
    return dict(weight_lb=float(weight),wingtip_heights_above_root_ft=heights,
        base=result['base'],node_count=system.network.nn,full_state_count=system.size,
        method='Fresh residual and output recovery at the saved physical equilibrium; no solve.',
        qualification='Literal public model, preserved physical-breaks mesh, declared 6.7 m/s level-flight condition. Native GIF settings and the user browser state remain unknown.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True)
    args=vars(parser.parse_args())
    inputs=list((ROOT/'openswing').glob('*.py'))+[ROOT/p for p in (
        'scripts/check_daedalus_source_operator.py','examples/dae.asw',
        'examples/dae-cruise-physical-mesh-project.json','docs/validation/ISAE_STATUS.md',
        'docs/validation/aswing-authoritative-sources.json','reference/aswing_doc.txt')]
    inputs+=[SOURCE/'trim-6.7-1/state.json']
    run(STUDY,args['tag'],inputs,inspect,args,__file__)


if __name__=='__main__':main()
