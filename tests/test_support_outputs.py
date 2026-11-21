"""Support output matrices against high-precision nonlinear physical loads."""
from decimal import Decimal,localcontext
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem,output_perturbation
from openswing.support_outputs import SupportTangent,SupportUnavailable,support_outputs
from test_direct_circulation import model_for,state_for


CASES=['ground0','ground1','ground2','articulated','dae',
       'tension','compression','wire_taut','wire_slack','zero_stiffness']


def system_for(name):
    model=model_for(name if name in ('articulated','dae') else 'flexible')
    if name.startswith('ground'):model.records['ground'][0][-1]=int(name[-1])
    if name in ('tension','compression','wire_taut','wire_slack','zero_stiffness','boundary'):
        rest=-.5 if name in ('tension','wire_taut') else 0 if name=='boundary' else .5
        model.records['strut']=[np.array([1,8,1.1,8.2,-.1,-2,1,-3,rest,0 if name=='zero_stiffness' else 24000.])]
    model.reference[1]=[.4,-.6,.25]
    n=StaticNetwork(model,4,FlightCondition(speed=30,alpha=5,mach=.1),None,[],
        strut_mode='wire' if name.startswith('wire') or name=='boundary' else 'bilateral')
    x=state_for(n)
    if name=='boundary':x[:6*n.nn]=0
    else:x[:6*n.nn].reshape(n.nn,6)[:,3:]+=[.1,-.15,.2]
    return DynamicSystem(n,x,'free')


