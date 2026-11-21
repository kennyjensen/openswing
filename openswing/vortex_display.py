"""JSON display of the actual influence horseshoes (no circulation solve)."""
import numpy as np


def vortex_geometry(geometry, direction, *, frozen, preview=False):
    return dict(axes='body', frozen=bool(frozen), preview=bool(preview),
                geometry='jig' if frozen or preview else 'current',
                bound_segments=np.stack([geometry['a'], geometry['b']], axis=1).tolist(),
                control_points=geometry['cp'].tolist(),
                wake_direction=np.asarray(direction).tolist())


def preview(meshes, *, alpha=0., beta=0., freeze_influences=True):
    from .aero import FlightCondition
    from .frozen_influence import lifting_geometry
    if type(freeze_influences) is not bool or not np.all(np.isfinite([alpha, beta])):
        raise ValueError('Vortex preview needs finite wind angles and a boolean freeze setting.')
    direction = np.array([1., 0., 0.]) if freeze_influences else FlightCondition(alpha=alpha, beta=beta).vectors()[0]
    return vortex_geometry(lifting_geometry(meshes, direction), direction,
                           frozen=freeze_influences, preview=True)
