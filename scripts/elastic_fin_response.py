"""Independent discrete-aero/continuous-rod harmonic feedback assembly.

No production imports. Mechanical node compliance is supplied from the
independent spatial-rod boundary problem, including its loaded geometric
stiffness and real inertia. The aerodynamic map supplies apparent mass once.
Exact condensation to receiving nodes is not a modal approximation.
"""
import numpy as np
from scipy.linalg import lu_factor, lu_solve, get_lapack_funcs
from elastic_fin_kinematics import NodalSampler
from elastic_fin_aero import AeroMap


def material_and_sampling(fixture, fin_stations):
    """Literal fin properties and analytic Glauert receivers on a straight jig.

    Material chord is independently interpolated with the already validated
    split natural-spline table utility. Flap slope retains literal -0.01745.
    """
    from boom_fin_reference import Tables
    t = np.asarray(fin_stations)
    lo, hi = -3.5, 5.
    if t[0] != lo or t[-1] != hi or np.any(np.diff(t) <= 0):
        raise ValueError('The full increasing fin span must be retained')
    theta = np.arccos(np.clip(1-2*(t-lo)/(hi-lo), -1, 1))
    tm = lo+(hi-lo)*(1-np.cos((theta[:-1]+theta[1:])/2))/2
    f = (tm-t[:-1])/np.diff(t)
    table = Tables(fixture['properties']['fin'])
    def chord(stations):
        return np.array([table.at('chord',s,mid) for s,mid in zip(stations,tm)])
    n = len(tm)
    material = {key: np.zeros(n) for key in AeroMap.scalar_material}
    material.update(chord=chord(tm), chord0=chord(t[:-1]), chord1=chord(t[1:]),
                    Xax=np.full(n,.25), Xax0=np.full(n,.25), Xax1=np.full(n,.25),
                    CLa=np.full(n,6.2), dCLdF3=np.full(n,-.01745*6.2), Cdf=np.full(n,.015))
    return material, tm, f


class Feedback:
    def __init__(self, sampler, aero, gamma, *, observer=None):
        self.sampler, self.aero = sampler, aero
        self.gamma = np.asarray(gamma, dtype=float)
        self.nn, self.ng = sampler.nn, len(self.gamma)
        self.observer = observer
        self.calls = 0

    def evaluate(self, q, v, a, gamma, gd, control):
        self.calls += 1
        section = self.sampler.sample(q,v,a)
        value = self.aero.evaluate(section,gamma,gd,control,lag=True)
        result = dict(residual=value['residual'],
                      nodal_wrench=self.sampler.transfer(section,value['strip_force'],value['strip_moment_axis']),
                      wrenches=value['wrenches'],
                      family_forces=value['family_forces'],family_moments_axis=value['family_moments_axis'],
                      cp_velocity=value['cp_velocity'],velocity=value['velocity'],axis_velocity=value['axis_velocity'])
        for key, term in value['strip_terms'].items():
            result[key+'_force']=term['force']
            result[key+'_moment_axis']=term['moment_axis']
        if self.observer is not None:
            self.observer(self.calls,dict(q=q,v=v,a=a,gamma=gamma,gamma_dot=gd,control=control),section,value,result)
        return result

    def base(self):
        zero = np.zeros((self.nn,6))
        return self.evaluate(zero,zero,zero,self.gamma,np.zeros(self.ng),0.)

    def derivatives(self, epsilon):
        """Complex derivatives of every physical output; no directional fitting.

        Non-fin node columns are identically zero in the explicit aero map.
        Elastic coupling to those nodes enters through the continuum Green map.
        Each geometry, rate, acceleration, circulation and input block is saved.
        """
        if not 0 < epsilon < 1e-6:
            raise ValueError('Complex-step width must be frozen and positive')
        baseline = self.base()
        blocks = {}
        sizes = dict(q=6*self.nn, v=6*self.nn, a=6*self.nn,
                     gamma=self.ng, gamma_dot=self.ng, control=1)
        active_nodes = np.unique(self.sampler.ends)
        active_motion = (6*active_nodes[:,None]+np.arange(6)).ravel()
        for name,size in sizes.items():
            outputs = {k: np.zeros((v.size,size)) for k,v in baseline.items()}
            active = active_motion if name in ('q','v','a') else range(size)
            for j in active:
                args = dict(q=np.zeros((self.nn,6),complex),v=np.zeros((self.nn,6),complex),
                            a=np.zeros((self.nn,6),complex),gamma=self.gamma.astype(complex),
                            gamma_dot=np.zeros(self.ng,complex),control=np.zeros(1,complex))
                args[name].reshape(-1)[j] += 1j*epsilon
                value = self.evaluate(args['q'],args['v'],args['a'],args['gamma'],args['gamma_dot'],args['control'][0])
                for key in outputs:
                    outputs[key][:,j] = np.imag(value[key]).ravel()/epsilon
            blocks[name] = outputs
        return dict(blocks=blocks,shapes={k:v.shape for k,v in baseline.items()},base=baseline,
                    epsilon=epsilon,evaluations=self.calls,
                    fields=self.aero.field_integrations,field_sets=self.aero.field_sets)


