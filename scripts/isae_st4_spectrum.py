"""Compare the complete three-frequency sets in ISAE Part III Table 6.

Ordering is fixed by frequency on each side, never by a best-match search.
This checks the spectrum, not the archived bending/torsion mode identities.
"""
from math import isfinite


def compare_triplet(targets, coarse, fine, shape_mac, *, relative=.05,
                    mesh_relative=.001, minimum_mac=.99):
    if len(targets) != 3 or len(coarse) != 3 or len(fine) != 3:
        raise ValueError('A complete three-mode comparison is required.')
    if {r['label'] for r in targets} != {'fb1', 'fb2', 'ft'}:
        raise ValueError('Retain each original Table 6 frequency exactly once.')
    expected = [r['expected'] for r in targets]
    for values in (expected, coarse, fine):
        if any(x is None or not isfinite(x) or x <= 0 for x in values):
            raise ValueError('A missing or invalid mode cannot be discarded.')
        if len(set(values)) != 3:
            raise ValueError('This scope requires three distinct modes.')
    if list(coarse) != sorted(coarse) or list(fine) != sorted(fine):
        raise ValueError('Predictions and shape rows must share ascending order.')
    if len(shape_mac) != 3 or any(len(row) != 3 for row in shape_mac):
        raise ValueError('Complete coarse/fine shape comparisons are required.')
    if any(not isfinite(x) or x < 0 or x > 1+1e-12 for row in shape_mac for x in row):
        raise ValueError('Invalid shape correlation.')
    rows = []
    for i, (target, a, b) in enumerate(zip(sorted(targets, key=lambda r: r['expected']),
                                         coarse, fine, strict=True)):
        value = target['expected']
        absolute = target['original_absolute_tolerance']
        if not isfinite(absolute) or absolute < 0:
            raise ValueError('Invalid source precision.')
        gate = max(absolute, relative*abs(value))
        match = max(abs(a-value), abs(b-value)) <= gate
        change = abs(a/b-1)
        mutual = (max(range(3), key=lambda j: shape_mac[i][j]) == i and
                  max(range(3), key=lambda j: shape_mac[j][i]) == i)
        mesh_pass = (change <= mesh_relative and shape_mac[i][i] >= minimum_mac
                     and mutual)
        rows.append(dict(rank=i+1, original_label=target['label'], expected_Hz=value,
            coarse_Hz=a, fine_Hz=b, error_percent=100*abs(b/value-1),
            worst_mesh_error_percent=100*max(abs(a/value-1), abs(b/value-1)),
            mesh_change_percent=100*change, shape_MAC=shape_mac[i][i],
            frequency_pass=match, mesh_pass=mesh_pass, passed=match and mesh_pass,
            native_mode_identity_validated=False))
    return rows
