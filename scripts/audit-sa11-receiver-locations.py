"""Locate the receiver changes and replay native AVL's span-angle rule."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/isae/sa11-winglet-receivers-20261108'
NATIVE=ROOT/'reference/avl-native-20261108/source/AVL3.52rel09032025/src'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def native_stations(path):
    lines=path.read_text().splitlines();segments=[];current=None
    for i,line in enumerate(lines):
        if line=='SURFACE':
            if current is not None:segments.append(current)
            label=re.fullmatch(r'Beam (\d+) interval (\d+)',lines[i+1]);assert label
            current=dict(beam=int(label[1]),sections=[])
        elif line=='SECTION':current['sections'].append(list(map(float,lines[i+1].split())))
    segments.append(current);t=[];beams=[]
    for segment in segments:
        assert len(segment['sections'])==2
        left,right=segment['sections'];n=int(left[5]);assert left[6]==1 and n==left[5]
        # sgutil.f literal PI, amake.f NSPACE=2*NVINT+1 and even FSPACE
        # entries for YCP, followed by section interpolation through FC.
        f=.5*(1-np.cos(3.1415926535*(np.arange(n)+.5)/n))
        t.extend(left[1]+f*(right[1]-left[1]));beams.extend([segment['beam']]*n)
    return np.array(t),np.array(beams)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    output=p.parse_args().output.resolve();assert not output.exists(),output
    plan=read(SOURCE/'plan.json');analysis=read(SOURCE/'analysis.json')
    for name,pin in plan['pins'].items():assert sha(ROOT/name)==pin,name
    for name,pin in analysis['report_pins'].items():assert sha(ROOT/name)==pin,name
    pins={str(f.relative_to(ROOT)):sha(f) for f in [Path(__file__),SOURCE/'analysis.json',NATIVE/'amake.f',NATIVE/'sgutil.f']}
    rows=[]
    for case in analysis['cases']:
        folder=SOURCE/case['case']['id'];old=(ROOT/case['source_report']).parent
        source_report=read(ROOT/case['source_report'])
        for base,report in [(folder,case),(old,source_report)]:
            for name,pin in report['artifact_sha256'].items():assert sha(base/name)==pin,name
        points,beam=native_stations(old/'model.avl')
        with np.load(old/'native-fields.npz') as f:native={k:f[k].copy() for k in f.files}
        with np.load(folder/'geometry.npz') as f:geometry={k:f[k].copy() for k in f.files}
        fields={}
        for label in ['native-old','native-new','whole-old','whole-new']:
            with np.load(folder/f'{label}.npz') as f:fields[label]={k:f[k].copy() for k in ('velocity','mach','beam')}
        np.testing.assert_array_equal(beam,fields['whole-new']['beam'])
        error=float(np.max(abs(points-native['RV'][:,1])));assert error<2e-14
        moved={str(i):dict(force=float(np.max(np.linalg.norm(geometry['hv'][beam==i]-native['RV'][beam==i],axis=1))),
                          control=float(np.max(np.linalg.norm(geometry['cp'][beam==i]-native['RC'][beam==i],axis=1)))) for i in (1,2,3)}
        roots=np.flatnonzero(fields['whole-new']['mach']>=1);assert len(roots)==2
        a,b,c,d=[fields[k]['velocity'] for k in ('native-old','whole-old','native-new','whole-new')]
        receiver=.5*((b-a)+(d-c));circulation=.5*((c-a)+(d-b));delta=d-a
        identity=float(np.max(abs(receiver+circulation-delta)));assert identity<3e-13
        root_records=[]
        for i in roots:
            root_records.append(dict(index=int(i),beam=int(beam[i]),force_receiver=geometry['hv'][i].tolist(),
                force_receiver_movement=float(np.linalg.norm(geometry['hv'][i]-native['RV'][i])),
                native_distance_from_arithmetic_midpoint=float(np.linalg.norm(native['RV'][i]-.5*(native['RV1'][i]+native['RV2'][i]))),
                velocity_change=delta[i].tolist(),receiver_contribution=receiver[i].tolist(),circulation_contribution=circulation[i].tolist(),
                direct_receiver_norm_ratio=float(np.linalg.norm(receiver[i])/np.linalg.norm(delta[i]))))
        rows.append(dict(alpha=case['case']['alpha'],per_beam_receiver_movement_m=moved,
                         native_section_theta_station_error=error,velocity_decomposition_error=identity,roots=root_records))
    output.parent.mkdir(parents=True,exist_ok=True)
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=rows,pins=pins,
        source_rule='amake.f:139-145 and348-367; sgutil.f:235-301. Sspace1 samples cosine at half angles within each declared section interval. These are not arithmetic midpoints.',
        conclusion='Main-wing receiver locations change materially; winglet root receivers coincide to rounding. The root velocity change comes from re-solved circulation, not relocating the root sampling point.',
        scope='Saved-field/source audit; no solver calls, production changes or primary passes.')
    output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':main()
