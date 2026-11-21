"""Audit displayed Daedalus chord stations without an aerodynamic solve."""
import argparse
from check_daedalus_load_sensitivity import ROOT, write
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-mesh-spacing-20261114'


def inspect(folder,args):
    import numpy as np
    from openswing.asw import parse_asw, ASWING_DEFAULT_BREAKS
    from openswing.geometry import model_meshes, geometry_summary
    from openswing.discretization import report, requirements
    model=parse_asw((ROOT/'examples/dae.asw').read_text())
    wing=model.beams[0];assert wing.index==1
    reasons={}
    for name,table in wing.distributions.items():
        if name in ('Cshell','Nshell','Atshell') or table.constant_rigid:continue
        native=name in ASWING_DEFAULT_BREAKS or name.startswith(('dCLdF','dCMdF','dCDdF'))
        for station in table.breaks:
            for t in (float(station),-float(station)):
                if wing.domain[0]<t<wing.domain[1]:
                    reason=dict(property=name,in_documented_default_break_list=native)
                    if reason not in reasons.setdefault(t,[]):reasons[t].append(reason)
    cases=[]
    for count,spacing in ((16,'cosine'),(48,'cosine'),(48,'uniform')):
        settings=dict(default=count,beams={'1':dict(count=count,spacing=spacing)})
        meshes=model_meshes(model,settings);mesh=meshes[0]
        geometry=geometry_summary(model,meshes=meshes)[0]
        nodes=report(model,meshes,settings)['beams'][0]['nodes']
        assert len(geometry['quads'])==len(geometry['streamwise_quads'])==len(mesh.tm)
        np.testing.assert_array_equal(np.array(geometry['axis'])[:,0],mesh.r0)
        np.testing.assert_array_equal(np.array(geometry['axis'])[:,1],mesh.r1)
        for node in nodes:node['break_properties']=reasons.get(node['t'],[])
        lengths=np.array(mesh.length)
        cases.append(dict(requested_intervals=count,spacing=spacing,
            actual_intervals=len(lengths),unique_stations=len(nodes),
            minimum_interval_ft=float(min(lengths)),maximum_interval_ft=float(max(lengths)),
            nodes=nodes,interval_lengths_ft=lengths.tolist()))
    required=requirements(model)[1]
    extras=[]
    for t,why in sorted(reasons.items()):
        if not any(r['in_documented_default_break_list'] for r in why) and not any(
                r['t']==t and r['kind']!='property break / mirror plane' for r in required):
            extras.append(dict(t=t,properties=[r['property'] for r in why]))
    write(folder/'cases.json',cases)
    return dict(cases=[{k:v for k,v in row.items() if k not in ('nodes','interval_lengths_ft')} for row in cases],
        extra_break_stations_beyond_documented_list=extras,
        display_rule='Both renderers draw the analysis panel boundaries; chord stations are not resampled uniformly for display.',
        reference='ASWING manual, Considerations for Data Discontinuities: KBREAK list and warning about irregular node spacing.',
        qualification='No native GIF node coordinates or mesh count recovered. This audit does not authenticate the GIF mesh or establish the native node relocation algorithm. No mesh policy changed and no solver ran.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True)
    args=vars(parser.parse_args())
    inputs=list((ROOT/'openswing').glob('*.py'))+[ROOT/p for p in (
        'examples/dae.asw','reference/aswing_doc.txt','docs/validation/aswing-authoritative-sources.json',
        'web/surface-faces.js','web/viewer.js','web/software-viewer.js','docs/validation/ISAE_STATUS.md')]
    run(STUDY,args['tag'],inputs,inspect,args,__file__)


if __name__=='__main__':main()
