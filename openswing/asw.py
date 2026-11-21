"""ASW configuration reader, preserving the original document for lossless save.

Reference: Drela's ASWING User Guide, configuration-definition section.
Raw model data stay in the file's consistent input units. Conversion is explicit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import math
import operator
import re
import numpy as np
from .beam_spline import NATURAL, checked_interpolation, segment_spline


class AswError(ValueError):
    def __init__(self, message: str, line: int | None = None):
        self.line = line
        super().__init__(f"Line {line}: {message}" if line else message)


DEFAULTS = dict.fromkeys(
    "x y z twist EIcn EIcs EIsn mgcc mgnn mg Ccg Ncg Dmgcc Dmgnn Dmg DCcg DNcg "
    "Cea Nea Cta Nta tdeps tdgam Cshell Nshell Atshell radius Cdf Cdp alpha Cm".split(), 0.0
)
RIGID = {"EIcc", "EInn", "GJ", "EA", "GKc", "GKn"}
DEFAULTS.update(dict.fromkeys(RIGID, math.inf))
DEFAULTS.update(Xax=0.5, CLmax=2.0, CLmin=-2.0, dCLda=2 * math.pi)
CANONICAL = {v.lower(): v for v in DEFAULTS} | {"chord": "chord"}
# User Guide, "Considerations for Data Discontinuities". This is the
# documented native default, not OpenSwing's broader physical-break policy.
# Native builds can enable additional properties in INDEXB.INC.
ASWING_DEFAULT_BREAKS = frozenset(
    "x y z twist Dmgcc Dmgnn Dmg DCcg DNcg chord alpha".split()
)


def canonical(name: str) -> str:
    if name.lower() in CANONICAL:
        return CANONICAL[name.lower()]
    # Control derivatives have no artificial implementation-dependent count limit.
    match = re.fullmatch(r"dC([LMD])dF([1-9]\d*)", name, re.I)
    if match:
        return f"dC{match[1].upper()}dF{match[2]}"
    return name


def numbers(line: str, number: int) -> list[float]:
    try:
        vals = []
        for token in line.replace(",", " ").split():
            token = token.replace("D", "e").replace("d", "e")
            try:
                value = float(token)
            except ValueError:
                # Fortran formatted/list-directed input permits an exponent
                # sign without E: e.g. 6.2832+00 and 2.1-6 in public .asw files.
                match = re.fullmatch(r"([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))([+-][0-9]+)", token)
                if match is None:
                    raise
                value = float(match[1] + "e" + match[2])
            vals.append(value)
    except ValueError as exc:
        raise AswError("Expected numeric values.", number) from exc
    if not all(math.isfinite(v) for v in vals):
        raise AswError("Data must be finite numbers (use zero for infinite stiffness).", number)
    return vals


def _exact_number(token):
    """Exact source decimal, including ASW/Fortran exponent spellings.

    This accompanies already validated numeric input. It never replaces the
    historical binary64 arithmetic used for raw records and distributions.
    """
    token = token.replace('D', 'e').replace('d', 'e')
    try:
        return Fraction(token)
    except ValueError:
        match = re.fullmatch(r'([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))([+-][0-9]+)', token)
        if match is None:
            raise
        return Fraction(match[1]+'e'+match[2])


@dataclass
class Distribution:
    name: str
    t: np.ndarray
    values: np.ndarray
    line: int
    interpolation: str = field(default=NATURAL, kw_only=True)
    _segments: list = field(init=False, repr=False)
    _constant_rigid: bool = field(init=False, repr=False, default=False)

    def __setattr__(self, name, value):
        if name == 'interpolation' and name in self.__dict__:
            raise AswError('Interpolation policy is immutable; construct a new Distribution.')
        super().__setattr__(name, value)

    def __post_init__(self):
        try:
            checked_interpolation(self.interpolation)
        except ValueError as exc:
            raise AswError(str(exc), self.line) from exc
        self.t = np.asarray(self.t, dtype=float)
        self.values = np.asarray(self.values, dtype=float)
        if self.t.ndim != 1 or self.values.shape != self.t.shape:
            raise AswError(f"{self.name}: stations and values must be matching one-dimensional arrays.", self.line)
        if not np.all(np.isfinite(self.t)) or not np.all(np.isfinite(self.values)):
            raise AswError(f"{self.name}: stations and values must be finite (use zero for infinite stiffness).", self.line)
        # Published FFWT models use a lone zero stiffness sample as a rigid
        # override. Its coordinate is metadata, not a spline knot or mesh
        # station. Other singletons cannot define a spline and remain errors.
        self._constant_rigid = bool(len(self.t) == 1 and self.name in RIGID and self.values[0] == 0.)
        if self.constant_rigid:
            self._segments = []
            self._compiled_t, self._compiled_values = self.t.copy(), self.values.copy()
            self._compiled_interpolation = self.interpolation
            return
        if len(self.t) < 2:
            raise AswError(f"{self.name} needs at least two stations.", self.line)
        differences = np.diff(self.t)
        if np.any(differences < 0) and not np.any(differences > 0):
            self.t, self.values = self.t[::-1].copy(), self.values[::-1].copy()
            differences = np.diff(self.t)
        if np.any(differences < 0):
            raise AswError(f"{self.name}: stations must be monotonic.", self.line)
        breaks = np.flatnonzero(differences == 0) + 1
        self._segments = []
        for ids in np.split(np.arange(len(self.t)), breaks):
            if len(ids) < 2:
                raise AswError(f"{self.name}: each side of a doubled station needs two points.", self.line)
            x, y = self.t[ids], self.values[ids]
            self._segments.append((x[0], x[-1], segment_spline(x, y, self.interpolation)))
        self._compiled_t, self._compiled_values = self.t.copy(), self.values.copy()
        self._compiled_interpolation = self.interpolation

    def evaluate(self, t, *, mirror=False, side="right", derivative=0):
        if side not in ("left", "right"):
            raise ValueError("side must be left or right")
        query = np.asarray(t, dtype=float)
        if self.constant_rigid:
            if operator.index(derivative) < 0:
                raise ValueError('Derivative order must be nonnegative.')
            return np.zeros_like(query)
        reflect = mirror and self.t[0] == 0
        negative_side = (query < 0) | ((query == 0) & (side == "left"))
        x = np.abs(query) if reflect else query
        out = np.empty_like(x)
        # A reflected discontinuity reverses the meaning of left/right.
        right = np.full(query.shape, side == "right")
        if reflect:
            right = np.where(negative_side, ~right, right)
        boundaries = np.array([v[0] for v in self._segments[1:]])
        ids = np.where(right, np.searchsorted(boundaries, x, side="right"),
                       np.searchsorted(boundaries, x, side="left"))
        for i, (_, end, spline) in enumerate(self._segments):
            sel = ids == i
            samples = x[sel]
            values = spline(samples, nu=derivative)
            # At the last knot, Horner evaluation can turn an exact zero
            # into a tiny negative radius. Retain the prescribed left-side
            # endpoint value exactly; nearby points and derivatives are live.
            if derivative == 0:
                terminal = samples == end
                if np.any(terminal):
                    values[terminal] = self.values[np.searchsorted(self.t, end, side="left")]
            out[sel] = values
        if reflect:
            if derivative % 2:
                out = np.where(negative_side, -out, out)
            if self.name == "y":
                out = np.where(negative_side, 2 * self.values[0] - out if derivative == 0 else -out, out)
        return out

    @property
    def constant_rigid(self):
        """A retained singleton zero encoding rigidity throughout the beam."""
        return self._constant_rigid

    @property
    def breaks(self):
        return self.t[:-1][np.diff(self.t) == 0]


@dataclass
class Beam:
    index: int
    physical_index: int
    name: str
    distributions: dict[str, Distribution]
    line: int

    @property
    def lifting(self):
        return "chord" in self.distributions

    @property
    def domain(self):
        d = self.distributions.get("chord")
        if d is None:
            d = next(self.distributions[k] for k in ("x", "y", "z") if k in self.distributions)
        return (-d.t[-1] if self.lifting and d.t[0] == 0 else d.t[0], d.t[-1])

    def value(self, name, t, *, side="right", derivative=0):
        name = canonical(name)
        if name in self.distributions:
            distribution = self.distributions[name]
            val = distribution.evaluate(t, mirror=self.lifting, side=side, derivative=derivative)
            if name in RIGID and derivative == 0:
                val = np.where(val == 0, np.inf, val)
            elif name in ("mg", "Dmg") and derivative == 0 and np.any(val < 0):
                # A spline can evaluate a zero weight as a tiny negative
                # number (e.g. extrapolation to the fw.asw tip). Preserve
                # signed input and any negative sample beyond roundoff.
                if np.all(distribution.values >= 0):
                    tolerance = 4 * np.finfo(float).eps * np.max(distribution.values)
                    val = np.where((val < 0) & (val >= -tolerance), 0.0, val)
            return val
        default = DEFAULTS.get(name)
        if re.fullmatch(r"dC[LMD]dF[1-9]\d*", name):
            default = 0.0
        if default is None:
            raise KeyError(name)
        return np.full_like(np.asarray(t, dtype=float), default if derivative == 0 else 0.0)

    def position(self, t, **kwargs):
        return np.stack([self.value(k, t, **kwargs) for k in ("x", "y", "z")], axis=-1)

    @property
    def breaks(self):
        """Required physical mesh breaks; shell recovery tables do not remesh."""
        return self.mesh_breaks()

    def mesh_breaks(self, *, include_shell=False):
        """Physical breaks, or the original all-table recipe for saved meshes."""
        all_breaks = []
        for name, d in self.distributions.items():
            if d.constant_rigid:
                continue
            # These fields only select where strain/stress is reported within
            # a section. Keep their spline breaks, but not as physical nodes.
            if not include_shell and name in {"Cshell", "Nshell", "Atshell"}:
                continue
            all_breaks.extend(d.breaks)
            if self.lifting and d.t[0] == 0:
                all_breaks.extend(-d.breaks)
                # Mirroring can introduce a slope break at the centerline even
                # when the input's first station is not doubled (sweep/dihedral).
                all_breaks.append(0.)
        lo, hi = self.domain
        return np.array(sorted({float(x) for x in all_breaks if lo < x < hi}))


@dataclass
class UnitSystem:
    declarations: dict[str, tuple[float, str]]

    def si_scales(self):
        """SI magnitude of one input L/T/F/M unit, including output scaling."""
        lookup = {
            "L": {"m": 1., "mm": .001, "cm": .01, "in": .0254, "ft": .3048},
            "T": {"s": 1., "sec": 1., "min": 60.},
            "F": {"N": 1., "kg": 9.80665, "g": .00980665, "oz": .2780138509537812, "lb": 4.4482216152605},
            "M": {"kg": 1., "g": .001, "oz": .028349523125, "lb": .45359237, "slug": 14.5939029372064},
        }
        out = {}
        for kind, (factor, label) in self.declarations.items():
            if label not in lookup[kind]:
                raise AswError(f"Unknown SI conversion for {kind} unit {label!r}; input-unit calculations remain available.")
            out[kind] = factor * lookup[kind][label]
        if "L" not in out:
            out["L"] = out["F"] * out["T"] ** 2 / out["M"]
        elif "T" not in out:
            out["T"] = math.sqrt(out["M"] * out["L"] / out["F"])
        elif "F" not in out:
            out["F"] = out["M"] * out["L"] / out["T"] ** 2
        elif "M" not in out:
            out["M"] = out["F"] * out["T"] ** 2 / out["L"]
        if not math.isclose(out["F"] * out["T"] ** 2, out["M"] * out["L"], rel_tol=1e-4):
            raise AswError("Inconsistent Unit declarations: F T² must equal M L.")
        return out


@dataclass
class Block:
    kind: str
    lines: list[tuple[int, str]]
    line: int
    header: str = ''
    end_line: int = 0


@dataclass
class Model:
    name: str
    source: str
    units: UnitSystem
    constants: np.ndarray
    reference: np.ndarray
    beams: list[Beam]
    records: dict[str, list[np.ndarray]]
    blocks: list[Block]
    diagnostics: list[str]
    beam_interpolation: str = field(default=NATURAL, kw_only=True)
    _parsed_signature: str | None = field(default=None, repr=False)
    _parsed_source: str | None = field(default=None, repr=False)

    def __setattr__(self, name, value):
        if name == 'beam_interpolation' and name in self.__dict__:
            raise AswError('Beam interpolation policy is immutable; parse a new model with the requested policy.')
        super().__setattr__(name, value)

    def __post_init__(self):
        try:
            checked_interpolation(self.beam_interpolation)
        except ValueError as exc:
            raise AswError(str(exc)) from exc
        if any(d.interpolation != self.beam_interpolation
               for beam in self.beams for d in beam.distributions.values()):
            raise AswError('Beam distributions must use the model interpolation policy.')

    def dumps(self, *, canonical=False):
        """ASW text only; retain beam_interpolation separately when reparsing."""
        from .asw_edit import serialize
        return serialize(self, canonical=canonical)

    @property
    def compatibility_notes(self):
        """Nonfatal native-input differences, recomputed after model edits.

        Detect value jumps in the actual scaled input tables. A repeated
        station with equal values is only a possible slope break and does
        not trigger the guide's warning. Stations refer to input t, before
        automatic reflection; no duplicate warning is generated for a mirror.
        Keep these separate from diagnostics, which block unsupported input.
        """
        notes = []
        for beam in self.beams:
            for name, distribution in beam.distributions.items():
                if name in ASWING_DEFAULT_BREAKS or re.fullmatch(r"dC[LM]dF[1-9]\d*", name):
                    continue
                if name not in CANONICAL.values() and not re.fullmatch(r"dCDdF[1-9]\d*", name):
                    continue  # Unknown properties already have a blocking diagnostic.
                t, values = distribution.t, distribution.values
                jumps = np.flatnonzero((t[1:] == t[:-1]) & (values[1:] != values[:-1]))
                if jumps.size:
                    notes.append(dict(code="aswing-default-kbreak", beam=beam.index,
                        property=name, line=distribution.line,
                        stations=t[jumps].tolist(), left=values[jumps].tolist(),
                        right=values[jumps + 1].tolist(),
                        mirrored=bool(beam.lifting and t[0] == 0)))
        return notes

    @property
    def controls(self):
        return sorted({int(k[5:]) for b in self.beams for k in b.distributions if re.fullmatch(r"dC[LMD]dF\d+", k)})

    @property
    def engine_controls(self):
        return sorted({int(row[0]) for row in self.records.get("engine", [])})


SCHEMAS = {
    "weight": (17, {0}, 6), "sensor": (12, {0, 1}, 6),
    "engine": (25, {0, 1, 2}, 11), "strut": (10, {0}, 10),
    "joint": (5, {0, 1, 4}, 4), "ground": (3, {0, 2}, 2),
    "constant": (3, set(), 3), "reference": (3, set(), 3),
}


def _table(block, width, integers=(), minimum=None, *, station_keys=None, station_columns=()):
    multiplier, adder = np.ones(width), np.zeros(width)
    exact_multiplier = dict.fromkeys(station_columns, Fraction(1))
    exact_adder = dict.fromkeys(station_columns, Fraction(0))
    indices = [i for i in range(width) if i not in integers]
    out = []
    for line, body in block.lines:
        if body[0] in "*+":
            vals = numbers(body[1:], line)
            if len(vals) > len(indices):
                raise AswError("Too many scaling values (integer columns are not scaled).", line)
            target = multiplier if body[0] == "*" else adder
            target[:] = 1 if body[0] == "*" else 0
            target[indices[:len(vals)]] = vals
            if station_keys is not None:
                exact = exact_multiplier if body[0] == '*' else exact_adder
                exact.update(dict.fromkeys(station_columns, Fraction(1 if body[0] == '*' else 0)))
                tokens = body[1:].replace(',', ' ').split()
                for column, token in zip(indices, tokens):
                    if column in exact:
                        exact[column] = _exact_number(token)
        else:
            vals = numbers(body, line)
            if len(vals) < (width if minimum is None else minimum) or len(vals) > width:
                raise AswError(f"{block.kind}: expected {minimum or width}–{width} columns, got {len(vals)}.", line)
            row = np.zeros(width)
            # Omitted optional values default to zero, without applying an adder.
            row[:len(vals)] = np.asarray(vals) * multiplier[:len(vals)] + adder[:len(vals)]
            if any(row[i] != int(row[i]) for i in integers):
                raise AswError("Index/type columns must contain integers.", line)
            out.append(row)
            if station_keys is not None:
                tokens = body.replace(',', ' ').split()
                station_keys.append({column: _exact_number(tokens[column])*exact_multiplier[column]+exact_adder[column]
                                     for column in station_columns if column < len(vals)})
    return out


def _reference_rows(block):
    """Current xyz rows, plus the published six-column zero-origin shorthand.

    ISAE and Durrant inputs label their trailing zero columns Xref/Yref/Zref.
    All reference locations at the origin are unambiguous under either the
    old shared-point convention or the current separate-point convention.
    No nonzero legacy coordinate map is inferred from those zero-only files.
    """
    data = [(line, body) for line, body in block.lines if body[0] not in '*+']
    if len(data) == 1 and len(numbers(data[0][1], data[0][0])) == 6:
        row = _table(block, 6)[0]
        if np.any(row[3:] != 0):
            raise AswError('Nonzero coordinates in a six-column Reference are not verified; use separate moment, acceleration and velocity reference rows.', data[0][0])
        return [row[:3]]
    return _table(block, 3)


def _beam(header, block, interpolation=NATURAL):
    parts = header.split()
    try:
        if not 2 <= len(parts) <= 3:
            raise ValueError()
        index = int(parts[1])
        physical = int(parts[2]) if len(parts) == 3 else index
    except ValueError as exc:
        raise AswError("Beam requires an integer index and optional physical index.", block.line) from exc
    if not block.lines:
        raise AswError("Missing beam name and distributions.", block.line)
    name = block.lines[0][1]
    distributions = {}
    groups = []
    for ln, text in block.lines[1:]:
        if text.split()[0].lower() == "t":
            fields = [canonical(n) for n in text.split()[1:]]
            if not fields or len(fields) != len(set(fields)):
                raise AswError("Distribution needs unique named columns after t.", ln)
            groups.append((fields, Block("distribution", [], ln)))
        elif not groups:
            raise AswError("Expected a distribution header starting with t.", ln)
        else:
            groups[-1][1].lines.append((ln, text))
    for fields, group in groups:
        station_keys = []
        rows = _table(group, len(fields) + 1, station_keys=station_keys, station_columns=(0,))
        if not rows:
            raise AswError("Empty distribution.", group.line)
        data = np.asarray(rows)
        if len(data) == 1 and (not set(fields) <= RIGID or np.any(data[0, 1:] != 0)):
            raise AswError('A singleton distribution table must contain only zero rigid-stiffness overrides; other properties need at least two stations.', group.line)
        for i, key in enumerate(fields):
            if key in distributions:
                raise AswError(f"Duplicate distribution {key} on beam {index}.", group.line)
            distributions[key] = Distribution(key, data[:, 0], data[:, i + 1], group.line,
                                              interpolation=interpolation)
            distribution = distributions[key]
            keys = tuple(row[0] for row in station_keys)
            if len(data) > 1 and data[-1, 0] < data[0, 0]:
                keys = keys[::-1]
            distribution._source_station_keys = keys
            distribution._source_station_values = distribution.t.copy()
    if not any(k in distributions for k in ("x", "y", "z")):
        raise AswError("Beam needs at least one x, y, or z distribution.", block.line)
    return Beam(index, physical, name, distributions, block.line)


def parse_asw(source: str, *, beam_interpolation=NATURAL) -> Model:
    """Parse literal ASW with an explicit, immutable beam-table policy.

    ASW text does not encode this OpenSwing option. Pass the same keyword when
    reloading a nondefault model's dumps(); untagged callers remain natural.
    This option does not change Jangle laws or time-forcing interpolation.
    """
    try:
        checked_interpolation(beam_interpolation)
    except ValueError as exc:
        raise AswError(str(exc)) from exc
    blocks, headers = [], []
    active = None
    for ln, raw in enumerate(source.splitlines(), 1):
        if raw.lstrip().startswith(("#", "%")):
            continue
        # Names may contain #/%; only ! starts an inline name comment.
        name_line = active is not None and (active.kind == "name" or
                    (active.kind == "beam" and not active.lines))
        body = (raw.split("!", 1)[0] if name_line else
                re.split(r"[!#%]", raw, maxsplit=1)[0]).strip()
        if not body:
            continue
        key = body.split()[0].lower()
        if key == "end":
            if active is None:
                raise AswError("End without an open block.", ln)
            active.end_line = ln
            active = None
        elif active is None:
            kind = "unit" if key == "units" else key
            active = Block(kind, [], ln, header=body)
            blocks.append(active)
            headers.append(body)
        else:
            active.lines.append((ln, body))
    if active:
        raise AswError(f"{active.kind} is missing End.", active.line)
    name, units, constants, reference = "Untitled aircraft", {}, None, None
    records, beams, diagnostics = {}, [], []
    weight_station_keys = []
    for header, block in zip(headers, blocks):
        kind = block.kind
        if kind == "name":
            if block.lines:
                name = block.lines[-1][1]
        elif kind == "unit":
            for ln, body in block.lines:
                parts = body.split()
                if len(parts) != 3 or parts[0] not in "LTFM" or len(parts[0]) != 1:
                    raise AswError("Unit row must be L/T/F/M, positive magnitude, and label.", ln)
                val = numbers(parts[1], ln)[0]
                if val <= 0:
                    raise AswError("Unit magnitude must be positive.", ln)
                units[parts[0]] = (val, parts[2])
        elif kind == "beam":
            beams.append(_beam(header, block, beam_interpolation))
        elif kind == "jangle":
            if not block.lines:
                raise AswError("Empty Jangle.", block.line)
            row = _table(Block(kind, block.lines[:1], block.line), 4, {0})[0]
            curve = _table(Block(kind, block.lines[1:], block.line), 2)
            if len(curve) < 2:
                raise AswError("Jangle needs at least two moment/angle pairs.", block.line)
            records.setdefault(kind, []).append({"header": row, "curve": np.asarray(curve)})
        elif kind in SCHEMAS:
            width, integers, minimum = SCHEMAS[kind]
            keys = [] if kind == 'weight' else None
            rows = _reference_rows(block) if kind == 'reference' else _table(block, width, integers, minimum,
                station_keys=keys, station_columns=(1,) if kind == 'weight' else ())
            if keys is not None:
                weight_station_keys.extend((row, int(row[0]), float(row[1]), key[1]) for row, key in zip(rows, keys))
            if kind == "constant":
                if rows:
                    constants = rows[-1]
            elif kind == "reference":
                if not 1 <= len(rows) <= 4:
                    raise AswError("Reference needs one to four rows.", block.line)
                reference = np.zeros((4, 3))
                reference[:len(rows)] = rows
            else:
                records.setdefault(kind, []).extend(rows)
        else:
            diagnostics.append(f"Unrecognized block {kind!r} at line {block.line}; preserved in source.")
    if len(units) < 3:
        raise AswError("Unit requires at least three of L, T, F, M.")
    if constants is None or np.any(constants <= 0):
        raise AswError("Constant requires positive gravity, density, and speed of sound.")
    if reference is None or reference[0, 0] < 0 or np.any(reference[0, 1:] <= 0):
        raise AswError("Reference requires nonnegative area and positive chord and span.")
    if not beams:
        raise AswError("At least one Beam is required.")
    beam_ids = [b.index for b in beams]
    if len(beam_ids) != len(set(beam_ids)):
        raise AswError("Beam indices must be unique.")
    refs = {"weight": [0], "sensor": [1], "engine": [2], "strut": [0], "joint": [0, 1], "ground": [0]}
    for kind, columns in refs.items():
        for row in records.get(kind, []):
            if any(int(row[col]) not in beam_ids for col in columns):
                raise AswError(f"{kind} references an undefined beam.")
    # Import locally because the law reuses this module's spline and errors.
    from .joints import hinge_laws
    hinge_laws(records)
    for beam in beams:
        for key in beam.distributions:
            if key not in CANONICAL.values() and not re.fullmatch(r"dC[LMD]dF\d+", key):
                diagnostics.append(f"Unrecognized distribution {key!r} on beam {beam.index}; preserved.")
    system = UnitSystem(units)
    try:
        system.si_scales()
    except AswError as exc:
        if "Unknown SI conversion" not in str(exc):
            raise
    model = Model(name, source, system, constants, reference, beams, records, blocks, diagnostics,
                  beam_interpolation=beam_interpolation)
    model._weight_station_keys = weight_station_keys
    from .sensors import validate_sensors
    validate_sensors(model)
    from .asw_edit import signature
    model._parsed_source = source
    model._parsed_signature = signature(model)
    return model


def weight_station(model, row):
    """Resolve a Weight station only from exact original decimal equality.

    Raw record arrays stay unchanged. An original scaled t may have rounded
    differently from the same exact decimal beam endpoint/discontinuity. Only
    those proven aliases use the beam's existing representation. No distance
    threshold applies; edited/replaced station data lose their provenance.
    Other attachment record types are deliberately outside this correction.
    """
    raw = float(row[1])
    source = next((entry for entry in getattr(model, '_weight_station_keys', ())
                   if entry[0] is row and entry[1] == row[0] and entry[2] == raw), None)
    if source is None:
        return raw
    beam = next((b for b in model.beams if b.index == int(row[0])), None)
    if beam is None:
        return raw
    def keys(distribution):
        saved = getattr(distribution, '_source_station_values', None)
        return (getattr(distribution, '_source_station_keys', None)
                if saved is not None and np.array_equal(distribution.t, saved) else None)
    candidates = []
    domain = beam.distributions.get('chord')
    if domain is None:
        domain = next((beam.distributions[k] for k in ('x', 'y', 'z') if k in beam.distributions), None)
    if domain is None:
        # An in-progress invalid edit must reach the existing model validator;
        # absence of a domain cannot certify an attachment alias.
        return raw
    domain_keys = keys(domain)
    if domain_keys is not None:
        candidates.append((domain_keys[-1], float(domain.t[-1])))
        if beam.lifting and domain.t[0] == 0 and domain_keys[0] == 0:
            candidates.append((-domain_keys[-1], -float(domain.t[-1])))
        else:
            candidates.append((domain_keys[0], float(domain.t[0])))
    for name, distribution in beam.distributions.items():
        if name in {'Cshell', 'Nshell', 'Atshell'} or distribution.constant_rigid:
            continue
        exact = keys(distribution)
        if exact is None:
            continue
        mirror = beam.lifting and distribution.t[0] == 0 and exact[0] == 0
        for i in np.flatnonzero(np.diff(distribution.t) == 0):
            # Distinct decimal inputs can round to the same binary64 number;
            # they do not provide an exact-equivalence certificate.
            if exact[i] != exact[i+1]:
                continue
            candidates.append((exact[i], float(distribution.t[i])))
            if mirror:
                candidates.append((-exact[i], -float(distribution.t[i])))
        if mirror:
            candidates.append((Fraction(0), 0.))
    matches = {value for exact, value in candidates if exact == source[3]}
    # Conflicting beam representations require their own geometry diagnosis.
    return matches.pop() if len(matches) == 1 else raw
