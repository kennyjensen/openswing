"""Independent scalar checks only; no production imports or physical solves."""
import importlib.util
import math
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('frozen_scalar_oracle',Path(__file__).with_name('oracle.py'))
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)


def integrate(f,a,b,tolerance=2e-12):
    def simpson(a,b,fa,fm,fb):
        return (b-a)*(fa+4*fm+fb)/6
    def recurse(a,b,fa,fm,fb,whole,tol,depth):
        m=(a+b)/2;fl,fr=f((a+m)/2),f((m+b)/2)
        left=simpson(a,m,fa,fl,fm);right=simpson(m,b,fm,fr,fb)
        error=left+right-whole
        if abs(error)<=15*tol:
            return left+right+error/15
        if depth==0:
            raise AssertionError('Independent integral did not converge.')
        return recurse(a,m,fa,fl,fm,left,tol/2,depth-1)+recurse(m,b,fm,fr,fb,right,tol/2,depth-1)
    fa,fm,fb=f(a),f((a+b)/2),f(b)
    return recurse(a,b,fa,fm,fb,simpson(a,b,fa,fm,fb),tolerance,28)


class ScalarChecks(unittest.TestCase):
    nodes=[-2.95,-2.1,-.7,.7,2.1,2.95]
    samples=[-2.6,-1.5,0.,1.5,2.6]
    gamma=[.7,1.5,1.8,1.5,.7]

    def calculation(self,alpha,gamma=None):
        return oracle.calculate(self.nodes,self.samples,self.gamma if gamma is None else gamma,alpha)

    def test_kernel_against_three_direct_line_integrals(self):
        for a,b,y,d in [(-1.3,.7,-.2,.500001),(-1.3,.7,1.2,.5),(-1.3,.7,-.2,0.)]:
            bound=0. if d==0 else integrate(lambda s:-d/(d*d+(y-s)**2)**1.5,a,b)
            def ray(eta):
                def integrand(t):
                    if t==1:return 0.
                    x=t/(1-t)
                    return eta/((d-x)**2+eta*eta)**1.5/(1-t)**2
                return integrate(integrand,0.,1.)
            expected=(bound+ray(y-b)-ray(y-a))/(4*math.pi)
            self.assertAlmostEqual(oracle.wpair(y,a,b,d),expected,delta=4e-12)

    def test_actual_wind_and_fixed_wake_are_distinct(self):
        zero,angled=self.calculation(0.),self.calculation(18.091)
        for a,b in zip(zero['strips'],angled['strips']):
            self.assertEqual(a['w_hv'],b['w_hv'])
            self.assertEqual(a['w_cp'],b['w_cp'])
            self.assertEqual(a['hv'],b['hv'])
            self.assertNotEqual(a['velocity'],b['velocity'])
        self.assertEqual(angled['values']['CLi'],zero['values']['CLi'])
        self.assertEqual(angled['values']['CDi'],zero['values']['CDi'])
        self.assertNotEqual(angled['values']['CDi_near'],angled['values']['CDi'])

    def test_projected_force_and_quarter_chord_identities(self):
        for alpha in (0.,.029369,1.9971,18.091,-18.091):
            c=self.calculation(alpha);i=c['identities'];v=c['values']
            self.assertAlmostEqual(i['near_circulation_CL'],i['near_circulation_CL_from_fixed_wake'],delta=3e-17)
            self.assertAlmostEqual(v['CDi_near'],i['near_circulation_CD_from_fixed_wake'],delta=3e-17)
            self.assertAlmostEqual(v['Cm'],i['Cm_from_fixed_wake'],delta=3e-17)

    def test_reflection_and_residual_parity(self):
        p=self.calculation(18.091);n=self.calculation(-18.091,[-g for g in self.gamma])
        for k in ('CL','CLi','Cm'):
            self.assertAlmostEqual(p['values'][k],-n['values'][k],delta=3e-16)
        for k in ('CD','CDi','CDi_near','CDp','efficiency'):
            self.assertAlmostEqual(p['values'][k],n['values'][k],delta=3e-16)
        for a,b in zip(p['strips'],n['strips']):
            self.assertAlmostEqual(a['residual'],-b['residual'],delta=3e-16)

    def test_profile_force_is_parallel_to_local_velocity(self):
        c=self.calculation(18.091)
        for s in c['strips']:
            f,v=s['profile_force'],s['velocity']
            self.assertAlmostEqual(f[0]*v[2]-f[2]*v[0],0.,delta=2e-11)


if __name__=='__main__':
    unittest.main(verbosity=2)
