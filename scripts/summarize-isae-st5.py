"""Reduce the reconstructed ST-5 study without interpolating across joints."""
from pathlib import Path
import hashlib
import importlib.util
import json
import numpy as np
import argparse

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'docs/validation'
LBF_FT_TO_NM = 4.4482216152605*.3048


def stats(pairs):
    if not pairs:
        return dict(count=0)
    values = np.asarray(pairs)
    error = (values[:,1]-values[:,2])*LBF_FT_TO_NM
    return dict(count=len(error), bias_Nm=float(np.mean(error)), rmse_Nm=float(np.sqrt(np.mean(error**2))),
                maximum_absolute_error_Nm=float(np.max(abs(error))), samples_y_ft_predicted_lbft_reference_lbft=values.tolist())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default='isae-st5.json')
    parser.add_argument('--output',default='isae-st5-comparison.json')
    args=parser.parse_args()
    source = DEST/args.input
    study = json.loads(source.read_text())
    modules = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'openswing').glob('*.py'))}
    assert study['provenance']['modules'] == modules
    spec = importlib.util.spec_from_file_location('isae_st5', ROOT/'scripts/verify-isae-st5.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    assert runner.sha(Path(spec.origin)) == study['provenance'].get('reference_decoder_sha256',study['provenance']['script_sha256'])
    output = dict(status='COMPARISONS_RECORDED_NOT_VALIDATION_PASS', provenance=dict(modules=modules,
                  study_sha256=runner.sha(source), script_sha256=runner.sha(Path(__file__))), cases=[])
    for case in study['cases']:
        model = runner.parse_asw((runner.CACHE/case['input_path']).read_text())
        comparisons = []
        for run in case['runs']:
            if run['status'] != 'computed':
                comparisons.append(dict(panels=run['specification']['panels'],status='rejected',error=run['error']))
                continue
            row = dict(panels=run['specification']['panels'],status='computed', beams=[])
            for beam in model.beams:
                elements = [e for e in run['result']['elements'] if e['beam'] == beam.index and e['t'] > 0]
                assert elements
                data = case['archived'][str(beam.index)]
                archived = np.asarray(data['rows'])
                joints = sorted({float(r[2] if int(r[0])==beam.index else r[3])
                                 for r in model.records.get('joint',[]) if beam.index in r[:2]})
                breaks = sorted({0., beam.domain[1], *[x for x in joints if 0 < x < beam.domain[1]]})
                curves = []
                for lo, hi in zip(breaks[:-1], breaks[1:]):
                    selected = [e for e in elements if lo < e['t'] < hi]
                    curves.append(dict(t_range=[lo,hi],y_ft=[float(beam.position(e['t'])[1]) for e in selected],
                                       Mx_lbft=[e['moment'][0] for e in selected]))
                # Text contains duplicated trace stations at material breaks and joints.
                parts = np.split(np.arange(len(archived)),np.flatnonzero(np.diff(archived[:,0]) == 0)+1)
                pairs, raw_pairs, missing = [], [], []
                for e in elements:
                    part = next((ids for ids in parts if len(ids)>1 and archived[ids[0],0] <= e['t'] <= archived[ids[-1],0]),None)
                    if part is None:
                        missing.append(e['t'])
                        continue
                    reference = float(np.interp(e['t'],archived[part,0],np.asarray(data['Mx_lbft'])[part]))
                    raw = float(np.interp(e['t'],archived[part,0],np.asarray(data['raw_Mx'])[part]))
                    y = float(beam.position(e['t'])[1])
                    pairs.append([y,e['moment'][0],reference])
                    raw_pairs.append([y,e['moment'][0],raw])
                # Dimensional CSV positions in inches; no per-series span normalization.
                measured = np.asarray([[np.nan if v is None else v for v in x] for x in case['experiment']])
                measured = measured[:,2*(beam.index-1):2*beam.index]
                samples, excluded = [], []
                for index,(x,mx) in enumerate(measured):
                    if not np.all(np.isfinite([x,mx])):
                        excluded.append(dict(row=index,reason='missing digitized datum'))
                        continue
                    y=x/12
                    curve=next((c for c in curves if len(c['y_ft'])>1 and c['y_ft'][0] <= y <= c['y_ft'][-1]),None)
                    if curve is None:
                        excluded.append(dict(row=index,y_in=float(x),reason='outside midpoint sample range or within a joint gap; no extrapolation'))
                    else:
                        predicted=float(np.interp(y,curve['y_ft'],curve['Mx_lbft']))
                        samples.append([float(y),predicted,float(mx/12)])
                # A fixed root has its undeformed frame. Diagnose reference scaling
                # using this boundary condition independently of any computed deflection.
                root_rows=np.flatnonzero(archived[:,0] == 0)
                root_rows=root_rows[np.asarray(data['raw_rows'])[root_rows,4] >= 0] if beam.index==1 else root_rows[np.asarray(data['raw_rows'])[root_rows,4] <= 0]
                i=int(root_rows[-1])
                derivative=beam.position(0.,derivative=1,side='right')
                jig_phi=float(np.rad2deg(np.arctan2(derivative[2],derivative[1])))
                row['beams'].append(dict(beam=beam.index, curves=curves,
                    archived_MATLAB_Mx=stats(pairs), archived_unscaled_text_Mx=stats(raw_pairs),
                    archived_unmatched_t=missing, experimental_Mx=stats(samples), experimental_excluded=excluded,
                    clamped_dihedral_deg=dict(input=jig_phi,archived_raw=data['raw_rows'][i][4],archived_MATLAB=archived[i,4])))
            comparisons.append(row)
        refinements=[]
        for coarse,fine in zip(case['runs'][:-1],case['runs'][1:]):
            if coarse['status']!='computed' or fine['status']!='computed':continue
            differences=[]
            for beam in model.beams:
                cn=[n for n in coarse['result']['nodes'] if n['beam']==beam.index]
                fn=[n for n in fine['result']['nodes'] if n['beam']==beam.index]
                differences.append(dict(beam=beam.index,tip_position_change_ft=float(np.linalg.norm(np.asarray(cn[-1]['position'])-fn[-1]['position'])),
                    tip_displacement_ft=float(np.linalg.norm(np.asarray(fn[-1]['position'])-fn[-1]['jig_position']))))
            refinements.append(dict(coarse=coarse['specification']['panels'],fine=fine['specification']['panels'],beams=differences))
        output['cases'].append(dict(name=case['name'],comparisons=comparisons,refinement=refinements))
    (DEST/args.output).write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    for case in output['cases']:
        print(case['name'])
        row=case['comparisons'][-1]
        for b in row.get('beams',[]):
            print(b['beam'],b['archived_MATLAB_Mx']['rmse_Nm'],b['experimental_Mx']['rmse_Nm'],b['experimental_Mx']['count'],b['clamped_dihedral_deg'])


if __name__ == '__main__':
    main()
