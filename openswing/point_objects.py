"""Analysis view of ASW Weight records, without changing parsed source data.

Steady Eqs.95--96 and164, and unsteady Eqs.46--47, give identically zero
loads and induced fields when mass, drag area, volume, angular momentum and
the complete inertia tensor vanish. The supporting pylon is massless and
introduces no separate degrees of freedom (ASWING input manual, Weight).
Such a record needs no analysis attachment or flow query. This is algebraic
elimination of a null object, not a claim about legacy input validation.
"""
import numpy as np


RIGID_ATTACHMENT_POLICY = 'whole-rigid-beam-endpoint-pylon-v1'
RIGID_ATTACHMENT_SCOPE = (
    'Out-of-range mechanical Weight anchors on an exactly rigid, undamped beam '
    'use its nearest endpoint and the original physical point position. '
    'This is a rigid-pylon reduction; native ASWING out-of-range input semantics '
    'are unverified. Finite time-step results still require refinement.')


def _zero_table(beam, name):
    """Certify the complete current table, including its compiled interpolant.

    All applicable defaults are rigid/zero. Sampling the mesh or accepting
    large finite stiffness would not prove rigidity between mesh nodes.
    Reject stale edited tables as well: their old spline may still be active.
    """
    d = beam.distributions.get(name)
    if d is None:
        return True
    return (d.values.ndim == 1 and d.values.shape == d.t.shape and len(d.t) > 0
            and np.all(np.isfinite(d.t)) and np.all(np.isfinite(d.values))
            and bool(np.all(d.values == 0))
            and np.array_equal(d.t, d._compiled_t)
            and np.array_equal(d.values, d._compiled_values)
            and d.interpolation == d._compiled_interpolation)


def analysis_weight_station(model, row):
    """Analysis anchor, without changing the original Weight or serialization.

    Apply exact decimal aliases first. Only a whole, exactly rigid beam with
    zero material damping admits this out-of-domain reduction. The current
    verified scope excludes point drag area and volume. An endpoint retains
    the inward section loads; moving the anchor to an interior node would not.
    Ineligible records keep their original out-of-range validation failure.
    """
    from .asw import weight_station, RIGID
    station = weight_station(model, row)
    values = np.asarray(row)
    if (values.shape != (17,) or not np.all(np.isfinite(values))
            or values[0] != int(values[0]) or values[6] != 0 or values[7] != 0):
        return station
    beam = next((b for b in model.beams if b.index == int(values[0])), None)
    if beam is None:
        return station
    lo, hi = beam.domain
    if lo <= station <= hi or not np.all(np.isfinite([lo, hi])) or lo >= hi:
        return station
    if not all(_zero_table(beam, name) for name in
               (*RIGID, 'EIcn', 'EIcs', 'EIsn', 'tdeps', 'tdgam')):
        return station
    return float(lo if station < lo else hi)


def rigid_weight_attachments(model):
    """Serializable provenance for reductions, excluding mere decimal aliases."""
    from .asw import weight_station
    result = []
    for index, row in active_weight_items(model):
        original = weight_station(model, row)
        effective = analysis_weight_station(model, row)
        if effective != original:
            result.append(dict(record=index+1, beam=int(row[0]), original_t=float(row[1]),
                effective_t=effective, position=row[2:5].tolist(),
                policy=RIGID_ATTACHMENT_POLICY, reason=RIGID_ATTACHMENT_SCOPE))
    return result


def null_weight(row):
    """Exact zeros in all twelve scaled physical fields; never a tolerance.

    Position and attachment coordinates alone carry no force or inertia.
    Nonfinite or malformed rows cannot certify nullity. The predicate is
    evaluated on current records so a subsequent physical-property edit is
    active in a newly constructed analysis.
    """
    values = np.asarray(row)
    return (values.shape == (17,) and np.all(np.isfinite(values))
            and bool(np.all(values[5:17] == 0)))


def active_weight_items(model):
    """Original zero-based record indices and row objects used by analysis."""
    return [(i, row) for i, row in enumerate(model.records.get('weight', []))
            if not null_weight(row)]


def active_weights(model):
    """Rows in analysis order; originals and source serialization stay intact."""
    return [row for _, row in active_weight_items(model)]


def check_point_data(rows, data, name):
    """Reject raw-record arrays mixed with the active point-object ordering."""
    if data is not None and len(data) != len(rows):
        raise ValueError(f'{name} must contain one entry per active Weight object.')
