"""Differentiate summed aerodynamic moments before cancellation of totals."""
from math import fsum
import numpy as np
from .vector_ops import cross3


def moment_difference(plus,minus,reference,*,force='force',moment='moment'):
    """Exact symmetric product difference, summed after differentiation.

    r+ cross F+ - r- cross F- equals r_mean cross delta_F plus
    delta_r cross F_mean. No large opposite-wing moments are subtracted.
    Each row retains its actual force application point and local couple.
    """
    if len(plus)!=len(minus):raise ValueError('Changed moment source layout.')
    if not plus:return np.zeros(3)
    r1,r2=[np.asarray([row['position'] for row in rows]) for rows in (plus,minus)]
    f1,f2=[np.asarray([row[force] for row in rows]) for rows in (plus,minus)]
    m1,m2=[np.asarray([row.get(moment,[0.,0.,0.]) for row in rows]) for rows in (plus,minus)]
    values=m1-m2+cross3(.5*(r1+r2)-reference,f1-f2)+cross3(r1-r2,.5*(f1+f2))
    return np.array([fsum(values[:,i]) for i in range(3)])


def aerodynamic_moments(snapshots,point_positions,reference,step):
    """Four real snapshots give the complete complex moment derivative."""
    if 'moment' not in snapshots[0]:return {}
    parts=[]
    for a,b in [(0,1),(2,3)]:
        plus,minus=snapshots[a],snapshots[b]
        strips=moment_difference(plus['strips'],minus['strips'],reference)
        apparent=moment_difference(plus['strips'],minus['strips'],reference,
            force='apparent_force',moment='apparent_moment')
        shoulders=moment_difference(plus['body_shoulders'],minus['body_shoulders'],reference)
        engine=moment_difference(plus['engines'],minus['engines'],reference)
        points=[[dict(position=p,force=f) for p,f in zip(point_positions[i],snapshots[i]['point_forces'],strict=True)] for i in (a,b)]
        point=moment_difference(*points,reference)
        distributed=strips-apparent+shoulders
        origin_strips=moment_difference(plus['strips'],minus['strips'],np.zeros(3))
        origin_shoulders=moment_difference(plus['body_shoulders'],minus['body_shoulders'],np.zeros(3))
        origin_apparent=moment_difference(plus['strips'],minus['strips'],np.zeros(3),
            force='apparent_force',moment='apparent_moment')
        parts.append(dict(moment=strips+shoulders+point+engine,
            distributed_aero_moment=distributed,apparent_moment=apparent,engine_moment=engine,
            moment_origin=origin_strips+origin_shoulders+moment_difference(*points,np.zeros(3))
                +moment_difference(plus['engines'],minus['engines'],np.zeros(3)),
            distributed_aero_moment_origin=origin_strips-origin_apparent+origin_shoulders))
    return {key:(parts[0][key]+1j*parts[1][key])/(2*step) for key in parts[0]}
