"""Construct networks for newly accepted ISAE files and retain one rigid replay.

This verifies setup and portability, not structural experimental agreement.
"""
from pathlib import Path
import hashlib,json,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.aero import FlightCondition,solve_rigid
root=Path(__file__).resolve().parents[1];audit=json.loads((root/'docs/validation/reference-compatibility.json').read_text());cache=root/'.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865'
rows=[]
for d in audit['differences']:
 if d['after']['status']!='parsed':continue
 path=d['path'][5:];model=parse_asw((cache/path).read_text());start=time.perf_counter()
 try:n=StaticNetwork(model,8,None,None,[])
 except ValueError as exc:row=dict(path=path,status='rejected',error=type(exc).__name__+': '+str(exc))
 else:row=dict(path=path,status='constructed_not_solved')
 row['source_sha256']=hashlib.sha256((cache/path).read_bytes()).hexdigest();row['seconds']=time.perf_counter()-start;rows.append(row);print(row,flush=True)
(root/'docs/validation/reference-setup.json').write_text(json.dumps(dict(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source_transition_sha256=hashlib.sha256((root/'docs/validation/reference-compatibility.json').read_bytes()).hexdigest(),modules=audit['candidate_modules'],meaning='8-interval structural network construction only, without solving or physical validation',cases=rows),indent=2)+'\n')
path='3 - Structure/CASE - ST3 Low aspect ratio/Vaccum_anaysis/[0_3_90].asw';model=parse_asw((cache/path).read_text());start=time.perf_counter()
r=solve_rigid(model,FlightCondition(speed=30,alpha=4,beta=2,density=1.225,mach=0),panels=12)
(root/'docs/validation/reference-browser-probe.json').write_text(json.dumps(dict(modules=audit['candidate_modules'],path=(cache/path).relative_to(root).as_posix(),source=path,settings=dict(speed=30,alpha=4,beta=2,density=1.225,mach=0,panels=12),result=r),indent=2)+'\n')
print('rigid',time.perf_counter()-start,r['CL'],r['CY'],r['residual'],flush=True)