def harmonic(compliance, derivative, frequency_hz):
    """Close circulation feedback around the exact receiving-node Green map.

    Compliance columns: six gauge wrenches/node, then physical tip Fy and Mz.
    Final inputs are native rudder F3 and that physical tip Mz, in this order.
    """
    blocks, shapes = derivative['blocks'], derivative['shapes']
    if compliance['diagnostics']['frequency_Hz'] != frequency_hz:
        raise ValueError('Mechanical Green map belongs to a different frequency')
    nodes = compliance['motion_gauge']
    nn, _, nrhs = nodes.shape
    nm = 6*nn
    if nrhs != nm+2:
        raise ValueError('Unexpected compliance basis ordering')
    ng = blocks['gamma']['residual'].shape[1]
    omega = 2*np.pi*frequency_hz
    H = nodes[:,:,:nm].reshape(nm,nm)
    def coefficients(output):
        u = blocks['q'][output]+1j*omega*blocks['v'][output]-omega**2*blocks['a'][output]
        g = blocks['gamma'][output]+1j*omega*blocks['gamma_dot'][output]
        c = blocks['control'][output][:,0]
        return u,g,c
    Fu,Fg,Fc = coefficients('nodal_wrench')
    Eu,Eg,Ec = coefficients('residual')
    K = np.block([[np.eye(nm)-H@Fu,-H@Fg],[Eu,Eg]])
    rhs = np.zeros((nm+ng,2),complex)
    rhs[:nm,0] = H@Fc
    rhs[:nm,1] = nodes[:,:,-1].ravel()
    rhs[nm:,0] = -Ec
    rows = np.max(abs(K),axis=1)
    if np.any(rows==0):
        raise ValueError('Empty independent coupled row')
    row_scaled = K/rows[:,None]
    columns = np.max(abs(row_scaled),axis=0)
    if np.any(columns==0):
        raise ValueError('Empty independent coupled column')
    scaled = row_scaled/columns[None,:]
    forcing = rhs/rows[:,None]
    lu,piv = lu_factor(scaled)
    rcond,info = get_lapack_funcs('gecon',(scaled,))(lu,np.linalg.norm(scaled,1))
    if info:
        raise ValueError('Independent condition estimate failed')
    solution = lu_solve((lu,piv),forcing)/columns[:,None]
    residual = K@solution-rhs
    denominator = abs(K)@abs(solution)+abs(rhs)
    backward = np.divide(abs(residual),denominator,out=np.zeros_like(denominator),where=denominator!=0)
    if np.any((denominator==0)&(abs(residual)!=0)):
        raise ValueError('Nonzero residual in a zero-denominator row')
    diagnostics = dict(reciprocal_condition=float(rcond),component_backward=float(np.max(backward)),
                       absolute_residual=float(np.max(abs(residual))),
                       available=bool(rcond>=1e-12 and np.max(backward)<=1e-10 and np.all(np.isfinite(solution))))
    out = dict(K=K,rhs=rhs,solution=solution,residual=residual,absolute_equation_denominator=denominator,
               row_scales=rows,column_scales=columns,lu=lu,pivots=piv,diagnostics=diagnostics,
               frequency_hz=frequency_hz,full_reference_unknowns=nm+ng)
    if not diagnostics['available']:
        return out
    u, gamma = solution[:nm],solution[nm:]
    outputs = {}
    for key in shapes:
        U,G,C = coefficients(key)
        output = U@u+G@gamma
        output[:,0] += C
        outputs[key]=output.reshape(tuple(shapes[key])+(2,))
    loads = np.zeros((nrhs,2),complex)
    loads[:nm] = outputs['nodal_wrench'].reshape(nm,2)
    loads[-1,1] = 1.
    recovered = {}
    for key in ('states_gauge','states_physical','clamp_reaction_gauge','fin_joint_reaction_gauge',
                'clamp_reaction_physical','fin_joint_reaction_physical'):
        recovered[key] = compliance[key]@loads
    out.update(motion_gauge=u.reshape(nn,6,2),gamma=gamma,outputs=outputs,
               total_load_basis=loads,recovered=recovered,
               motion_recovery_difference=recovered['states_gauge'][:,:6]-u.reshape(nn,6,2))
    return out
