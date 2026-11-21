"""Objective axial struts/wires between a moving pylon and a body-fixed anchor.

ASW's Strut block supplies no buckling load or compression-type flag. The
bilateral axial law and the optional tension-only wire law are therefore explicit
analysis choices. See docs/NUMERICS.md for the ambiguity in printed steady eq. 141.
"""
import numpy as np


def strut_load(row, position, *, tension_only=False, factor=1.):
    anchor = np.asarray(row[5:8], dtype=float)
    jig_length = float(np.linalg.norm(anchor-row[2:5]))
    rest_length = jig_length+factor*float(row[8])
    ea = float(row[9])
    if jig_length <= 0 or jig_length+row[8] <= 0 or ea < 0:
        raise ValueError("Strut needs distinct endpoints, positive unloaded length and nonnegative EAw.")
    delta = anchor-position
    length = float(np.linalg.norm(delta))
    if length <= 1e-12*jig_length:
        raise ValueError("Strut endpoints have collapsed; its axial direction is undefined.")
    extension = length-rest_length
    active_extension = max(0., extension) if tension_only else extension
    tension = ea*active_extension/rest_length
    force = tension*delta/length
    return dict(position=np.asarray(position), anchor=anchor, force=force,
                length=length, unloaded_length=rest_length, strain=extension/rest_length,
                tension=tension, energy=.5*ea/rest_length*active_extension**2,
                tension_only=bool(tension_only), slack=bool(tension_only and extension <= 0))
