"""Stage-local numerical partials for the original Radau residual.

The caller must explicitly supply every rate-dependent column. Each stage is
evaluated at its own state, rate and time; nothing is frozen across stages.
Failure leaves the ordinary full collocation difference fallback available.
"""
import numpy as np

def stage_jacobian(residual, initial, flat, times, step, inverse, rate_columns,
                   *, difference_step=1e-6, progress=None):
    initial=np.asarray(initial,dtype=float);flat=np.asarray(flat,dtype=float)
    n=len(initial);times=np.asarray(times,dtype=float);inverse=np.asarray(inverse,dtype=float)
    columns=np.asarray(rate_columns)
    if (initial.shape!=(n,) or flat.shape!=(3*n,) or times.shape!=(3,)
            or inverse.shape!=(3,3) or columns.ndim!=1 or columns.dtype.kind not in 'iu'
            or len(np.unique(columns))!=len(columns) or np.any(columns<0) or np.any(columns>=n)
            or not np.isfinite(step) or step<=0 or not np.isfinite(difference_step) or difference_step<=0
            or not all(np.all(np.isfinite(x)) for x in (initial,flat,times,inverse))):
        raise ValueError('Invalid Radau stage derivative layout or coordinates.')
    increments=flat.reshape(3,n);rates=inverse@increments/step
    matrix=np.empty((3*n,3*n));evaluations=0
    total=3*(n+len(columns));done=0
    if progress is not None:progress('radau_stage_tangent',0,total)
    for i,(increment,rate,time) in enumerate(zip(increments,rates,times)):
        state=initial+increment
        base=np.asarray(residual(state,rate,time),dtype=float);evaluations+=1
        if base.shape!=(n,) or not np.all(np.isfinite(base)):
            raise ValueError('Invalid Radau stage residual.')
        fy=np.empty((n,n));fd=np.zeros((n,n))
        for column in range(n):
            delta=difference_step*max(1.,abs(state[column]))
            trial=state.copy();trial[column]+=delta
            fy[:,column]=(residual(trial,rate,time)-base)/delta
            evaluations+=1;done+=1
            if progress is not None:progress('radau_stage_tangent',done,total)
        for column in columns:
            delta=difference_step*max(1.,abs(rate[column]))
            trial=rate.copy();trial[column]+=delta
            fd[:,column]=(residual(state,trial,time)-base)/delta
            evaluations+=1;done+=1
            if progress is not None:progress('radau_stage_tangent',done,total)
        for j in range(3):
            matrix[i*n:(i+1)*n,j*n:(j+1)*n]=(inverse[i,j]/step)*fd
        matrix[i*n:(i+1)*n,i*n:(i+1)*n]+=fy
    if not np.all(np.isfinite(matrix)):
        raise ValueError('Nonfinite Radau stage derivative.')
    return matrix,dict(stages=3,size=n,rate_columns=len(columns),stage_residual_evaluations=evaluations)

def attach(function,residual,initial,times,step,inverse,rate_columns,progress=None):
    """Use the existing guarded Newton builder and dense residual fallback."""
    def build(flat):
        from .time_integration import lu_factor,LinAlgWarning
        import warnings
        matrix,diagnostics=stage_jacobian(residual,initial,flat,times,step,inverse,
            rate_columns,progress=progress)
        with warnings.catch_warnings():
            warnings.simplefilter('error',LinAlgWarning)
            factorization=lu_factor(matrix)
        function.stage_tangent_diagnostics=diagnostics
        return factorization
    function.factorization_builder=build

def supported_rate_columns(chart):
    """Only the audited ordinary chart opts in; broader paths keep full FD.

    InitialSystem.residual structurally reads rates only at nodal kinematics,
    circulation, local velocities/rates, and the12 frame coordinates. Its
    dynamic_indices describes those columns in this controller-free scope.
    Numerical zeros alone never authorize this exclusion.
    """
    from .nonlinear_initial import InitialSystem
    system=chart.system
    if (type(chart) is not InitialSystem or system.feedback is not None
            or system.position_lift is not None or system.network.operating.count
            or system.network.operating.custom):
        return None
    return chart.dynamic_indices
