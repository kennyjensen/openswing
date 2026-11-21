"""Independent axial mass/spring mechanics; standard library, no solver imports."""
from math import sqrt,sin,cos
from fractions import Fraction
M=2.;K=500.;W=sqrt(K/M);Q0=-M*.4/K

def target(t):return (.3*t*t-.1*t**3,.6*t-.3*t*t,.6*(1-t))
def continuous(t):
 p,v,a=target(t)
 q=-.6/W**2+.6/W**2*t+(.6-.4)/W**2*cos(W*t)-.6/W**3*sin(W*t)
 u=.6/W**2-(.6-.4)/W*sin(W*t)-.6/W**2*cos(W*t)
 return dict(time=t,extension=q,local_velocity=u,local_acceleration=-W**2*q-a,
             engine_force=-K*q,position=p,velocity=v,acceleration=a)

def linear_solve(a,b):
 a=[list(row)+[value] for row,value in zip(a,b)];n=len(b)
 for j in range(n):
  pivot=max(range(j,n),key=lambda i:abs(a[i][j]));a[j],a[pivot]=a[pivot],a[j]
  assert abs(a[j][j])>1e-15
  v=a[j][j];a[j]=[x/v for x in a[j]]
  for i in range(n):
   if i==j:continue
   v=a[i][j];a[i]=[x-v*y for x,y in zip(a[i],a[j])]
 return [r[-1] for r in a]

def radau(times,initial=(Q0,0.)):
 r=sqrt(6);c=[(4-r)/10,(4+r)/10,1.]
 A=[[(88-7*r)/360,(296-169*r)/1800,(-2+3*r)/225],
    [(296+169*r)/1800,(88+7*r)/360,(-2-3*r)/225],
    [(16-r)/36,(16+r)/36,1/9]]
 O=[[0.,1.],[-K/M,0.]];y=list(initial);out=[y.copy()]
 for t0,t in zip(times,times[1:]):
  h=t-t0;matrix=[];rhs=[]
  for i in range(3):
   for d in range(2):
    matrix.append([float(i==j and d==e)-h*A[i][j]*O[d][e] for j in range(3) for e in range(2)])
    rhs.append(sum(O[d][e]*y[e] for e in range(2))-(target(t0+c[i]*h)[2] if d==1 else 0.))
  stages=linear_solve(matrix,rhs)
  y=[y[d]+h*sum(A[2][i]*stages[2*i+d] for i in range(3)) for d in range(2)];out.append(y)
 return out

def bdf(times,order):
 # Differentiate Lagrange polynomials at the new time using exact rationals.
 Q=Fraction;ts=[Q(str(t)) for t in times];y=[Q(-1,625),Q(0)];out=[y.copy()]
 for i,t in enumerate(ts[1:],1):
  count=2 if i==1 or order==1 else 3;nodes=[ts[i-j]-t for j in range(count)];weights=[]
  for j,node in enumerate(nodes):
   poly=[Q(1)]
   for k,other in enumerate(nodes):
    if k==j:continue
    next=[Q(0)]*(len(poly)+1)
    for degree,value in enumerate(poly):next[degree]-=value*other/(node-other);next[degree+1]+=value/(node-other)
    poly=next
   weights.append(poly[1])
  a=weights[0];rq=-sum(weights[j]*out[i-j][0] for j in range(1,count))
  rv=-Q(3,5)*(1-t)-sum(weights[j]*out[i-j][1] for j in range(1,count))
  q=(rv+a*rq)/(Q(250)+a*a);v=a*q-rq;y=[q,v];out.append(y)
 return [[float(q),float(v)] for q,v in out]

def discrete_step(history,time,order):
 """Original oscillator equations with the recorded integration formula."""
 if order==5:return radau([history[-1][0],time],history[-1][1])[1]
 h=time-history[-1][0]
 if order==1:weights=[1/h,-1/h]
 else:
  k=history[-1][0]-history[-2][0]
  weights=[(2*h+k)/(h*(h+k)),-(h+k)/(h*k),h/(k*(h+k))]
 a=weights[0]
 rq=-sum(w*history[-j][1][0] for j,w in enumerate(weights[1:],1))
 rv=-target(time)[2]-sum(w*history[-j][1][1] for j,w in enumerate(weights[1:],1))
 q=(rv+a*rq)/(K/M+a*a)
 return [q,a*q-rq]

def verify(data):
 ss=data['snapshots'];history=[];records=[];expected=[Q0,0.]
 assert ss[0]['time']==0.,'Reference starts at the retained physical initial state'
 for i,s in enumerate(ss):
  t=s['time']
  if i:expected=discrete_step(history,t,s['order'])
  qd,ud=expected;ref=continuous(t);a=target(t)[2];state=s['restart']['state']
  q=state['network']['positions'][-1][1]-2;u=s['local_velocity'][-1][1]
  dd=s['local_acceleration'][-1][1];force=s['operating_values']['power.1'];frame=s['frame']
  defects=dict(spring_inertia=abs(M*(dd+a)+K*q),root_force=abs(force+K*q),
   position=abs(frame['position_earth'][1]-ref['position']),
   velocity=abs(frame['velocity_origin_body'][1]-ref['velocity']),
   acceleration=abs(frame['acceleration_reference_body'][1]-a),
   free_x=abs(frame['position_earth'][0]+10*t),discrete_q=abs(q-qd),
   discrete_u=abs(u-ud),discrete_force=abs(force+K*qd))
  assert max(defects.values())<1e-7,(t,defects)
  assert s['converged'] and s['residual']<=1e-8
  records.append(dict(time=t,defects=defects,continuous_q_error=abs(q-ref['extension']),
   continuous_force_error=abs(force-ref['engine_force']),continuous_u_error=abs(u-ref['local_velocity'])))
  history.append((t,expected))
 assert abs(ss[0]['local_acceleration'][-1][1]+.2)<1e-7
 assert abs(ss[0]['operating_values']['power.1']-.8)<1e-7
 if 'launch_transition' in data:
  transition=data['launch_transition'];before=transition['before_input']
  assert max(transition['held_state_max_error'].values())<1e-12
  assert before['restart_scope']=='saved_equilibrium_source_only'
  assert 'position_history' not in before['input_context']['state']
  assert abs(before['snapshot']['frame']['acceleration_reference_body'][1]-.4)<1e-12
  assert before['snapshot']['local_acceleration'][-1]==[0.,0.,0.]
  assert data['restart_context']['setup']['saved_history_scope']['version']==4
 return dict(status='PASS',records=records,production_solver_imports=0,
  maximum_continuous_force_error=max(r['continuous_force_error'] for r in records))

if __name__=='__main__':
 import argparse,json
 from pathlib import Path
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--result',required=True,type=Path)
 parser.add_argument('--report',required=True,type=Path)
 args=parser.parse_args();report=verify(json.loads(args.result.read_text()))
 args.report.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(status=report['status'],snapshots=len(report['records']),
  maximum_continuous_force_error=report['maximum_continuous_force_error'])))
