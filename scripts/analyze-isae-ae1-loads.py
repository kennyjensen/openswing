"""Saved-only AE-1 aerodynamic wrench and twist audit (Python stdlib only).

No production imports, model construction, aerodynamic field evaluation,
residual calls, aircraft solves, or changes to the frozen sweep. SO(3) frame
interpolation and stiffness algebra are reconstructed from retained values.
"""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
SELECTED = ((5, 30), (5, 40), (5, 56), (7, 30), (7, 38), (7, 41))
GROUPS = ('lift_force_arm', 'lift_quarter_chord_couple', 'section_pitch_couple', 'profile_force_arm')
I = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]
ZERO = [0., 0., 0.]
# Eight-point Gauss-Legendre rule, used only to integrate the observation map
# along the already saved rotation arc, never to evaluate an aircraft load.
GAUSS = ((-.9602898564975363, .1012285362903763), (-.7966664774136267, .2223810344533745),
         (-.5255324099163290, .3137066458778873), (-.1834346424956498, .3626837833783620),
         (.1834346424956498, .3626837833783620), (.5255324099163290, .3137066458778873),
         (.7966664774136267, .2223810344533745), (.9602898564975363, .1012285362903763))


def pin(path):
    path = Path(path); data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def add(a, b): return [x+y for x, y in zip(a, b)]
def sub(a, b): return [x-y for x, y in zip(a, b)]
def mul(a, x): return [v*x for v in a]
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def norm(a): return math.sqrt(dot(a, a))
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def trans(a): return list(map(list, zip(*a)))
def mv(a, b): return [dot(r, b) for r in a]
def mm(a, b): return [[dot(r, c) for c in trans(b)] for r in a]
def skew(a): return [[0., -a[2], a[1]], [a[2], 0., -a[0]], [-a[1], a[0], 0.]]
def sumv(v): return [sum(row[i] for row in v) for i in range(3)]


def inv3(a):
    # Row cofactor vectors transpose to the adjugate.
    c = [cross(a[1], a[2]), cross(a[2], a[0]), cross(a[0], a[1])]
    det = dot(a[0], c[0]); assert det > 0
    return [[v/det for v in row] for row in trans(c)]


def exp(v):
    theta = norm(v); k = skew(v); k2 = mm(k, k)
    a = 1-theta**2/6+theta**4/120 if theta < 1e-5 else math.sin(theta)/theta
    b = .5-theta**2/24+theta**4/720 if theta < 1e-5 else (1-math.cos(theta))/theta**2
    return [[I[i][j]+a*k[i][j]+b*k2[i][j] for j in range(3)] for i in range(3)]


def log(q):
    v = [(q[2][1]-q[1][2])/2, (q[0][2]-q[2][0])/2, (q[1][0]-q[0][1])/2]
    sn = norm(v); theta = math.atan2(sn, (sum(q[i][i] for i in range(3))-1)/2)
    assert theta < .1, 'This audit assumes the small adjacent arcs of the retained fine mesh.'
    return mul(v, theta/sn if sn else 1.)


def jac(v):
    theta = norm(v); k = skew(v); k2 = mm(k, k)
    a = .5-theta**2/24+theta**4/720 if theta < 1e-4 else (1-math.cos(theta))/theta**2
    b = 1/6-theta**2/120+theta**4/5040 if theta < 1e-4 else (theta-math.sin(theta))/theta**3
    return [[I[i][j]+a*k[i][j]+b*k2[i][j] for j in range(3)] for i in range(3)]


def arc(qa, qb, f): return mm(qa, exp(mul(log(mm(trans(qa), qb)), f)))


def angular_weights(qa, qb, f):
    k = log(mm(trans(qa), qb))
    b = mm(mm(mm(qa, [[f*x for x in row] for row in jac(mul(k, f))]), inv3(jac(k))), trans(qa))
    return [[I[i][j]-b[i][j] for j in range(3)] for i in range(3)], b


def projected_twist(q): return math.atan2(-q[2][0], q[0][0])


def observation_factors(qa, qb, ds):
    # For c'=Q(kappa cross e_c), d atan2(-c_z,c_x)/ds = g_s*k_s+g_n*k_n.
    factors = [0., 0.]
    for point, weight in GAUSS:
        c, s, n = trans(arc(qa, qb, (point+1)/2)); den = c[0]**2+c[2]**2
        factors[0] += weight*ds/2*(c[0]*n[2]-c[2]*n[0])/den
        factors[1] += weight*ds/2*(c[2]*s[0]-c[0]*s[2])/den
    return factors


