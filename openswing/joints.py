"""ASWING Jangle laws: jig-body axis and angle(structural moment).

Angles in the file and reports are degrees; rotations in the solver are radians.
Natural cubic endpoint conditions are provisional (see docs/NUMERICS.md).
"""
import numpy as np
from .asw import AswError, Distribution


class HingeLaw:
    def __init__(self, record):
        header, curve = record["header"], record["curve"]
        self.index = int(header[0])
        axis = np.asarray(header[1:], dtype=float)
        norm = np.linalg.norm(axis)
        if norm == 0 or not np.isfinite(norm):
            raise AswError(f"Jangle {self.index}: hinge axis must be nonzero and finite.")
        self.axis = axis/norm
        self.curve = np.array(curve, dtype=float, copy=True)
        # Legacy FFWT inputs scale the two moment samples by a negative
        # factor. Reverse paired samples only in the compiled law: this keeps
        # the exact affine function, its sign and the original source records.
        if len(self.curve) == 2 and self.curve[1, 0] < self.curve[0, 0]:
            self.curve = self.curve[::-1].copy()
        delta = np.diff(self.curve[:, 0])
        if np.any(delta < 0):
            raise AswError(f"Jangle {self.index}: moments must increase, except for doubled stations.")
        if np.any(np.diff(self.curve[:, 1])[delta == 0] != 0):
            raise AswError(f"Jangle {self.index}: doubled moments must have equal angles for a continuous slope break; discontinuous angle jumps are not supported.")
        self.spline = Distribution(f"Jangle {self.index}", self.curve[:, 0], self.curve[:, 1], 0)
        self.zero_angle = self.angle(0.)

    def angle(self, moment, factor=1.):
        # Continue a prescribed unloaded angle, retaining the complete spring
        # tangent at zero load (a sprung joint must not become a mechanism).
        value = np.deg2rad(self.spline.evaluate(moment))
        return value if factor == 1 else value-(1-factor)*self.zero_angle

    def report(self, moment, axis):
        return dict(joint=self.index, axis_jig=self.axis.tolist(), axis=np.asarray(axis).tolist(),
                    structural_moment=float(moment), angle_deg=float(np.rad2deg(self.angle(moment))),
                    compliance_deg_per_moment=float(self.spline.evaluate(moment, derivative=1)),
                    extrapolated=bool(moment < self.curve[0, 0] or moment > self.curve[-1, 0]))


def hinge_laws(records):
    joints = records.get("joint", [])
    required = {i for i, row in enumerate(joints, 1) if int(row[4]) == 3}
    laws = {}
    for record in records.get("jangle", []):
        law = HingeLaw(record)
        if law.index not in required:
            raise AswError(f"Jangle {law.index} must reference a type 3 Joint row (numbered from 1).")
        if law.index in laws:
            raise AswError(f"Joint {law.index} has more than one Jangle block.")
        laws[law.index] = law
    if missing := required-laws.keys():
        raise AswError(f"Type 3 Joint {min(missing)} requires a Jangle block.")
    return laws
