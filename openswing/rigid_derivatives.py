"""Analytic steady control and flight-state responses at rigid geometry.

One circulation Jacobian factorization supplies all flap columns. Output
partials differentiate the distributed aerodynamic wrench before summation;
the stability axes, dynamic pressure and reference lengths remain fixed.
Both file-reference and body-origin moments are reported explicitly.
This is a rigid response, not a coupled structural or free-frame derivative.
"""
from types import SimpleNamespace
import warnings
import numpy as np
from scipy.linalg import lu_factor, lu_solve, LinAlgWarning
from .aero import _validate, AnalysisError, evaluate_aerodynamics
from .geometry import model_meshes
from .structured_static import IterationFields
from .circulation_tangent import FlowDerivative, surface_derivatives, body_derivatives, cross
from .control_tangent import ControlFlow
from .derivatives import stability_rotation
from .volume import body_quadrature


def distributed_wrench_columns(model, data, flow):
    """Differentiate every lifting/body/shoulder distributed load and arm."""
    force, moment, residual = surface_derivatives(data, flow, distributed_only=True)
    reference = model.reference[1]
    moment = moment+cross(data['p']['rm']-reference, force)
    total_force, total_moment = force.sum(axis=0), moment.sum(axis=0)
    for mesh, velocity in data['bodies']:
        _, df = body_derivatives(mesh, velocity, flow, data['rho'])
        positions = body_quadrature(mesh)[1]
        total_force += df.sum(axis=(0, 1))
        total_moment += cross(positions-reference, df).sum(axis=(0, 1))
    for shoulder in data['shoulders']:
        position, span, velocity = [np.asarray(shoulder[key]) for key in
                                   ('position', 'tangent', 'incident_velocity')]
        dv = flow.velocity(('shoulder', shoulder['beam'], shoulder['t']), position[None, :])[0]
        along, dalong = velocity@span, span@dv
        normal = velocity-along*span
        df = data['rho']*shoulder['area_jump']*((dv-span[:, None]*dalong)*along+normal[:, None]*dalong)
        total_force += df
        total_moment += cross(position-reference, df)
    return np.vstack((total_force, total_moment)), residual


def rigid_control_derivatives(model, condition, panels=48, *, controls=None,
                              circulation=None, circulation_method='auto', _audit=None):
    """Return exact implicit control derivatives for an engine-free rigid case.

    An optional supplied physical circulation is checked against the complete
    base residual; otherwise the normal steady circulation solve runs once.
    Body and point-object induced flows remain in the circulation equations.
    Coefficients follow steady eqs. 220–229: distributed beam/shoulder loads,
    excluding point-object, engine and apparent-mass loads. No perturbed flow
    solves or finite-difference columns are used in this analytic path.
    """
    return _rigid_derivatives(model, condition, panels, controls=controls,
        circulation=circulation, circulation_method=circulation_method, _audit=_audit)


def rigid_state_derivatives(model, condition, panels=48, *, parameters=None,
                            circulation=None, circulation_method='auto', _audit=None):
    """Analytic standard stability derivatives, steady eqs. 226–229.

    All six state columns share one circulation tangent factorization. Body
    wrenches are differentiated before applying the BASE stability rotation,
    dynamic pressure and reference lengths. u is fractional speed, alpha/beta
    are radians and p/q/r are normalized rates in BASE stability axes.
    Current influence dependence on wind and PG is included; K/F instead
    retains its explicitly selected zero-angle influence geometry.
    """
    from .state_tangent import STATE_PARAMETERS
    parameters = list(STATE_PARAMETERS) if parameters is None else parameters
    return _rigid_derivatives(model, condition, panels, parameters=parameters,
        circulation=circulation, circulation_method=circulation_method, _audit=_audit)


