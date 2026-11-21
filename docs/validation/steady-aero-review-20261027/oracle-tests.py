"""Independent integral and symmetry tests; no production/numerical imports."""
import ast,math,unittest
from pathlib import Path
tree=ast.parse(Path(__file__).with_name('oracle.py').read_text())
scope={'math':math}
exec(compile(ast.Module(body=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='wpair'],type_ignores=[]),'<oracle-wpair>','exec'),scope)
wpair=scope['wpair']

def integrate(f,a,b,tol=2e-12):
    def simpson(a,b,fa,fm,fb):return (b-a)*(fa+4*fm+fb)/6
    fa,fm,fb=f(a),f((a+b)/2),f(b)
    def recurse(a,b,fa,fm,fb,whole,tol,depth):
        m=(a+b)/2;fl,fr=f((a+m)/2),f((m+b)/2)
        left=simpson(a,m,fa,fl,fm);right=simpson(m,b,fm,fr,fb)
        error=left+right-whole
        if abs(error)<=15*tol:return left+right+error/15
        if depth==0:raise AssertionError('Integral tolerance not reached')
        return recurse(a,m,fa,fl,fm,left,tol/2,depth-1)+recurse(m,b,fm,fr,fb,right,tol/2,depth-1)
    return recurse(a,b,fa,fm,fb,simpson(a,b,fa,fm,fb),tol,28)

def direct_biot_savart(y,a,b,d):
    bound=0. if d==0 else integrate(lambda s:-d/(d*d+(y-s)**2)**1.5,a,b)
    # Independent integration of each infinite filament with l=t/(1-t).
    def ray(eta):
        return integrate(lambda t:eta*(1-t)/((d*(1-t)-t)**2+eta*eta*(1-t)**2)**1.5,0.,1.)
    return (bound+ray(y-b)-ray(y-a))/(4*math.pi)

class OracleTests(unittest.TestCase):
    def test_closed_form_against_three_line_integrals(self):
        for a,b,y,d in [(-1.3,.7,-.2,.500001),(-1.3,.7,.5,.500001),(-1.3,.7,1.2,.5),
                        (-1.3,.7,-2.,-.5),(-1.3,.7,-.2,0.),(-1.3,.7,1.2,0.)]:
            with self.subTest(a=a,b=b,y=y,d=d):
                self.assertAlmostEqual(wpair(y,a,b,d),direct_biot_savart(y,a,b,d),delta=4e-12)
    def test_boundline_is_half_infinite_wake(self):
        y,a,b=.3,-1.,2.
        infinite=(1/(y-b)-1/(y-a))/(2*math.pi)
        self.assertEqual(2*wpair(y,a,b,0.),infinite)
    def test_constant_circulation_internal_wakes_cancel(self):
        nodes=[-2.,-1.8,-.9,.2,.7,1.5,2.]
        for d in [0.,.500001,-.5]:
            actual=math.fsum(wpair(.4,a,b,d) for a,b in zip(nodes,nodes[1:]))
            self.assertAlmostEqual(actual,wpair(.4,nodes[0],nodes[-1],d),delta=2e-15)
    def test_span_reflection(self):
        for d in [0.,.5,-.5]:
            self.assertAlmostEqual(wpair(.4,-1.2,.9,d),wpair(-.4,-.9,1.2,d),delta=2e-16)
    def test_two_dimensional_lift_slope_limit(self):
        a0=6.2832;c=1.;d=a0*c/(4*math.pi);h=1e8
        slope=2/(-wpair(0.,-h,h,d)*c)
        # Finite-span end-ray correction bounded analytically by 2d/h.
        self.assertLess(abs(slope/a0-1),2*d/h)
    def test_dimensional_scaling(self):
        scale=17.3
        self.assertAlmostEqual(scale*wpair(.4*scale,-1.2*scale,.9*scale,.5*scale),wpair(.4,-1.2,.9,.5),delta=3e-16)

if __name__=='__main__':unittest.main(verbosity=2)
