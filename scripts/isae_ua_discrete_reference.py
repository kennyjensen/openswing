"""Independent discrete UA-2 equations from unsteady theory Eqs.123-128.

Backward-difference weights come from polynomial moment conditions. The
straight-wing aerodynamic integrals are independent of production geometry,
residuals, loads and integration. No production module is imported.
"""
import math
import numpy as np


def derivative_weights(times,index):
    """Derivative of the interpolating polynomial at the current time."""
    if index<1 or index>=len(times):raise ValueError('A noninitial time index is required')
    h=times[index]-times[index-1]
    if not h>0:raise ValueError('Times must increase')
    if index==1:return np.array([1.,-1.,0.])/h
    nodes=np.array([0.,-1.,(times[index-2]-times[index])/h])
    if not nodes[2]<-1:raise ValueError('Times must increase')
    weights=np.linalg.solve(np.vstack((np.ones(3),nodes,nodes**2)),np.array([0.,1.,0.]))/h
    # Enforce the exact constant moment in the numerically stable difference form.
    weights[1]=-weights[0]-weights[2]
    return weights


def kinematics(times,acceleration,*,position0=.25,velocity0=0.):
    times=np.asarray(times);acceleration=np.asarray(acceleration)
    if acceleration.shape!=times.shape:raise ValueError('One acceleration at every time required')
    velocity=np.empty(len(times));position=np.empty(len(times))
    velocity[0]=velocity0;position[0]=position0
    for i in range(1,len(times)):
        k0,_,k2=derivative_weights(times,i);older=max(0,i-2)
        velocity[i]=velocity[i-1]+(acceleration[i]-k2*(velocity[older]-velocity[i-1]))/k0
        position[i]=position[i-1]+(velocity[i]-k2*(position[older]-position[i-1]))/k0
    return velocity,position


def circulation_residual_jacobian(wing,gamma,previous,older,coefficients,velocity,*,speed=10.):
    k0,_,k2=coefficients
    incident=math.hypot(speed,velocity);ex=speed/incident
    downwash=wing.H@gamma
    local=np.sqrt(incident**2+downwash**2)
    tangency=-velocity-ex*(wing.C@gamma)
    rate=k0*(gamma-previous)+k2*(older-previous)
    residual=rate-np.pi/2*local*tangency
    jacobian=k0*np.eye(wing.panels)-np.pi/2*(tangency*downwash/local)[:,None]*wing.H+np.pi/2*ex*local[:,None]*wing.C
    return residual,jacobian


def discrete_trajectory(wing,times,velocity,acceleration,*,speed=10.):
    """Solve each coupled circulation step with an independent analytic Newton matrix."""
    times=np.asarray(times);velocity=np.asarray(velocity);acceleration=np.asarray(acceleration)
    if velocity.shape!=times.shape or acceleration.shape!=times.shape or times[0]!=0:
        raise ValueError('Matching histories from time zero required')
    gamma=np.zeros((len(times),wing.panels));rate=np.zeros_like(gamma);lift=np.empty(len(times));iterations=[]
    lift[0]=wing.fields(gamma[0],velocity[0],acceleration[0],speed=speed,rate=rate[0])['CL']
    maximum_residual=0.
    for i in range(1,len(times)):
        coefficients=derivative_weights(times,i);previous=gamma[i-1];older=gamma[max(0,i-2)]
        current=previous.copy()
        for iteration in range(13):
            residual,jacobian=circulation_residual_jacobian(wing,current,previous,older,coefficients,velocity[i],speed=speed)
            error=float(np.max(abs(residual)))
            if error<1e-11:break
            current-=np.linalg.solve(jacobian,residual)
        else:raise RuntimeError(f'Independent circulation solve did not converge at step {i}: {error:g}')
        maximum_residual=max(maximum_residual,error);iterations.append(iteration)
        gamma[i]=current
        rate[i]=coefficients[0]*(current-previous)+coefficients[2]*(older-previous)
        lift[i]=wing.fields(current,velocity[i],acceleration[i],speed=speed,rate=rate[i])['CL']
    return dict(circulation=gamma,circulation_rate=rate,CL=lift,maximum_equation_residual=maximum_residual,
        maximum_newton_iterations=max(iterations),total_newton_updates=sum(iterations))
