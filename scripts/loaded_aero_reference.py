"""Independent loaded finite-wing aerodynamic tangent reference.

No production import. Vortex geometry, section loads and motion are reconstructed
from saved physical nodes and input tables. SO(3) Jacobians are integrated matrix
exponentials, independently of the production trigonometric implementation.
"""
import json,math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.linalg import expm_frechet
from loaded_aero_geometry import rows,prop,interpolate,vortex,JIG,nodal_loads

ROOT=Path(__file__).resolve().parent
PARTS=['lift','Cm','profile','circulation_rate','apparent']

def cross_matrix(v):
 x,y,z=v
 return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])

GAUSS_X,GAUSS_W=np.polynomial.legendre.leggauss(8)
GAUSS_X=(GAUSS_X+1)/2;GAUSS_W=GAUSS_W/2
def jacobian_integral(k,kdot=None):
 # d Exp(k) Exp(-k) = [J(k) dk]x and J(k)=integral_0^1 Exp(t[k]x) dt.
 if kdot is None:
  return np.einsum('g,gij->ij',GAUSS_W,Rotation.from_rotvec(GAUSS_X[:,None]*k).as_matrix())
 return sum(w*expm_frechet(t*cross_matrix(k),t*cross_matrix(kdot),compute_expm=False) for t,w in zip(GAUSS_X,GAUSS_W))

def section_motion(Q,velocity,rates,acceleration,alpha,f):
 v=(1-f[:,None])*velocity[:-1]+f[:,None]*velocity[1:]
 a=(1-f[:,None])*acceleration[:-1]+f[:,None]*acceleration[1:]
 omega=[];angular=[]
 for left,right,wl,wr,al,ar,t in zip(Q[:-1],Q[1:],rates[:-1],rates[1:],alpha[:-1],alpha[1:],f):
  k=Rotation.from_matrix(left.T@right).as_rotvec();J=jacobian_integral(k)
  kd=np.linalg.solve(J,left.T@(wr-wl));z=t*k;zd=t*kd;Ji=jacobian_integral(z)
  rel=left@Ji@zd;omega.append(wl+rel)
  if np.any(kd):
   kdd=np.linalg.solve(J,left.T@(ar-al-np.cross(wl,wr-wl))-jacobian_integral(k,kd)@kd)
   angular.append(al+np.cross(wl,rel)+left@(jacobian_integral(z,zd)@zd+Ji@(t*kdd)))
  else:angular.append(al+left@Ji@(t*np.linalg.solve(J,left.T@(ar-al))))
 return v,np.array(omega),a,np.array(angular)