def _rigid_derivatives(model, condition, panels, *, controls=None, parameters=None,
                       circulation=None, circulation_method='auto', _audit=None):
    _validate(model, condition)
    from .aero import _reference_area
    _reference_area(model, required=True)
    if model.records.get('engine', []):
        raise AnalysisError('Analytic rigid derivatives do not yet include engine-inflow and jet derivatives.')
    if parameters is None:
        controls = list(model.controls) if controls is None else list(controls)
    meshes = model_meshes(model, panels)
    fields = IterationFields(); fields.capture_circulation = True
    base = evaluate_aerodynamics(model, condition, meshes, circulation=circulation,
        circulation_method=circulation_method, _iteration_fields=fields)
    data = fields.circulation_aero
    residual = np.asarray(base['circulation_residual'])
    base_residual = float(np.max(abs(residual), initial=0.))
    if not np.isfinite(base_residual) or base_residual > 1e-8:
        raise AnalysisError('Analytic control derivatives require converged base circulation.')
    if not len(data['gamma']):
        raise AnalysisError('Analytic control derivatives require lifting circulation unknowns.')
    if parameters is None:
        direct_flow = ControlFlow(model, data, controls)
    else:
        from .state_tangent import StateFlow
        if base['ground_plane'].get('wall_roots'):
            raise AnalysisError('Standard state derivatives at a wall root require constrained admissible flight-state directions.')
        direct_flow = StateFlow(model, meshes, fields, parameters)
    p = data['p']; span = p['s']; v = data['velocity']
    speed = np.linalg.norm(v-np.sum(v*span, axis=1)[:, None]*span, axis=1)
    if np.any(speed <= 100*condition.speed*1e-12):
        raise AnalysisError('Control derivative is too close to the section speed floor.')
    if hasattr(direct_flow, 'cdp_partial') and np.any((p['cdp'] <= 0) & np.any(direct_flow.cdp_partial != 0, axis=1)):
        raise AnalysisError('Control derivative is on the nonnegative profile-drag boundary.')
    basis = data['basis']
    # FlowDerivative accepts physical coefficient columns through this scale.
    context = SimpleNamespace(gamma_scale=1., ng=basis.size, size=basis.size)
    gamma_flow = FlowDerivative(context, fields, data)
    wrench_gamma, jac = distributed_wrench_columns(model, data, gamma_flow)
    wrench_direct, partial = distributed_wrench_columns(model, data, direct_flow)
    norms = np.maximum(np.linalg.norm(jac, axis=0), 1e-30)
    scaled = jac/norms
    singular = np.linalg.svd(scaled, compute_uv=False)
    rcond = float(singular[-1]/singular[0]) if singular[0] else 0.
    if not np.isfinite(rcond) or rcond < 1e-10:
        raise AnalysisError('Rigid circulation tangent is singular or too ill-conditioned.')
    with warnings.catch_warnings():
        warnings.simplefilter('error', LinAlgWarning)
        factor = lu_factor(scaled)
        response = lu_solve(factor, -partial)/norms[:, None]
    linear_residual = np.max(abs(jac@response+partial), axis=0)/np.maximum(
        1., np.max(abs(partial), axis=0))
    if not np.all(np.isfinite(response)) or np.max(linear_residual) > 1e-8:
        raise AnalysisError('Analytic control tangent failed its full linear residual check.')
    wrench = wrench_direct+wrench_gamma@response
    rotation = stability_rotation(condition.alpha)
    qs = base['atmosphere']['dynamic_pressure']*model.reference[0, 0]
    lever = model.reference[0, [2, 1, 2]]
    transform = np.zeros((6, 6))
    transform[:3, :3] = np.diag([1., 1., -1.])@rotation/qs
    transform[3:, 3:] = rotation/(qs*lever[:, None])
    coefficients = transform@wrench
    # The rigid moment reference is fixed in body axes. Translate each force
    # column before the stability-axis rotation and unequal c/b normalizations.
    # Eqs. 221/223 use the origin; retain the existing reference-point outputs.
    origin_wrench = wrench.copy()
    origin_wrench[3:] += np.cross(model.reference[1], wrench[:3].T).T
    origin_coefficients = transform@origin_wrench
    if not np.all(np.isfinite(coefficients)) or not np.all(np.isfinite(origin_coefficients)):
        raise AnalysisError('Nonfinite analytic control coefficient derivative.')
    if _audit is not None:
        _audit(dict(base=base, jacobian=jac.copy(), input_partials=partial.copy(),
                    coefficient_response=response.copy(), wrench_gamma=wrench_gamma.copy(),
                    wrench_direct=wrench_direct.copy(), coefficient_transform=transform.copy(),
                    fields=fields))
    result = dict(method='analytic implicit rigid control derivatives' if parameters is None else
                  'analytic implicit rigid state derivatives', axes='stability',
        coefficient_rows=['CX', 'CY', 'CL', 'Cl', 'Cm', 'Cn'],
        coefficients=coefficients.tolist(), distributed_aero_wrench=wrench.tolist(),
        coefficients_origin=origin_coefficients.tolist(),
        distributed_aero_wrench_origin=origin_wrench.tolist(),
        circulation=(basis.sample@response).tolist(),
        circulation_coefficients=response.tolist(),
        base_coefficients=(transform@np.r_[base['distributed_aero_force'], base['distributed_aero_moment']]).tolist(),
        base_coefficients_origin=(transform@np.r_[base['distributed_aero_force'],
            base['distributed_aero_moment_origin']]).tolist(),
        moment_definitions=dict(reference=model.reference[1].tolist(),
            wrench_axes='body', coefficient_axes='base stability',
            reference_outputs=['distributed_aero_wrench', 'coefficients', 'base_coefficients'],
            origin_outputs=['distributed_aero_wrench_origin', 'coefficients_origin', 'base_coefficients_origin'],
            translation='dM_origin = dM_reference + reference cross dF; reference is fixed in body axes',
            scope=base['moment_definitions']['distributed_scope']),
        base_residual=base_residual, linear_residuals=linear_residual.tolist(),
        reciprocal_condition=rcond, physical_evaluations=1, factorizations=1,
        panels=len(data['gamma']), circulation_basis=basis.report(),
        limitations=[
            'Prescribed rigid geometry; no structural or free-frame acceleration response.',
            'Fixed base stability axes, dynamic pressure and reference lengths.',
            'Distributed coefficients exclude direct point-object, engine and apparent-mass loads.',
            'No engine records are accepted by this fully analytic path.',
            'A converged discrete tangent does not establish historical ASWING settings or mesh parity.'])
    if parameters is None:
        result.update(controls=controls, units='per file flap setting')
    else:
        from .state_tangent import STATE_PARAMETERS, STATE_UNITS
        result.update(parameters=list(parameters),
                      units=[STATE_UNITS[STATE_PARAMETERS.index(name)] for name in parameters],
                      influence_derivative='zero-angle K/F geometry with live PG Mach' if condition.freeze_influences
                      else 'complete current-wind source, receiver, wake, volume and PG derivatives')
        result['limitations'].extend([
            'This differentiates the current steady equations; historical isolated-wing Newton influence lagging at derivative export is unverified.',
            'General spatial expression-gust gradients and wall-root flight-state constraints are not implemented in this analytic path.'])
    return result