def high_precision_support(system,vector,step='1e-20'):
    """Central differences of nonlinear supports at 80-digit precision.

    Evaluate the physical axial law and exponential rotation, without using
    the implemented tangent or any stiffness formula.
    """
    n=system.network
    with localcontext() as context:
        context.prec=80;D=lambda x:Decimal.from_float(float(x));h=Decimal(step)
        dec=lambda values:[D(x) for x in values]
        cross=lambda a,b:[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
        add=lambda a,b:[x+y for x,y in zip(a,b)]
        sub=lambda a,b:[x-y for x,y in zip(a,b)]
        norm=lambda a:sum(x*x for x in a).sqrt()
        ref=dec(n.model.reference[1]);parts=[]
        for v in (np.real(vector),np.imag(vector)):
            totals=[]
            for sign in (1,-1):
                z=[sign*h*D(x) for x in v];force=[Decimal(0)]*3;moment=force.copy()
                start=6*(n.nn+n.ne)
                for c in n.constraints:
                    if c['b'] is not None:continue
                    i=c['a'];a=start+c['sl'].start;b=start+c['sl'].stop
                    reaction=[D(x)+dz for x,dz in zip(system.base[a:b],z[a:b])]
                    f=[D(n.F)*x for x in reaction[:3]] if c['type']!=2 else [Decimal(0)]*3
                    m=[D(n.F)*D(n.L)*x for x in reaction[-3:]] if c['type']!=1 else [Decimal(0)]*3
                    position=add(dec(system.r0[i]),[D(system.L)*x for x in z[6*i:6*i+3]])
                    force=add(force,f);moment=add(moment,add(m,cross(sub(position,ref),f)))
                for row in n.struts:
                    i=n.node(*row[:2]);offset=sub(dec(row[2:5]),dec(n.rj[i]))
                    offset=[sum(D(q)*x for q,x in zip(line,offset)) for line in system.Q0[i]]
                    rotated=offset.copy();term=offset.copy();angles=z[6*i+3:6*i+6]
                    for order in range(1,30):
                        term=[x/Decimal(order) for x in cross(angles,term)];rotated=add(rotated,term)
                    position=add(add(dec(system.r0[i]),[D(system.L)*x for x in z[6*i:6*i+3]]),rotated)
                    anchor=dec(row[5:8]);delta=sub(anchor,position);length=norm(delta)
                    rest=norm(sub(anchor,dec(row[2:5])))+D(row[8]);extension=length-rest
                    if n.tension_only:extension=max(Decimal(0),extension)
                    f=[D(row[9])*extension/rest*x/length for x in delta]
                    force=add(force,f);moment=add(moment,cross(sub(anchor,ref),f))
                totals.append(force+moment)
            parts.append(np.array([float((a-b)/(2*h)) for a,b in zip(*totals)]))
        return parts[0]+1j*parts[1]


def snapshots_for(system,vector,step=1e-6):
    result=[]
    for part in (vector.real,vector.imag):
        for sign in (1,-1):result.append(system.snapshot(sign*step*part,sign*step*.7*part)[1])
    return result


@pytest.mark.parametrize('name',CASES)
def test_complete_support_matrix_against_high_precision_nonlinear_law(name):
    s=system_for(name);v=np.random.default_rng(49).normal(size=s.size)+1j*np.random.default_rng(63).normal(size=s.size)
    tangent=SupportTangent(s);snapshots=snapshots_for(s,v)
    values=tangent.apply(v,snapshots);actual=np.r_[values['support_force'],values['support_moment']]
    expected=high_precision_support(s,v)
    assert np.max(abs(actual-expected)/(1+abs(expected)))<2e-11,(name,actual,expected)
    # Compare with the original full network output, including ground supports,
    # internal joint cancellation and all body-fixed strut anchors.
    arrays=[np.r_[q['support_force'],q['support_moment']] for q in snapshots]
    physical=((arrays[0]-arrays[1])+1j*(arrays[2]-arrays[3]))/(2e-6)
    assert np.max(abs(actual-physical)/(1+abs(actual)))<2e-7,(name,actual,physical)
    # All non-position/non-reaction state columns have exactly zero support map.
    n=s.network;allowed=np.r_[np.arange(6*n.nn),np.arange(6*(n.nn+n.ne),n.gamma_start)]
    excluded=np.setdiff1d(np.arange(s.size),allowed)
    assert tangent.matrix[:,excluded].nnz==0


def test_reuse_ownership_and_physical_mutation_invalidation():
    s=system_for('tension');v=np.ones(s.size,dtype=complex);snapshots=snapshots_for(s,v)
    before=support_outputs(s,v,snapshots);first=s._support_output_tangent
    support_outputs(s,2*v,snapshots);assert s._support_output_tangent is first
    assert not first.matrix.data.flags.writeable and not first.matrix.indices.flags.writeable
    other=system_for('tension');assert not first.matches(other)
    # Unconnected nodes do not enter this output map; support nodes do.
    old=s.r0[0,0];s.r0[0,0]+=.25
    assert first.matches(s);s.r0[0,0]=old
    ground=s.network.constraints[0]['a']
    for array,index in [(s.base,6*(s.network.nn+s.network.ne)),(s.r0,(ground,0)),
                        (s.Q0,(-1,0,0)),(s.network.model.reference,(1,0)),
                        (s.network.struts[0],9)]:
        old=array[index];array[index]+=.25
        try:assert not first.matches(s)
        finally:array[index]=old
    after=support_outputs(s,v,snapshots)
    for key in before:np.testing.assert_array_equal(before[key],after[key])
    assert first.matches(s)


def test_budget_nonfinite_and_wire_boundary_keep_physical_fallback():
    s=system_for('tension')
    try:SupportTangent(s,limit=0)
    except SupportUnavailable as e:assert 'budget' in str(e)
    else:raise AssertionError('unbounded storage')
    s.base[6*(s.network.nn+s.network.ne)]=np.nan
    try:SupportTangent(s)
    except SupportUnavailable as e:assert 'Nonfinite' in str(e)
    else:raise AssertionError('nonfinite baseline')
    s=system_for('boundary');v=np.ones(s.size,dtype=complex)
    # Set an exactly represented zero extension using the same unloaded norm.
    row=s.network.struts[0];i=s.network.node(*row[:2]);row[2:5]=s.r0[i]
    assert support_outputs(s,v,snapshots_for(s,v))=={}
    assert 'boundary' in s.support_output_diagnostics['fallback']
    s=system_for('wire_taut');t=SupportTangent(s);snaps=snapshots_for(s,v[:s.size])
    snaps[0]['struts'][0]['slack']=True
    try:t.apply(v[:s.size],snaps)
    except SupportUnavailable as e:assert 'boundary' in str(e)
    else:raise AssertionError('wire branch was ignored')


def test_public_output_has_exact_complex_linearity_across_input_amplitudes():
    s=system_for('tension');rng=np.random.default_rng(841)
    v=rng.normal(size=s.size)+1j*rng.normal(size=s.size);expected=high_precision_support(s,v)
    for amplitude in (1e-12,1.,1e12):
        out=output_perturbation(s,amplitude*v,.3j*amplitude*v)
        actual=np.concatenate([np.array(out['global'][key]['real'])+1j*np.array(out['global'][key]['imag']) for key in ('support_force','support_moment')])/amplitude
        assert np.max(abs(actual-expected)/(1+abs(expected)))<2e-11
