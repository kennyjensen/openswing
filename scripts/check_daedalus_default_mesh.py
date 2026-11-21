"""Check the requested GIF-like app mesh without a flight or Bode solve."""
import argparse
from check_daedalus_load_sensitivity import ROOT, read, write
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-default-mesh-20261114'


def inspect(folder,args):
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes, geometry_summary
    from openswing.discretization import report, requirements
    model=parse_asw((ROOT/'examples/dae.asw').read_text())
    source=model.dumps()
    settings=read(ROOT/'web/daedalus-mesh.json')
    results=[]
    for label,panels in [('previous',48),('gif-like',settings)]:
        meshes=model_meshes(model,panels)
        geometry=geometry_summary(model,meshes=meshes)
        mesh_report=report(model,meshes,panels)
        required=requirements(model)
        components=[]
        for mesh,view,beam_report in zip(meshes,geometry,mesh_report['beams']):
            stations=np.r_[mesh.t0,mesh.t1[-1]]
            for item in required[mesh.beam.index]:assert item['t'] in stations,item
            if mesh.beam.lifting:
                assert len(view['quads'])==len(view['streamwise_quads'])==len(mesh.tm)
            assert np.all(mesh.length>0)
            np.testing.assert_array_equal(np.array(view['axis'])[:,0],mesh.r0)
            if mesh.beam.index in (1,2):
                np.testing.assert_allclose(stations,-stations[::-1],rtol=0,
                    atol=8*np.finfo(float).eps*sum(mesh.length))
            components.append(dict(beam=mesh.beam.index,name=mesh.beam.name,
                intervals=len(mesh.tm),stations=len(stations),
                minimum_interval=float(min(mesh.length)),maximum_interval=float(max(mesh.length)),
                length=float(sum(mesh.length)),settings=beam_report['settings']))
        if label=='gif-like':
            assert mesh_report['settings']==settings
            assert [len(m.tm) for m in meshes]==[50,12,10,17,9]
            wing=meshes[0]
            # Main-wing spans use the target spacing; outer spans redistribute
            # evenly around the two short required tip panels.
            assert np.count_nonzero(np.isclose(wing.length,112/48,rtol=0,atol=3e-14))==42
        write(folder/f'{label}-mesh.json',mesh_report)
        results.append(dict(case=label,total_intervals=sum(len(m.tm) for m in meshes),components=components))
    assert model.dumps()==source
    return dict(cases=results,all_required_stations_retained=True,
        qualification='Counts and regular spacing approximate the GIF appearance, not recovered native settings. No aerodynamic, structural or Bode convergence is established; the default ASWING comparison states and physics are unchanged.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True)
    args=vars(parser.parse_args())
    inputs=list((ROOT/'openswing').glob('*.py'))+[ROOT/p for p in (
        'examples/dae.asw','web/daedalus-mesh.json','web/daedalus-mesh.js','web/main.js',
        'web/node-editor.js','tests/daedalus-mesh.test.mjs','docs/validation/ISAE_STATUS.md',
        'docs/validation/aswing-authoritative-sources.json')]
    run(STUDY,args['tag'],inputs,inspect,args,__file__)


if __name__=='__main__':main()
