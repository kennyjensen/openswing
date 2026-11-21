"""Reference geometry and beam-local frames in ASWING x-aft/y-right/z-up axes."""
from dataclasses import dataclass
import math
import numpy as np
from .asw import Beam
from .point_objects import active_weights, analysis_weight_station
from .discretization import beam_settings, normalize as normalize_discretization, requirements
from .discretization import CURRENT_MESH_RECIPE, checked_recipe, mesh_breaks
from .arc_length import material_arc


def normalize(v):
    v = np.asarray(v, dtype=float)
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    if np.any(norm < 1e-13):
        raise ValueError("Cannot normalize a zero vector; check beam geometry.")
    return v / norm


def surface_frame(beam: Beam, t, side="right"):
    s = normalize(beam.position(t, derivative=1, side=side))
    if beam.lifting:
        phi = np.arctan2(s[..., 2], s[..., 1])
        psi = -np.arcsin(np.clip(s[..., 0], -1, 1))
        c0 = np.stack([np.cos(psi), np.sin(psi) * np.cos(phi), np.sin(psi) * np.sin(phi)], axis=-1)
        n0 = np.stack([np.zeros_like(phi), -np.sin(phi), np.cos(phi)], axis=-1)
    else:
        # Fuselage beams reverse the first two Euler rotations (steady eq. 10)
        # to avoid the surface-frame pole near an x-aligned fuselage.
        phi = np.arcsin(np.clip(s[..., 2], -1, 1))
        psi = np.arctan2(-s[..., 0], s[..., 1])
        c0 = np.stack([np.cos(psi), np.sin(psi), np.zeros_like(phi)], axis=-1)
        n0 = np.stack([np.sin(psi)*np.sin(phi), -np.cos(psi)*np.sin(phi), np.cos(phi)], axis=-1)
    theta = np.deg2rad(beam.value("twist", t, side=side))[..., None]
    c = c0 * np.cos(theta) - n0 * np.sin(theta)
    n = c0 * np.sin(theta) + n0 * np.cos(theta)
    return np.stack([c, s, n], axis=-1)


@dataclass
class PanelMesh:
    beam: Beam
    t0: np.ndarray
    t1: np.ndarray
    tm: np.ndarray
    r0: np.ndarray
    r1: np.ndarray
    rm: np.ndarray
    frames: np.ndarray
    length: np.ndarray
    frame0: np.ndarray | None = None
    frame1: np.ndarray | None = None
    ts: np.ndarray | None = None  # midpoint in undeformed material arc length
    theta: np.ndarray | None = None  # material node angles, decreasing pi to zero
    mesh_recipe: str = CURRENT_MESH_RECIPE


def minimum_spaced_nodes(candidate_s, required_s, minimum, total, beam_index):
    """Coarsen generated nodes symmetrically, retaining every required station.

    Distances are undeformed material arc lengths on this logical beam. Taking
    candidates from both ends avoids a left-to-right bias on mirrored surfaces.
    A final conflicting pair is replaced by its center, not selected by side.
    """
    tolerance = min(1e-11 * total, minimum * 1e-8)
    if np.any(np.diff(required_s) < minimum - tolerance):
        raise ValueError(f'Beam {beam_index}: required stations are closer than the minimum horseshoe spacing; reduce the minimum or revise the required stations.')
    retained = list(required_s)
    for left, right in zip(required_s[:-1], required_s[1:]):
        candidates = candidate_s[(candidate_s > left + tolerance) & (candidate_s < right - tolerance)]
        while len(candidates):
            first = np.searchsorted(candidates, left + minimum - tolerance, side='left')
            last = np.searchsorted(candidates, right - minimum + tolerance, side='right') - 1
            if first > last:
                break
            a, b = candidates[first], candidates[last]
            if b - a < minimum - tolerance:
                retained.append((a + b) / 2)
                break
            retained.extend((a, b))
            left, right = a, b
            candidates = candidates[first + 1:last]
    return np.unique(retained)