def tables(source):
    out = []; table = None; in_beam = False
    for original in source.splitlines():
        line = original.split('!')[0].strip()
        if line.startswith('Beam '):
            assert line == 'Beam 1' and not in_beam and not out
            in_beam = True
        elif in_beam and line == 'End': in_beam = False; table = None
        elif in_beam and line.startswith('t '):
            table = dict(names=line.split(), rows=[]); out.append(table)
        elif table is not None and line:
            row = list(map(float, line.split())); assert len(row) == len(table['names'])
            table['rows'].append(row)
    assert len(out) == 3
    return out


def sample_constant_sections(table, t):
    for a, b in zip(table['rows'], table['rows'][1:]):
        if a[0] < t < b[0]:
            assert a[1:] == b[1:], 'Only literal constant sections are covered, no spline assumptions.'
            return dict(zip(table['names'], a))
    raise AssertionError('No strict interior material interval: '+str(t))


class Audit:
    def __init__(self): self.count = 0; self.failures = []; self.maxima = {}
    def check(self, name, value):
        self.count += 1
        if not value: self.failures.append(name)
    def near(self, name, a, b, group, atol=2e-10, rtol=2e-10):
        if isinstance(b, list):
            self.check(name+'.shape', len(a) == len(b))
            for i, (x, y) in enumerate(zip(a, b)): self.near(f'{name}.{i}', x, y, group, atol, rtol)
        else:
            error = abs(a-b); self.maxima[group] = max(error, self.maxima.get(group, 0.))
            self.check(name, math.isfinite(a) and error <= atol+rtol*abs(b))


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sweep', type=Path, default=ROOT/'docs/validation/isae-ae1-sweep.json')
    parser.add_argument('--raw', type=Path, default=Path('/tmp/openswing-isae-ae1-sweep-20261025/native/cases'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=False)
    sweep = json.loads(args.sweep.read_text()); scope_path = ROOT/'docs/validation/isae-ae1-source-scope.json'
    scope = json.loads(scope_path.read_text()); audit = Audit()
    pins = [pin(args.sweep), pin(scope_path), pin(__file__), pin(ROOT/'.reference/asw_theory.txt')]
    for name, digest in sweep['plan']['source_sha256'].items():
        p = ROOT/name
        if name.startswith('openswing/'):
            record = pin(p); pins.append(record); audit.check('kernel pin '+name, record['sha256'] == digest)
    selected = [s for s in sweep['states'] if s['specification']['intervals_per_half'] == 60 and
                (s['specification']['alpha_deg'], s['specification']['speed_m_s']) in SELECTED]
    audit.check('six requested states', len(selected) == 6)
    summaries = []; strip_rows = []; section_rows = []
    for entry in selected:
        path = args.raw/entry['raw']['file']; record = pin(path); pins.append(record)
        audit.check('compressed pin '+path.name, record['sha256'] == entry['raw']['sha256'])
        decoded = gzip.decompress(path.read_bytes())
        audit.check('uncompressed pin '+path.name, hashlib.sha256(decoded).hexdigest() == entry['raw']['uncompressed_sha256'])
        raw = json.loads(decoded); r = raw['result']; spec = raw['specification']; alpha = spec['alpha_deg']; speed = spec['speed_m_s']
        name = f'alpha{alpha}-u{speed:g}'; audit.check(name+'.source', hashlib.sha256(raw['source'].encode()).hexdigest() == raw['source_sha256'])
        geometry, stiffness, aero = tables(raw['source'])
        for row in geometry['rows']:
            g = dict(zip(geometry['names'], row))
            audit.near(name+'.literal geometry', [g['x'],g['y'],g['z'],g['chord'],g['Xax']], [0.,g['t'],0.,.1,.441], 'literal')
        material = sample_constant_sections(aero, 0.)
        audit.near(name+'.literal aero', [material[k] for k in ('dCLda','CLmax','CLmin','alpha','Cm','Cdf','Cdp')], [6.1185,1.1,-1.1,0.,0.,0.,0.], 'literal')
        for k in ('body_force','engine_force','engine_moment','apparent_force','apparent_moment','gravity_body'):
            audit.near(name+'.inactive '+k, r[k], ZERO, 'inactive', atol=0, rtol=0)
        audit.check(name+'.no extra loads', len(r['point_forces']) == 34 and r['struts'] == [] and r['hinges'] == [])
        audit.near(name+'.zero point loads', r['point_forces'], [ZERO]*34, 'inactive', atol=0, rtol=0)
        nodes = r['nodes']; elements = r['elements']; strips = r['strips']; nn = len(nodes)
        audit.check(name+'.layout', nn == 121 and len(elements) == len(strips) == 120)
        rho = r['atmosphere']['density']; freestream = r['reference_flow']['relative_velocity_body']; L = max(n['t'] for n in nodes)
        nodal = {key:[[ZERO[:], ZERO[:]] for _ in nodes] for key in GROUPS}
        records = []
        for j, (strip, element) in enumerate(zip(strips, elements)):
            label = f'{name}.strip{j}'; a, b = nodes[j], nodes[j+1]; qa, qb = a['rotation'], b['rotation']
            f = (strip['t']-element['t0'])/(element['t1']-element['t0']); q = arc(qa, qb, f)
            c, s, n = trans(q); pa, pb = a['position'], b['position']; rm = add(pa, mul(sub(pb, pa), f)); ds = norm(sub(pb, pa))
            audit.near(label+'.position', rm, strip['position'], 'geometry', atol=3e-13, rtol=3e-13)
            audit.near(label+'.length', ds, strip['length'], 'geometry', atol=3e-13, rtol=3e-13)
            audit.near(label+'.axis', [pa,pb], r['geometry'][0]['axis'][j], 'geometry')
            audit.near(label+'.midframe', arc(qa,qb,.5), element['frame'], 'geometry')
            for k, node in enumerate((a,b)):
                chord = trans(node['rotation'])[0]; le = add(node['position'],mul(chord,-.0441)); te=add(node['position'],mul(chord,.0559))
                audit.near(label+'.quad'+str(k), [le,te], [r['geometry'][0]['quads'][j][k],r['geometry'][0]['quads'][j][3-k]], 'physical_chord')
            v = strip['relative_velocity']; vp = sub(v,mul(s,dot(s,v))); V = norm(vp); gamma=strip['circulation']; cl=2*gamma/(.1*V)
            lift = mul(cross(v,s),rho*gamma*ds)
            leakage = V/6.1185*40*.05*(math.log1p(math.exp((cl-1.1)/.05))-math.log1p(math.exp((-1.1-cl)/.05)))
            # CP velocity is not retained. Recover its NORMAL component from
            # saved local residual plus eqs 203-204; no independent CP field claim.
            T = speed*r['circulation_local_residual'][j]+leakage
            profile = mul(vp,2*rho*.1*T*T*ds/V)
            quarter = cross(mul(c,-.0191),lift); section = mul(s,.5*rho*V*V*.1**2*strip['cm']*ds)
            moment = add(quarter,section); force=add(lift,profile)
            for k in ('circulation_rate_force','apparent_force','apparent_moment'):
                audit.near(label+'.inactive '+k,strip[k],ZERO,'inactive',atol=0,rtol=0)
            audit.near(label+'.force',force,strip['force'],'strip_force')
            audit.near(label+'.moment',moment,strip['moment'],'strip_moment')
            audit.near(label+'.cl',cl,strip['cl'],'section_outputs')
            audit.near(label+'.speed',V,strip['normal_speed'],'section_outputs')
            audit.near(label+'.f_aero',dot(lift,n)/ds,strip['f_aero'],'section_outputs')
            audit.near(label+'.da_eff',dot(sub(n,[0.,0.,1.]),v)/norm(v),strip['da_eff'],'section_outputs')
            audit.check(label+'.stall flag', strip['stalled'] == (cl > 1.1 or cl < -1.1))
            wind=mul(freestream,1/speed); hv=add(rm,mul(wind,-.0191/norm(cross(wind,s))))
            audit.near(label+'.HV',hv,strip['velocity_position'],'geometry')
            wa, wb = angular_weights(qa,qb,f)
            values = {'lift_force_arm':(lift,ZERO),'lift_quarter_chord_couple':(ZERO,quarter),
                      'section_pitch_couple':(ZERO,section),'profile_force_arm':(profile,ZERO)}
            for key,(F,M) in values.items():
                for node,weight,w in ((j,1-f,wa),(j+1,f,wb)):
                    nodal[key][node][0]=add(nodal[key][node][0],mul(F,weight))
                    nodal[key][node][1]=add(nodal[key][node][1],mv(trans(w),M))
            row=dict(case=name,alpha_deg=alpha,speed_m_s=speed,index=j,t=strip['t'],span_fraction=strip['t']/L,
                     current_ds_m=ds,current_y_m=rm[1],current_z_m=rm[2],gamma=gamma,cl=cl,stalled=strip['stalled'],cm=strip['cm'],
                     normal_speed_m_s=V,alpha_HV_deg=math.degrees(math.atan2(dot(v,n),dot(v,c))),
                     alpha_freestream_local_deg=math.degrees(math.atan2(dot(freestream,n),dot(freestream,c))),
                     induced_HV_alpha_change_deg=math.degrees(math.atan2(dot(v,n),dot(v,c))-math.atan2(dot(freestream,n),dot(freestream,c))),
                     da_eff_deg=math.degrees(strip['da_eff']),projected_section_twist_deg=math.degrees(projected_twist(q)),
                     equivalent_linear_cl_angle_deg=math.degrees(cl/6.1185),CP_normal_velocity_inferred_m_s=T,
                     leakage_velocity_m_s=leakage,lift_N=dot(lift,[-wind[2],0.,wind[0]]),normal_lift_N=dot(lift,n),
                     profile_N=norm(profile),quarter_torque_current_s_Nm=dot(quarter,s),section_pitch_torque_current_s_Nm=dot(section,s),
                     torque_using_HV_arm_Nm=dot(cross(sub(hv,rm),lift),s),
                     physical_arm_m=-.0191,quarter_torque_per_current_m_N=dot(quarter,s)/ds)
            records.append(dict(row=row,rm=rm,force=force,moment=moment,lift=lift,profile=profile,quarter=quarter,section=section))
            strip_rows.append(row)
        # Independent force transfer plus exact transpose of the SO(3) angular
        # sampling map, with zero endpoint offsets verified by the geometry.
        external=[[sumv([nodal[k][i][part] for k in GROUPS]) for part in (0,1)] for i in range(nn)]
        audit.near(name+'.force sum',sumv([x['force'] for x in records]),r['force'],'global_force')
        audit.near(name+'.moment sum',sumv([add(cross(x['rm'],x['force']),x['moment']) for x in records]),r['moment'],'global_moment')
        audit.near(name+'.transferred force',sumv([x[0] for x in external]),r['applied_force'],'global_force')
        audit.near(name+'.transferred moment',sumv([add(cross(nodes[i]['position'],v[0]),v[1]) for i,v in enumerate(external)]),r['applied_moment'],'global_moment')
        balance=[[x[0][:],x[1][:]] for x in external]
        for j,e in enumerate(elements):
            N,M=e['force'],e['moment']; dr=sub(nodes[j+1]['position'],nodes[j]['position']); couple=mul(cross(dr,N),.5)
            balance[j][0]=add(balance[j][0],N);balance[j+1][0]=sub(balance[j+1][0],N)
            balance[j][1]=add(balance[j][1],add(M,couple));balance[j+1][1]=add(balance[j+1][1],sub(couple,M))
        for reaction in r['reactions']:
            audit.check(name+'.root clamp',reaction['node']==60 and reaction['kind']=='ground' and reaction['type']==0)
            for part,key in enumerate(('force','moment')): balance[60][part]=add(balance[60][part],reaction[key])
        audit.near(name+'.all nodal force balances',[x[0] for x in balance],[ZERO]*nn,'nodal_force_balance',atol=2e-8,rtol=0)
        audit.near(name+'.all nodal moment balances',[x[1] for x in balance],[ZERO]*nn,'nodal_moment_balance',atol=2e-8,rtol=0)
        section_records=[]
        for j,e in enumerate(elements):
            if e['t'] <= 0: continue
            qa,qb=nodes[j]['rotation'],nodes[j+1]['rotation']; q=arc(qa,qb,.5); qt=trans(q); ds=e['length']; midpoint=e['position']
            st=sample_constant_sections(stiffness,e['t']);B=inv3([[st['EIcc'],st['EIcs'],st['EIcn']],[st['EIcs'],st['GJ'],st['EIsn']],[st['EIcn'],st['EIsn'],st['EInn']]])
            h=[[0.,st['Nta'],0.],[-st['Nea'],0.,st['Cea']],[0.,-st['Cta'],0.]]
            factors=observation_factors(qa,qb,ds); Ftotal=ZERO[:];Mtotal=ZERO[:]; contributions={}
            for key in GROUPS:
                F=sumv([nodal[key][i][0] for i in range(j+1,nn)])
                M=sumv([add(cross(sub(nodes[i]['position'],midpoint),nodal[key][i][0]),nodal[key][i][1]) for i in range(j+1,nn)])
                Ftotal=add(Ftotal,F);Mtotal=add(Mtotal,M);f_local=mv(qt,F);m_local=mv(qt,M)
                curvature=mv(B,add(m_local,mv(h,f_local)))
                contributions[key]=dict(torque_s=dot(M,qt[1]),curvature_s=curvature[1],
                    projected_twist_deg=math.degrees(factors[0]*curvature[1]+factors[1]*curvature[2]))
            audit.near(name+f'.cut{j}.F',Ftotal,e['force'],'internal_cut_force',atol=2e-8)
            audit.near(name+f'.cut{j}.M',Mtotal,e['moment'],'internal_cut_moment',atol=2e-8)
            localF=mv(qt,e['force']);localM=mv(qt,e['moment']); translated=add(localM,mv(h,localF));curvature=mv(B,translated)
            audit.near(name+f'.section{j}.localF',localF,e['force_local'],'constitutive_outputs')
            audit.near(name+f'.section{j}.localM',localM,e['moment_local'],'constitutive_outputs')
            audit.near(name+f'.section{j}.translatedM',translated,e['moment_axes'],'constitutive_outputs')
            audit.near(name+f'.section{j}.curvature',curvature,e['curvature_change'],'constitutive_outputs')
            geometry_curvature=mul(log(mm(trans(qa),qb)),1/ds)
            audit.near(name+f'.section{j}.curvature geometry',curvature,geometry_curvature,'geometric_curvature',atol=2e-8)
            exact=math.degrees(projected_twist(qb)-projected_twist(qa))
            predicted=math.degrees(factors[0]*curvature[1]+factors[1]*curvature[2])
            audit.near(name+f'.section{j}.projected increment',predicted,exact,'projected_twist',atol=2e-8)
            row=dict(case=name,alpha_deg=alpha,speed_m_s=speed,index=j,t=e['t'],span_fraction=e['t']/L,original_ds_m=ds,
                     torque_s_Nm=translated[1],curvature_s_rad_m=curvature[1],
                     kappa_s_from_Ms_rad_m=B[1][1]*translated[1],kappa_s_from_Mc_rad_m=B[1][0]*translated[0],kappa_s_from_Mn_rad_m=B[1][2]*translated[2],
                     integral_kappa_s_deg=math.degrees(curvature[1]*ds),projected_increment_deg=exact,
                     projected_from_kappa_s_deg=math.degrees(factors[0]*curvature[1]),projected_from_kappa_n_deg=math.degrees(factors[1]*curvature[2]))
            for key,v in contributions.items():
                for subkey,value in v.items(): row[key+'_'+subkey]=value
            section_rows.append(row);section_records.append(row)
        positive=[v for v in records if v['row']['t']>0]; half_force=sumv([v['force'] for v in positive])
        half_moment=sumv([add(cross(v['rm'],v['force']),v['moment']) for v in positive]); tip=nodes[-1]
        twist=math.degrees(projected_twist(tip['rotation']));audit.near(name+'.tip output',twist,raw['observable']['projected_twist_deg'],'projected_twist')
        audit.near(name+'.integrated projected twist',sum(v['projected_increment_deg'] for v in section_records),twist,'projected_twist')
        decomposed={key:sum(v[key+'_projected_twist_deg'] for v in section_records) for key in GROUPS}
        audit.near(name+'.full load to twist attribution',sum(decomposed.values()),twist,'load_to_twist',atol=2e-7)
        tags=[v for v in scope['coordinate_tags'] if v['alpha_deg']==alpha and v['speed_m_s']==speed]
        assert len(tags)==1
        def bounds(key): return [min(v['row'][key] for v in positive),max(v['row'][key] for v in positive)]
        bands=[]
        for lo,hi in ((0.,.25),(.25,.5),(.5,.75),(.75,1.000001)):
            pp=[v for v in positive if lo<=v['row']['span_fraction']<hi];ss=[v for v in section_records if lo<=v['span_fraction']<hi]
            bands.append(dict(span_fraction=[lo,min(hi,1.)],strips=len(pp),
                lift_N=sum(v['row']['lift_N'] for v in pp),quarter_torque_current_s_Nm=sum(v['row']['quarter_torque_current_s_Nm'] for v in pp),
                projected_twist_increment_deg=sum(v['projected_increment_deg'] for v in ss)))
        summaries.append(dict(case=name,specification=spec,source_qualification=tags[0],raw=record,tip_projected_twist_deg=twist,
            half_force_N=half_force,half_moment_about_root_Nm=half_moment,
            direct_quarter_chord_torque_current_s_sum_Nm=sum(v['row']['quarter_torque_current_s_Nm'] for v in positive),
            direct_section_pitch_torque_sum_Nm=sum(v['row']['section_pitch_torque_current_s_Nm'] for v in positive),
            half_profile_force_magnitude_sum_N=sum(v['row']['profile_N'] for v in positive),
            cl_range=bounds('cl'),alpha_HV_deg_range=bounds('alpha_HV_deg'),alpha_freestream_local_deg_range=bounds('alpha_freestream_local_deg'),
            da_eff_deg_range=bounds('da_eff_deg'),inferred_CP_normal_velocity_m_s_range=bounds('CP_normal_velocity_inferred_m_s'),
            stalled_strips=sum(v['row']['stalled'] for v in positive),
            integrated_kappa_s_deg=sum(v['integral_kappa_s_deg'] for v in section_records),
            integrated_kappa_s_components_deg={key:sum(math.degrees(v['original_ds_m']*v['kappa_s_from_'+key+'_rad_m']) for v in section_records) for key in ('Ms','Mc','Mn')},
            projected_twist_from_kappa_s_deg=sum(v['projected_from_kappa_s_deg'] for v in section_records),
            projected_twist_from_kappa_n_deg=sum(v['projected_from_kappa_n_deg'] for v in section_records),
            frozen_geometry_load_to_projected_twist_deg=decomposed,span_bands=bands))
    for p in pins: audit.check('unchanged '+p['path'],pin(p['path'])==p)
    report=dict(schema='openswing-isae-ae1-saved-load-audit-v1',status='PASS' if not audit.failures else 'FAIL',
        activity=dict(new_aircraft_solves=0,aerodynamic_evaluations=0,residual_evaluations=0,production_imports=0,saved_states=len(summaries)),
        checks=dict(total=audit.count,passed=audit.count-len(audit.failures),failures=audit.failures,max_absolute_error_by_group=audit.maxima),
        formulas=dict(primary_source='https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf',
            aerodynamic='Steady equations 67,69,70,72-73,155-157,202-204; cached .reference/asw_theory.txt, printed pp16-17,31-32,40-41.',
            load_arm='Physical quarter-chord arm = (0.25-Xax)*chord*c = -0.0191*c. The HV velocity location uses the projected wind direction and is not the physical force arm.',
            transfer='F_a=(1-f)F, F_b=fF; M_a=W_a^T M, M_b=W_b^T M with W_b=R_a J(f*k) f J(k)^(-1) R_a^T and W_a=I-W_b.',
            constitutive='Inverse symmetric 3x3 bending/torsion stiffness applied to M+hF; literal constant material sections, no spline approximation.',
            observation='Exact saved arc integral d atan2(-c_z,c_x)/ds = g_s*kappa_s + g_n*kappa_n; 8-point scalar quadrature checked against endpoint angle.'),
        scope=['Independent stdlib reconstruction using saved local HV velocities and circulation; aerodynamic influence fields are not independently recomputed.',
               'CP normal tangency is inferred from stored local residual plus documented leakage, not independently validated from a CP velocity field.',
               'Load-to-twist decomposition holds the converged geometry and linear section compliance fixed. It is an algebraic attribution, not a counterfactual re-solve or sensitivity.',
               'The ASWING reference axis is the physical elastic axis for this model because Cea=Nea=0. Nta and Cta affect the bending/axial translation and are retained.',
               'Section Cm, Cdf and Cdp are literal zero; smooth below-limit stall leakage and its profile force remain included.',
               'Source dynamic qualifications and unresolved processed-displacement axis are inherited; this audit does not establish experimental agreement or stability.'],
        cases=summaries,input_pins=pins)
    write_csv(args.output/'strips.csv',strip_rows);write_csv(args.output/'sections.csv',section_rows)
    report['outputs']=[pin(args.output/'strips.csv'),pin(args.output/'sections.csv')]
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status=report['status'],checks=report['checks'],cases=summaries),indent=2))
    if audit.failures: raise SystemExit(1)


if __name__ == '__main__': main()
