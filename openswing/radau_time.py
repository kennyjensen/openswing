"""Three-stage Radau IIA collocation of the common continuous time residual.

Fifth order for regular ODEs; constrained variables can have lower order.
Stages use the common continuous equations, with Earth position/velocity-defect
coordinates for prescribed position histories. No explicit mass inversion,
constraint projection or added damping modifies the physical system.
"""
import numpy as np

_s=np.sqrt(6.)
NODES=np.array([(4-_s)/10,(4+_s)/10,1.])
TABLEAU=np.array([[(88-7*_s)/360,(296-169*_s)/1800,(-2+3*_s)/225],
    [(296+169*_s)/1800,(88+7*_s)/360,(-2-3*_s)/225],
    [(16-_s)/36,(16+_s)/36,1/9]])
INVERSE=np.linalg.inv(TABLEAU)


def collocate(residual,initial,rate_guess,time,step,tolerance,*,factorization=None,end_time=None,check_rank=False,accepted_root_diagnostic=None,capture=False,progress=None,stage_rate_columns=None,stage_chart=None):
    """Solve all collocation stages together; the final stage is the endpoint."""
    from .time_integration import newton
    initial=np.asarray(initial);n=len(initial)
    times=time+NODES*step
    if end_time is not None:times[-1]=end_time
    def function(flat,_mechanical_data=None):
        increments=flat.reshape(3,n);rates=INVERSE@increments/step
        if _mechanical_data is not None:
            return np.concatenate([residual.capture_mechanical(initial+z,d,t,data)
                for z,d,t,data in zip(increments,rates,times,_mechanical_data)])
        return np.concatenate([residual(initial+z,d,t) for z,d,t in zip(increments,rates,times)])
    function.progress=progress
    function.accepted_root_diagnostic=accepted_root_diagnostic
    if stage_rate_columns is not None:
        from .radau_tangent import attach
        attach(function,residual,initial,times,step,INVERSE,stage_rate_columns,progress)
    if stage_chart is not None:
        from .structured_radau import attach
        attach(function,stage_chart,residual,initial,times,step,INVERSE,progress)
        from .nonlinear_initial import InitialSystem
        if type(stage_chart) is InitialSystem and hasattr(residual, 'capture_mechanical'):
            from .time_tangent import attach_mechanical_columns
            attach_mechanical_columns(stage_chart.system, function,
                lambda values, data: function(values, _mechanical_data=data), stages=3)
    guess=(step*NODES[:,None]*rate_guess).ravel()
    values,factorization,iterations,builds=newton(function,guess,tolerance,factorization,check_rank=check_rank)
    increments=values.reshape(3,n);rates=INVERSE@increments/step
    errors=function(values).reshape(3,n)
    result=(initial+increments[-1],rates[-1],factorization,iterations,builds,float(np.max(abs(errors))))
    if capture:
        result+=(dict(initial=initial.copy().tolist(),increments=increments.copy().tolist(),
            times=times.copy().tolist(),step=float(step),tolerance=float(tolerance)),)
    return result


def step(system,previous,time,frame,side,tolerance,*,factorization=None,capture=False):
    from .nonlinear_initial import InitialSystem
    if system.position_lift is None:
        chart=InitialSystem(system,previous,frame,apply_forcing=True)
    else:
        from .position_history_radau import PositionHistoryRadauChart
        chart=PositionHistoryRadauChart(system,previous,frame)
    h=time-previous.time;zero=np.zeros(chart.size)
    # Higher-index reaction variables amplify geometric residuals by inverse
    # powers of the step. Tighten the nonlinear solve, with an explicit floor.
    stage_tolerance=min(tolerance,max(1e-12,tolerance*min(1.,h*chart.W)**2))
    def residual(z,d,t,_mechanical_data=None):
        options={} if _mechanical_data is None else dict(_mechanical_data=_mechanical_data)
        return chart.residual(z,d,t,side=side if t==time else 'right',**options)
    if type(chart) is InitialSystem:
        residual.capture_mechanical=lambda z,d,t,data:residual(z,d,t,_mechanical_data=data)
    diagnostic=None
    if system.feedback is not None:
        rows=[stage*chart.size+system.feedback_start+i for stage in range(3) for i in range(system.feedback.count)]
        diagnostic=system.feedback.root_diagnostic(rows,stage_tolerance)
    from .radau_tangent import supported_rate_columns
    solved=collocate(residual,zero,chart.rate_guess(zero),previous.time,h,
        stage_tolerance,factorization=factorization,end_time=time,check_rank=system.requires_unique_time_solution,
        accepted_root_diagnostic=diagnostic,capture=capture,progress=getattr(system,'progress',None),
        stage_rate_columns=supported_rate_columns(chart),stage_chart=chart)
    z,rate,factorization,iterations,builds,error=solved[:6]
    _,state,options=chart.residual(z,rate,time,side=side,detail=True)
    result=(state,options,factorization,iterations,builds,error,stage_tolerance)
    if capture:
        stage_data=solved[6];stage_data['sides']=['right','right',side]
        result+=(stage_data,)
    return result
