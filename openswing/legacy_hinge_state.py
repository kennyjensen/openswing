"""Checked legacy static winding recovery from original setup and source law.

No equilibrium solve or target-setting substitution occurs here. The original
physical state must already satisfy its original mechanical/controller equations.
"""
from copy import deepcopy
import hashlib
import json
import numpy as np
from .aero import AnalysisError


def recover(target,saved):
    if getattr(target,'source_dynamic',False):
        raise AnalysisError('Source dynamic hinge states require version-2 packets with owned continuous angles; legacy winding recovery is unavailable.')
    from .equilibrium_state import (identity,matching_identity,restore_physical_fields,
                                    checked_hinge_charts,restore_feedback,recipe_from_identity)
    from .network import StaticNetwork
    from .inertia import Motion,vector
    from .ground import body_to_earth
    from .time_state import read_condition
    from .time_integration import TimeState
    from .feedback import FeedbackSystem
    if (saved.get('format')!='openswing-equilibrium' or type(saved.get('version')) is not int
            or saved['version']!=1 or 'hinge_charts' in saved):
        raise AnalysisError('Legacy hinge recovery requires an unambiguous version-1 packet without hinge_charts.')
    if not matching_identity(saved.get('identity'),identity(target)):
        raise AnalysisError('Saved equilibrium aircraft, mesh or constraint layout does not match the current configuration.')
    launch=saved.get('launch')
    required={'version','panels','condition','motion','gravity','loads','strut_mode','controller','frame','released_constraints'}
    if (not isinstance(launch,dict) or not required<=launch.keys()
            or type(launch['version']) is not int or launch['version']!=1):
        raise AnalysisError('Legacy hinge recovery needs the complete original saved launch/setup; no winding is inferred.')
    if launch['released_constraints']!=[]:
        raise AnalysisError('Legacy hinge recovery does not reconstruct original trim/custom constraints; original evidence is insufficient for this importer.')
    if launch.get('quiescent_density') is not None:
        raise AnalysisError('Legacy hinge recovery is not implemented for quiescent modal packets.')
    try:
        launch=deepcopy(launch)
        condition=read_condition(launch['condition']);motion=Motion(**launch['motion'])
        if not isinstance(launch['loads'],list):raise ValueError('original loads must be a list')
        pose=launch['frame']
        position,attitude,velocity=(vector(pose[key],'Original '+key) for key in ('position','attitude','velocity'))
        magnitude=pose['gravity_magnitude']
        if magnitude is not None and (isinstance(magnitude,bool) or not isinstance(magnitude,(int,float))
                                     or not np.isfinite(magnitude) or magnitude<0):
            raise ValueError('invalid original gravity magnitude')
        original=StaticNetwork(target.model,launch['panels'],condition,launch['gravity'],launch['loads'],
            motion if condition is None else None,(),launch['strut_mode'],
            mesh_recipe=recipe_from_identity(saved.get('identity')))
        if condition is not None and any(not np.allclose(getattr(original.motion,key),getattr(motion,key),rtol=1e-12,atol=1e-12)
                                         for key in ('rates','acceleration','angular_acceleration')):
            raise AnalysisError('Original launch condition and stored motion disagree.')
        if not matching_identity(saved['identity'],identity(original)):
            raise AnalysisError('Original saved launch/setup does not reproduce the saved aircraft and mesh.')
        # No chart is selected by decoding physical resultants/rotations.
        x=restore_physical_fields(original,saved)
        options={}
        if condition is None and launch['gravity'] is None:
            options['gravity_override']=body_to_earth(attitude).T@np.array([0.,0.,-(target.model.constants[0] if magnitude is None else magnitude)])
        feedback=None
        if launch['controller'] is None:
            if saved.get('feedback') is not None:raise AnalysisError('Legacy controller state lacks its original controller definition.')
        else:
            if condition is None:raise AnalysisError('Legacy controller recovery needs its original aerodynamic condition.')
            feedback=FeedbackSystem(original,launch['controller'])
            r,q,*_,gamma=original.unpack(x);zero=np.zeros_like(r)
            state=TimeState(condition.time,x,r,q,zero,zero,
                -condition.speed*condition.vectors()[0]-np.cross(original.motion.rates,target.model.reference[3]),
                original.motion.rates,np.asarray(condition.position_earth),body_to_earth(condition.attitude),gamma)
            _,data=original.residual(x,detail=True,**options)
            feedback.initialize(state,data)
            restore_feedback(original,feedback,state,saved,preserve_commands=True)
            options['condition_override']=feedback.apply(state,condition)
        _,data=original.residual(x,detail=True,**options)
        trace={row['joint']:row for row in data['hinges']}
        rows=[dict(joint=c['law'].index,angle_rad=float(c['law'].angle(trace[c['law'].index]['structural_moment'])))
              for c in original.constraints if c['type']==3]
        upgraded=deepcopy(saved);upgraded.update(version=2,hinge_charts=rows)
        centers=checked_hinge_charts(original,upgraded,x)
        for c,center in zip((c for c in original.constraints if c['type']==3),centers):c['angle_chart']=center
        residual,data=original.residual(x,detail=True,**options)
        if feedback is not None:
            residual=np.r_[residual,feedback.evaluate(state,data,np.zeros(feedback.size))[0]]
        error=float(np.max(abs(residual)))
        if not np.isfinite(error) or error>1e-8:
            raise AnalysisError(f'Legacy original equilibrium fails its complete mechanical/controller residual ({error:.3g}); winding cannot be certified.')
        upgraded['legacy_hinge_recovery']=dict(method='original-setup-source-law-and-full-residual-v1',
            original_residual=error,tolerance=1e-8,controller_verified=feedback is not None,
            structural_moments=[dict(joint=row['joint'],structural_moment=row['structural_moment']) for row in data['hinges']],
            original_launch_sha256=hashlib.sha256(json.dumps(saved['launch'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
            target_settings_used=False,nonlinear_equilibrium_solved=False)
        return upgraded
    except AnalysisError:
        raise
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        raise AnalysisError(f'Invalid original setup for legacy hinge recovery: {exc}') from exc