class Context:
 def __init__(self,case):
  self.case=case;b=self.case['base'];self.data=rows(self.case['source'])
  self.r=np.array([x['position'] for x in b['nodes']]);self.Q=np.array([x['rotation'] for x in b['nodes']]);self.Rn=self.Q@JIG
  self.z=np.array(self.case['jig_positions'])[:,2];self.L=self.z[-1]-self.z[0];self.ds=np.diff(self.z)
  self.t=np.array([x['t'] for x in b['nodes']]);self.theta=np.arccos(2*(self.z-self.z[0])/self.L-1)
  za=self.z[0]+self.L/2*(1+np.cos((self.theta[:-1]+self.theta[1:])/2));self.f=(za-self.z[:-1])/self.ds
  self.tp=self.t[:-1]+self.f*np.diff(self.t);self.ng=len(self.ds);self.nn=len(self.z)
  self.U=self.case['condition']['speed'];self.rho=self.case['condition']['density'];self.chord=float(prop(self.data,'chord',self.t[0]))
  self.G=np.array([x['circulation'] for x in b['strips']]);self.condition=self.case['condition']
  a,be=np.deg2rad([self.condition['alpha'],self.condition['beta']]);self.wind=np.array([np.cos(a)*np.cos(be),-np.sin(be),np.sin(a)*np.cos(be)])
  self.sound=float(self.case['source'].split('Constant\n',1)[1].splitlines()[0].split()[2])
  self.force_scale=.5*self.rho*self.U**2*self.chord*self.L
  self.wrench_scale=np.r_[np.full(3,self.force_scale),np.full(3,self.force_scale*self.chord)]
  # Complete nodal spatial motion basis, in chord/one-radian coordinates.
  fields=np.eye(6*self.nn).reshape(self.nn,6,6*self.nn)
  self.displacements=self.chord*fields[:,:3].transpose(2,0,1)
  self.rotations=fields[:,3:].transpose(2,0,1)
  self.nd=6*self.nn;self.size=3*self.nd+2*self.ng
  self._geometry_key=None;self._geometry=None;self._gravity_key=None;self._gravity=None
  assert not self.condition['freeze_influences'] and self.condition['mach']==0.
  assert not np.any(self.condition['rates'])
  assert not np.any(self.condition['acceleration']) and not np.any(self.condition['angular_acceleration'])
  assert self.condition['ground_effect']==0 and self.condition['gust'] is None
  assert not self.condition['circulation_modes'] and not self.condition['powers'] and not self.condition['controls']
  assert np.max(abs(np.array(self.case['jig_positions'])[:,:2]))<1e-14
  for key in ['chord','Xax','dCLda','alpha','Cm','Cdf','Cdp','CLmin','CLmax']:
   assert np.ptp(self.data[key][:,1])==0.,key

 def state(self,x):
  n=self.nd
  q,qd,qdd=x[:n],x[n:2*n],x[2*n:3*n]
  rv=np.einsum('d,dni->ni',q,self.rotations)
  r=self.r+np.einsum('d,dni->ni',q,self.displacements)
  Q=Rotation.from_rotvec(rv).as_matrix()@self.Q
  v=self.U/self.chord*np.einsum('d,dni->ni',qd,self.displacements)
  w=self.U/self.chord*np.einsum('d,dni->ni',qd,self.rotations)
  a=(self.U/self.chord)**2*np.einsum('d,dni->ni',qdd,self.displacements)
  alpha=(self.U/self.chord)**2*np.einsum('d,dni->ni',qdd,self.rotations)
  G=self.G+x[3*n:3*n+self.ng]*self.U*self.chord
  Gd=x[3*n+self.ng:]*self.U**2
  return r,Q,v,w,a,alpha,G,Gd

 def gravity(self,r,Q):
  key=(r.tobytes(),Q.tobytes())
  if key==self._gravity_key:return self._gravity.copy()
  xx,ww=np.polynomial.legendre.leggauss(12)
  f=np.broadcast_to((xx+1)/2,(self.ng,12))
  _,frames=interpolate(r,Q,f);R=frames@JIG
  tm=(self.t[:-1]+self.t[1:])/2
  gravity=float(self.case['source'].split('Constant\n',1)[1].splitlines()[0].split()[0])
  mu=prop(self.data,'mg',tm)/gravity
  arm=prop(self.data,'Ccg',tm)[:,None,None]*R[:,:,:,0]+prop(self.data,'Ncg',tm)[:,None,None]*R[:,:,:,2]
  force=mu[:,None,None]*self.ds[:,None,None]*ww[None,:,None]/2*np.asarray(self.case['gravity'])
  result=nodal_loads(Q,f,force,np.cross(arm,force))/self.wrench_scale
  self._gravity_key=key;self._gravity=result.ravel()
  return self._gravity.copy()

 def pack(self,residual,parts,position,r,Q,gravity=None):
  out={'residual':np.asarray(residual)}
  for key,(F,M) in parts.items():
   nodal=nodal_loads(Q,self.f,F,M)
   # Uniform spatial translation/rotation must preserve total virtual work.
   np.testing.assert_allclose(nodal[:,:3].sum(0),F.sum(0),rtol=1e-10,atol=1e-12)
   np.testing.assert_allclose((nodal[:,3:]+np.cross(r,nodal[:,:3])).sum(0),(M+np.cross(position,F)).sum(0),rtol=1e-10,atol=1e-12)
   out[key]=(nodal/self.wrench_scale).ravel()
  out['total']=sum(out[k] for k in PARTS)
  out['gravity']=self.gravity(r,Q) if gravity is None else gravity
  return out

 def evaluate(self,x,variant='axis_own_bound_excluded',detail=False):
  r,Q,vn,wn,an,alph, G,Gd=self.state(x)
  rm,Qa=interpolate(r,Q,self.f);R=Qa@JIG;Rn=Q@JIG;c,s,n=R[:,:,0],R[:,:,1],R[:,:,2]
  chord=prop(self.data,'chord',self.tp);xax=prop(self.data,'Xax',self.tp);slope=prop(self.data,'dCLda',self.tp)
  across=np.linalg.norm(np.cross(self.wind,s),axis=1);quarter=(.25-xax)*chord
  hv=rm+(quarter/across)[:,None]*self.wind
  cp=hv+(slope*chord/(4*np.pi)/across)[:,None]*self.wind
  en=r+(((.25-prop(self.data,'Xax',self.t))*prop(self.data,'chord',self.t))/np.linalg.norm(np.cross(self.wind,Rn[:,:,1]),axis=1))[:,None]*self.wind
  v,w,a,ad=section_motion(Q,vn,wn,an,alph,self.f)
  rq=quarter[:,None]*c;rcp=((.25+slope/(4*np.pi)-xax)*chord)[:,None]*c
  kh=rm+rq if variant=='physical_kinematic_arms' else hv
  kc=rm+rcp if variant=='physical_kinematic_arms' else cp
  key=(r.tobytes(),Q.tobytes(),variant)
  if key!=self._geometry_key:
   self._geometry_key=key
   self._geometry=[vortex(hv,en[:-1],en[1:],self.wind,True),vortex(cp,en[:-1],en[1:],self.wind),vortex(rm,en[:-1],en[1:],self.wind,variant in ['axis_own_bound_excluded','physical_kinematic_arms'])]
  V=self.U*self.wind-v-np.cross(w,kh-rm)+np.einsum('ijk,j->ik',self._geometry[0],G)
  Vcp=self.U*self.wind-v-np.cross(w,kc-rm)+np.einsum('ijk,j->ik',self._geometry[1],G)
  Vp=V-(V*s).sum(1)[:,None]*s;speed=np.linalg.norm(Vp,axis=1);va=np.linalg.norm(V,axis=1)
  aa=np.deg2rad(prop(self.data,'alpha',self.tp));normal=np.sin(aa)[:,None]*c+np.cos(aa)[:,None]*n
  lag=Gd if self.condition['aero_lag'] else np.zeros_like(Gd)
  tangency=(Vcp*normal).sum(1)-2/np.pi*lag/speed
  cl=2*G/(chord*speed);width=self.condition['stall_width']
  leak=width*(np.logaddexp(0.,(cl-prop(self.data,'CLmax',self.tp))/width)-np.logaddexp(0.,(prop(self.data,'CLmin',self.tp)-cl)/width))
  leak=speed/slope*self.condition['stall_factor']*leak if self.condition['stall'] else np.zeros_like(speed)
  residual=(tangency-leak)/self.U;length=np.linalg.norm(np.diff(r,axis=0),axis=1)
  Fl=self.rho*G[:,None]*np.cross(V,s)*length[:,None]
  Fr=self.rho*(chord*lag/speed)[:,None]*np.cross(V,s)*length[:,None]
  Fp=(.5*self.rho*va[:,None]*V*(chord*prop(self.data,'Cdf',self.tp))[:,None]+.5*self.rho*speed[:,None]*Vp*(chord*prop(self.data,'Cdp',self.tp))[:,None]+2*self.rho*Vp/speed[:,None]*(tangency**2*chord)[:,None])*length[:,None]
  Cm=prop(self.data,'Cm',self.tp)/np.sqrt(1-(speed/self.sound)**2)
  Mc=(.5*self.rho*speed**2*chord**2*Cm*length)[:,None]*s
  axis=self.U*self.wind-v+np.einsum('ijk,j->ik',self._geometry[2],G)
  arm=(.5-xax)[:,None]*chord[:,None]*c
  acceleration=a+np.cross(ad,arm)+np.cross(w,np.cross(w,arm))
  mass=self.rho*np.pi/4*chord**2*length
  rate=(np.cross(axis,w)*n).sum(1)
  Fa=(mass*(rate-(acceleration*n).sum(1)))[:,None]*n
  Ma=(-mass*(chord/4*rate+chord**2/32*(s*ad).sum(1)))[:,None]*s+np.cross(arm,Fa)
  parts=dict(lift=(Fl,np.cross(rq,Fl)),Cm=(np.zeros_like(Fl),Mc),profile=(Fp,np.zeros_like(Fl)),circulation_rate=(Fr,np.cross(rq,Fr)),apparent=(Fa,Ma))
  out=self.pack(residual,parts,rm,r,Q)
  if detail:return out,dict(axis_velocity=axis,force_velocity=V,frames=R,position=rm,velocity=v,rates=w,acceleration=a,angular_acceleration=ad,quarter_arm=rq,virtual_quarter_arm=hv-rm,control_arm=rcp,virtual_control_arm=cp-rm)
  return out

def tangent(evaluator,context,step):
 columns=[]
 for j in range(context.size):
  x=np.zeros(context.size);x[j]=step
  plus=evaluator(x);minus=evaluator(-x)
  columns.append({k:(plus[k]-minus[k])/(2*step) for k in plus})
 return {k:np.array([c[k] for c in columns]).T for k in columns[0]}

def harmonic(T,c,freq):
 n=c.nd;g=c.ng
 prescribed=np.vstack([np.eye(n),1j*freq*np.eye(n),-freq**2*np.eye(n)])
 R=T['residual'];D=R[:,3*n:3*n+g]+1j*freq*R[:,3*n+g:]
 gamma=np.linalg.solve(D,-R[:,:3*n]@prescribed)
 state=np.vstack([prescribed,gamma,1j*freq*gamma])
 loads={k:v@state for k,v in T.items() if k!='residual'}
 loads['apparent_acceleration']=T['apparent'][:,2*n:3*n]@prescribed[2*n:3*n]
 loads['apparent_pitch_rate']=T['apparent'][:,n:2*n]@prescribed[n:2*n]
 return loads,gamma,float(np.max(abs(R@state))),float(np.linalg.cond(D))