def mesh_beam(beam: Beam, panels=40, stations=(), *, mesh_recipe=CURRENT_MESH_RECIPE):
    mesh_recipe = checked_recipe(mesh_recipe)
    breaks = mesh_breaks(beam, mesh_recipe)
    settings = beam_settings(beam, panels)
    lo, hi = beam.domain
    if hi <= lo:
        raise ValueError(f"Beam {beam.index} has an empty parameter range.")
    # Parameter t is arbitrary; generated spacing is in material arc length.
    if mesh_recipe == CURRENT_MESH_RECIPE:
        arc_map = material_arc(beam)
        total, arc_at, parameter_at = arc_map.total, arc_map.at, arc_map.inverse
    else:
        # Retain both historical recipes exactly, including their quadrature.
        dense_t = np.unique(np.r_[np.linspace(lo, hi, 2049), breaks])
        # A doubled station's rigid position jump is not beam material.
        intervals = beam.position(dense_t[1:], side="left") - beam.position(dense_t[:-1], side="right")
        arc = np.r_[0., np.cumsum(np.linalg.norm(intervals, axis=1))]
        if arc[-1] <= 1e-12 or np.any(np.diff(arc) <= 0):
            raise ValueError(f"Beam {beam.index} has zero-length geometry.")
        total = arc[-1]
        arc_at = lambda t: np.interp(t, dense_t, arc)
        parameter_at = lambda s: np.interp(s, arc, dense_t)
    required = np.unique(np.r_[breaks, stations])
    if not np.all(np.isfinite(required)) or np.any(required < lo) or np.any(required > hi):
        raise ValueError(f"Attachment station is outside beam {beam.index}'s parameter range.")
    if 'nodes' in settings:
        base_nodes = np.array(settings['nodes'])
        if base_nodes[0] != lo or base_nodes[-1] != hi:
            raise ValueError(f'Beam {beam.index}: explicit nodes must include the domain endpoints {lo:g} and {hi:g}.')
    else:
        if settings['spacing'] == 'uniform-breaks':
            # Distribute each mandatory-station span independently. Appending
            # breaks to a global grid creates accidental near-coincident pairs.
            # Round each span's interval count to the requested mean spacing;
            # equal mirrored spans therefore receive equal counts. A short
            # span between two required stations must still remain a panel.
            anchors = arc_at(np.unique(np.r_[lo, required, hi]))
            widths = np.diff(anchors)
            counts = np.maximum(1, np.floor(widths / (total / settings['count']) + .5)).astype(int)
            s = np.r_[np.concatenate([left + width*np.arange(n)/n
                for left, width, n in zip(anchors[:-1], widths, counts)]), total]
        elif settings['spacing'] == 'modified-cosine':
            # Reproduce the distribution checked against the printed ISAE
            # SA-2 coordinates; it is an option, not a universal ASWING default.
            # See docs/validation/isae-sa1-sa5-spacing-20261029.md.
            n = settings['count']
            angle = math.asin(float(np.nextafter(np.float32(1), np.float32(0))))
            u = np.sin((2 * np.arange(n + 1) / n - 1) * angle)
            eta = .7 * u + .3 * u**3
            eta[0], eta[-1] = -1., 1.
            if n % 2 == 0:
                eta[n // 2] = 0.
            s = total * (1 + eta) / 2
        else:
            fraction = np.linspace(0, 1, settings['count'] + 1)
            s = total * ((1 - np.cos(np.pi * fraction)) / 2 if settings['spacing'] == 'cosine' else fraction)
        base_nodes = parameter_at(s)
        if settings['spacing'] == 'modified-cosine':
            base_nodes[0], base_nodes[-1] = lo, hi
    # Snap near-coincident boundaries to declared breaks to avoid vanishing
    # panels from floating-point cosine spacing (especially at t=0).
    minimum = settings.get('min_spacing', 0.)
    if minimum > 0:
        spaced = minimum_spaced_nodes(arc_at(base_nodes), arc_at(required), minimum, total, beam.index)
        base_nodes = parameter_at(spaced)
    for point in required:
        base_nodes[np.abs(base_nodes - point) < 1e-11 * (hi - lo)] = point
    nodes = np.unique(np.r_[base_nodes, required])
    if np.any(np.diff(nodes) <= 1e-12 * (hi-lo)):
        raise ValueError(f'Beam {beam.index}: node stations are too close; remove or move the nearly coincident nodes.')
    ns = arc_at(nodes)
    length = arc_map.between(nodes[:-1], nodes[1:]) if mesh_recipe == CURRENT_MESH_RECIPE else np.diff(ns)
    if np.any(length <= 1e-12 * total):
        raise ValueError(f'Beam {beam.index}: nodes are too close in material arc length.')
    if minimum > 0 and np.any(length < minimum - 1e-11 * total):
        raise ValueError(f'Beam {beam.index}: reconstructed nodes violate the minimum horseshoe spacing.')
    theta = np.arccos(np.clip(1 - 2 * ns / total, -1, 1))
    sm = total * (1 - np.cos((theta[:-1] + theta[1:]) / 2)) / 2
    tm = parameter_at(sm)
    r0, r1 = beam.position(nodes[:-1], side="right"), beam.position(nodes[1:], side="left")
    portion = arc_map.between(nodes[:-1], tm) if mesh_recipe == CURRENT_MESH_RECIPE else sm-ns[:-1]
    fraction = (portion / length)[:, None]
    rm = r0 + fraction * (r1 - r0)
    ts = parameter_at((ns[:-1]+ns[1:])/2)
    return PanelMesh(beam, nodes[:-1], nodes[1:], tm, r0, r1, rm,
                     surface_frame(beam, tm), length, ts=ts, theta=np.pi-theta, mesh_recipe=mesh_recipe)


def model_meshes(model, panels=40, loads=(), *, mesh_recipe=CURRENT_MESH_RECIPE):
    panels = normalize_discretization(panels, model)
    required = requirements(model, loads, mesh_recipe=mesh_recipe)
    return [mesh_beam(b, panels, [r['t'] for r in required[b.index]], mesh_recipe=mesh_recipe) for b in model.beams]


def undeformed_mesh(mesh):
    """Recover jig coordinates on the exact supplied material intervals.

    This also works for deformed meshes restored from a physical checkpoint.
    Do not remesh: attachment stations and the circulation ordering must survive.
    The arc quadrature is the one used by mesh_beam, excluding rigid jumps.
    """
    beam = mesh.beam
    checked_recipe(mesh.mesh_recipe)
    if mesh.mesh_recipe == CURRENT_MESH_RECIPE:
        arc_map = material_arc(beam)
        length = arc_map.between(mesh.t0, mesh.t1)
        fraction = arc_map.between(mesh.t0, mesh.tm)/length
    else:
        lo, hi = beam.domain
        dense_t = np.unique(np.r_[np.linspace(lo, hi, 2049), mesh_breaks(beam, mesh.mesh_recipe)])
        delta = beam.position(dense_t[1:], side='left')-beam.position(dense_t[:-1], side='right')
        arc = np.r_[0., np.cumsum(np.linalg.norm(delta, axis=1))]
        s0, s1, sm = [np.interp(t, dense_t, arc) for t in (mesh.t0, mesh.t1, mesh.tm)]
        length, fraction = s1-s0, (sm-s0)/(s1-s0)
    r0, r1 = beam.position(mesh.t0, side='right'), beam.position(mesh.t1, side='left')
    rm = r0+fraction[:, None]*(r1-r0)
    return PanelMesh(beam, mesh.t0, mesh.t1, mesh.tm, r0, r1, rm,
                     surface_frame(beam, mesh.tm), length, ts=mesh.ts, theta=mesh.theta, mesh_recipe=mesh.mesh_recipe)


def _streamwise_chord(vector, span):
    """Display-only chord unsweeping (ASWING plotting option U).

    Shear the chord along the local span until its projection on the plane
    normal to body x has no spanwise component. This keeps the section surface
    plane and twist; an untwisted chord becomes body-x aligned with length
    chord/cos(sweep), as described in Drela's FAQ. A body-x-aligned span has no
    finite streamwise projection, so retain its normal chord for drawing.
    """
    transverse = span.copy()
    transverse[..., 0] = 0.
    denominator = np.sum(transverse*transverse, axis=-1)
    shear = np.divide(-np.sum(vector*transverse, axis=-1), denominator,
                      out=np.zeros_like(denominator), where=denominator > 1e-12)
    return vector+shear[..., None]*span


def geometry_summary(model, panels=40, meshes=None):
    out = []
    for mesh in (meshes if meshes is not None else model_meshes(model, panels)):
        b = mesh.beam
        if b.lifting:
            f0 = surface_frame(b, mesh.t0, "right") if mesh.frame0 is None else mesh.frame0
            f1 = surface_frame(b, mesh.t1, "left") if mesh.frame1 is None else mesh.frame1
            c0, c1 = b.value("chord", mesh.t0, side="right"), b.value("chord", mesh.t1, side="left")
            x0, x1 = b.value("Xax", mesh.t0, side="right"), b.value("Xax", mesh.t1, side="left")
            le0, le1 = mesh.r0 - (c0 * x0)[:, None] * f0[..., 0], mesh.r1 - (c1 * x1)[:, None] * f1[..., 0]
            te0, te1 = le0 + c0[:, None] * f0[..., 0], le1 + c1[:, None] * f1[..., 0]
            quads = np.stack([le0, le1, te1, te0], axis=1).tolist()
            # Keep raw normal-section quads for existing output contracts.
            # Publish the alternative display geometry with identical topology
            # so modal/Bode snapshots can differentiate it before rendering.
            d0 = _streamwise_chord(c0[:, None]*f0[..., 0], f0[..., 1])
            d1 = _streamwise_chord(c1[:, None]*f1[..., 0], f1[..., 1])
            sle0, sle1 = mesh.r0-x0[:, None]*d0, mesh.r1-x1[:, None]*d1
            streamwise_quads = np.stack([sle0, sle1, sle1+d1, sle0+d0], axis=1).tolist()
        else:
            f0 = surface_frame(b, mesh.t0, "right") if mesh.frame0 is None else mesh.frame0
            f1 = surface_frame(b, mesh.t1, "left") if mesh.frame1 is None else mesh.frame1
            radius0 = b.value("radius",mesh.t0,side="right")
            radius1 = b.value("radius",mesh.t1,side="left")
            if np.any(radius0 < 0) or np.any(radius1 < 0):
                raise ValueError(f"Beam {b.index}: body radius must be nonnegative.")
            quads = []
            if np.any(radius0) or np.any(radius1):
                angle = np.arange(13)*2*np.pi/12
                rings0 = mesh.r0[:,None,:]+radius0[:,None,None]*(np.cos(angle)[None,:,None]*f0[:,None,:,0]+np.sin(angle)[None,:,None]*f0[:,None,:,2])
                rings1 = mesh.r1[:,None,:]+radius1[:,None,None]*(np.cos(angle)[None,:,None]*f1[:,None,:,0]+np.sin(angle)[None,:,None]*f1[:,None,:,2])
                quads = np.stack([rings0[:,:-1],rings1[:,:-1],rings1[:,1:],rings0[:,1:]],axis=2).reshape(-1,4,3).tolist()
                # Concentric radius jumps have an annular face. Use a common
                # circular basis; twisting a circular section changes no area.
                for i in range(len(mesh.t1)-1):
                    inner_radius,outer_radius=radius1[i],radius0[i+1]
                    scale=np.linalg.norm(mesh.r1[i])+np.linalg.norm(mesh.r0[i+1])+mesh.length[i]+mesh.length[i+1]
                    if inner_radius==outer_radius or np.linalg.norm(mesh.r1[i]-mesh.r0[i+1])>64*np.finfo(float).eps*scale or np.linalg.norm(f1[i,:,1]-f0[i+1,:,1])>1e-8:continue
                    circle=np.cos(angle)[:,None]*f1[i,:,0]+np.sin(angle)[:,None]*f1[i,:,2]
                    inner=mesh.r1[i]+inner_radius*circle;outer=mesh.r1[i]+outer_radius*circle
                    quads.extend(np.stack([inner[:-1],outer[:-1],outer[1:],inner[1:]],axis=1).tolist())
        out.append(dict(index=b.index, name=b.name, lifting=b.lifting, physical_index=b.physical_index,
                        panels=len(mesh.tm), quads=quads, axis=np.stack([mesh.r0, mesh.r1], axis=1).tolist()))
        if b.lifting:
            out[-1]['streamwise_quads'] = streamwise_quads
        # Give the viewer the topology of an automatically mirrored root. The
        # raw normal-section quads remain unchanged for outputs/linearization;
        # only the renderer trims their overlapping inboard portions.
        if b.lifting and all(k not in b.distributions or b.distributions[k].t[0] == 0
                             for k in ("x", "y", "z", "twist", "chord", "Xax")):
            joins = np.flatnonzero((mesh.t1[:-1] == 0) & (mesh.t0[1:] == 0))
            if len(joins) == 1:
                out[-1]["mirror_join"] = int(joins[0] + 1)
    return out


def attachment_geometry(model, nodes=None):
    """Actual pylon/strut endpoints and engine disk circles for the workbench."""
    from .propulsion import engine_axes
    beams = {b.index: b for b in model.beams}
    objects = []
    def mount(beam, t):
        original = beams[int(beam)].position(t)
        if nodes is None:
            return original, original, np.eye(3)
        node = min((n for n in nodes if n["beam"] == int(beam)), key=lambda n: abs(n["t"]-t))
        if abs(node["t"]-t) > 1e-10*max(1.,abs(t)):
            raise ValueError("Attachment is missing from the deformed geometry nodes.")
        return original, np.asarray(node["position"]), np.asarray(node["rotation"])
    for kind in ("strut", "engine", "weight", "sensor"):
        rows = active_weights(model) if kind == 'weight' else model.records.get(kind, [])
        for row in rows:
            offset = 2 if kind == "engine" else 1 if kind == "sensor" else 0
            station = analysis_weight_station(model, row) if kind == 'weight' else row[offset+1]
            original, attached, q = mount(row[offset], station)
            p = attached+q@(row[offset+2:offset+5]-original)
            segments = [[attached.tolist(),p.tolist()]]
            if kind == 'sensor':
                from .sensors import sensor_orientation
                axes, _, _ = sensor_orientation(row)
                if axes is not None:
                    for axis in (q@axes).T:
                        segments.append([p.tolist(), (p+.15*model.reference[0,1]*axis).tolist()])
            if kind == "strut":
                segments.append([p.tolist(),row[5:8].tolist()])
            elif kind == "engine":
                axes = engine_axes(row[7:10],q)
                radius = abs(row[12])
                if radius:
                    angle = np.linspace(0,2*np.pi,49)
                    circle = p+radius*(np.cos(angle)[:,None]*axes[:,1]+np.sin(angle)[:,None]*axes[:,2])
                    segments.extend(np.stack([circle[:-1],circle[1:]],axis=1).tolist())
                segments.append([p.tolist(),(p-max(radius,.1*model.reference[0,1])*axes[:,0]).tolist()])
            objects.append(dict(kind=kind,beam=int(row[offset]),segments=segments))
    from .joints import hinge_laws
    hinges = hinge_laws(model.records)
    for index, row in enumerate(model.records.get("joint", []), 1):
        _, first, q = mount(row[0], row[2])
        _, second, _ = mount(row[1], row[3])
        segments = [[first.tolist(), second.tolist()]]
        if index in hinges:
            axis = q@hinges[index].axis
            half = .2*model.reference[0, 1]*axis
            segments.append([(second-half).tolist(), (second+half).tolist()])
        objects.append(dict(kind="hinge" if index in hinges else "joint", joint=index,
                            beam=int(row[0]), segments=segments))
    return objects
