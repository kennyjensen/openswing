"""Pinned SA-11 sources and explicit input reconstructions; never run upstream code."""
from pathlib import Path
import csv, hashlib, json, re, sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes, surface_frame, mesh_beam

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE = ROOT / '.reference/isae-validation' / REVISION
FOLDER = next(CACHE.glob('1 - Aerodynamics/SA*/SA - 11 - *'))
DEST = ROOT / 'docs/validation'
NAMES = ['wing_alone', 'wingtip_up', 'wingtip_up_and_down', 'wing_extension']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def reconstruction(name, source):
    lines = source.splitlines(keepends=True)
    if name == 'wingtip_up':
        old = '*     1      1       0.1            0.1        1'
        assert source.count(old) == 1
        return source.replace(old, '*     0.1      0.1'), 'station_scaling', (
            'Replace the invalid five-entry Joint scaling line with its two real-column factors, '
            '0.1 and 0.1. Integer beam identifiers and joint type are not scaled.')
    if name == 'wingtip_up_and_down':
        i = next(i for i, s in enumerate(lines) if s.strip() == 'Joint')
        lines.insert(i + 2, '*     0.1      0.1\n')
        return ''.join(lines), 'station_scaling', (
            'Insert Joint real-column scales 0.1,0.1 so all four root stations use the same '
            'parameter units as the geometry. No geometry or section-property edit.')
    if name == 'wingtip_up_cant0':
        active = False; changed = 0
        for i, line in enumerate(lines):
            if line.strip() == 'Joint': active = True; continue
            if active and line.strip() == 'End': break
            fields = line.split()
            if active and len(fields) == 5 and fields[:2] in [['1', '2'], ['1', '3']]:
                fields[3] = '1.5257' if fields[1] == '2' else '-1.5257'
                lines[i] = '      ' + '      '.join(fields) + '\n'; changed += 1
        assert changed == 2
        return ''.join(lines), 'joint_station', (
            'Change only the winglet-side joint parameters to their root values +/-1.5257; '
            'these winglets use signed z as parameter. Retain the tenfold geometry scale, '
            'different reference area and asymmetric twist. No experimental curve is assigned.')
    return None


def setup(source):
    rows = []
    try:
        model = parse_asw(source)
    except ValueError as exc:
        return dict(parsed=False, error=str(exc), setups=[])
    for panels in [25, 50, 100]:
        try:
            meshes = model_meshes(model, panels)
            rows.append(dict(panels=panels, status='constructed', strips=sum(len(m.tm) for m in meshes)))
        except ValueError as exc:
            rows.append(dict(panels=panels, status='rejected', error=str(exc)))
    beams = []
    for beam in model.beams:
        lo, hi = beam.domain; t = (lo+hi)/2 if lo >= 0 or hi <= 0 else hi/2
        frame = surface_frame(beam, t)
        mesh = mesh_beam(beam, 100)
        edges = []
        for t_edge, side in [(mesh.t0, 'right'), (mesh.t1, 'left')]:
            c = surface_frame(beam, t_edge, side=side)[..., 0]
            chord = beam.value('chord', t_edge, side=side)
            axis = beam.value('Xax', t_edge, side=side)
            le = beam.position(t_edge, side=side) - (chord*axis)[:, None]*c
            edges.append((le, le+chord[:, None]*c))
        le0, te0 = edges[0]; le1, te1 = edges[1]
        triangle_a = .5*np.cross(le1-le0, te1-le0)
        triangle_b = .5*np.cross(te1-le0, te0-le0)
        beams.append(dict(index=beam.index, physical_index=beam.physical_index, domain=list(beam.domain),
            endpoints=beam.position([lo, hi]).tolist(), frame_at=t, frame=frame.tolist(),
            geometry_diagnostic=dict(requested_intervals=100, actual_strips=len(mesh.tm),
                area_of_section_quadrilaterals=float(np.linalg.norm(triangle_a, axis=1).sum()+np.linalg.norm(triangle_b, axis=1).sum()),
                xy_projected_area_of_section_quadrilaterals=float(abs(triangle_a[:, 2]).sum()+abs(triangle_b[:, 2]).sum()),
                axis_length=float(mesh.length.sum()),
                main_wing_horizontal_cut_incidence_deg=float(np.rad2deg(np.arctan2(frame[0, 2], frame[2, 2]))) if beam.index == 1 else None),
            distributions={k: dict(t=d.t.tolist(), values=d.values.tolist()) for k, d in beam.distributions.items()}))
    return dict(parsed=True, setups=rows, reference=model.reference.tolist(), constants=model.constants.tolist(),
        units=model.units.declarations, beams=beams, joints=[r.tolist() for r in model.records.get('joint', [])])


def paired_csv(path, reverse):
    raw = list(csv.reader(path.open())); assert len(raw[0]) == 8 and raw[1] == ['X', 'Y']*4
    out = {}
    for j, name in enumerate(NAMES):
        values = []; missing = []
        for i, row in enumerate(raw[2:], 3):
            pair = row[2*j:2*j+2]
            if not any(pair): missing.append(i); continue
            assert len(pair) == 2 and all(pair), (path, i, j)
            pair = list(map(float, pair))
            values.append(dict(row=i, raw_xy=pair, xy=pair[::-1] if reverse else pair))
        out[name] = dict(path=path.relative_to(CACHE).as_posix(), sha256=sha(path),
            header=raw[0][2*j], columns=[2*j, 2*j+1], values=values, empty_rows=missing,
            raw_axes=['CL', 'alpha_deg'] if reverse else ['CL', 'CD'],
            normalized_axes=['alpha_deg', 'CL'] if reverse else ['CL', 'CD'])
    return out


def main():
    manifest = json.loads((CACHE.parent / 'manifest.json').read_text()); assert manifest['revision'] == REVISION
    pins = {}
    for p in sorted(FOLDER.rglob('*')):
        if not p.is_file(): continue
        name = p.relative_to(CACHE).as_posix(); pin = manifest['files'][name]
        assert sha(p) == pin['sha256'] and p.stat().st_size == pin['bytes'], name
        pins[name] = pin
    models = []; derived = []
    for p in sorted(FOLDER.rglob('*.asw')):
        source = p.read_text(); row = dict(name=p.stem, path=p.relative_to(CACHE).as_posix(),
            sha256=sha(p), source=source, **setup(source)); models.append(row)
        candidate = reconstruction(p.stem, source)
        if candidate is not None:
            text, kind, note = candidate; parsed = setup(text)
            assert parsed['parsed'] and all(s['status'] == 'constructed' for s in parsed['setups'])
            if row['parsed']:
                assert row['beams'] == parsed['beams']
                assert row['reference'] == parsed['reference'] and row['constants'] == parsed['constants']
                original = parse_asw(source); reconstructed = parse_asw(text)
                for key in original.records:
                    if key != 'joint':
                        assert all(np.array_equal(a, b) for a, b in zip(original.records[key], reconstructed.records[key], strict=True))
            else:
                # Prove that the invalid scaling line is the sole textual edit.
                assert p.stem == 'wingtip_up'
                assert len([1 for a, b in zip(source.splitlines(), text.splitlines(), strict=True) if a != b]) == 1
            path = DEST / f'isae-sa11-{p.stem}-{kind}.asw'; path.write_text(text)
            derived.append(dict(name=p.stem, case_id=p.stem+'_'+kind, kind=kind, note=note,
                source=text, sha256=sha(path), artifact=path.relative_to(ROOT).as_posix(), **parsed))
    archived = []
    for p in sorted(FOLDER.rglob('*_Ma_0_*.txt')):
        rows = np.loadtxt(p, skiprows=3); assert rows.shape == (41, 82)
        nominal = float(re.search(r'Ma_0_(\d+)', p.name)[1])/100
        name = next(n for n in NAMES if p.name.startswith(n+'_Ma'))
        archived.append(dict(name=name, nominal_mach=nominal, path=p.relative_to(CACHE).as_posix(), sha256=sha(p),
            headers=p.read_text().splitlines()[:3], rows=rows.tolist(),
            speeds=np.unique(rows[:, 69]).tolist(), alpha=rows[:, 71].tolist(),
            actual_equals_reference_flow=bool(np.array_equal(rows[:, 69:72], rows[:, 72:75])),
            all_convergence_flags_one=bool(np.all(rows[:, 2] == 1))))
    commands = [dict(path=p.relative_to(CACHE).as_posix(), sha256=sha(p), source=p.read_text())
                for p in sorted(FOLDER.rglob('*.sh'))]
    experimental = {str(m): dict(lift=paired_csv(FOLDER/'Experimental_Data'/f'Ma0{int(m*10)}_CL_alpha.csv', True),
        drag=paired_csv(FOLDER/'Experimental_Data'/f'KC135_MA0{int(m*100)}.csv', False)) for m in [.7, .8]}
    primary = ROOT / '.reference/isae-sa11/NASA-TN-D-8473.pdf'
    assert sha(primary) == 'a91ebb0b9b51b476cedc0822cffd76325bd0b852f395c08b335f2347e0aa96a7'
    notes = [
        'SA-11 is explicitly a transonic tendency study in the ISAE report, outside ASWING design validity. PG does not represent shock or wave drag.',
        'Only two literal files construct; three preserve their original syntax/attachment failures. Every derived input is separately labeled and changes only joint syntax/stations.',
        'The cant0 file has geometry ten times larger, a different reference area, and opposite signed left twist. It has no archived polar or assigned experimental curve.',
        'The baseline file uses dCLda=7, Cdp=.01818, Cdf=0 and CLmax=3; other main wings use dCLda=6.34 and spanwise Cdp/Cdf, with different/default CLmax. These are not isolated geometry variations.',
        'CSV headers map pair3 to upper/lower winglets and pair4 to tip extension. MATLAB lift plotting swaps those two labels; this audit follows the headers. Drag plotting uses their correct mapping.',
        'Lift CSVs have two header rows, but MATLAB asks for three; all numeric rows, including the first, are retained here. Its experimental slope calculations repeatedly select baseline columns, even for other configurations.',
        'MATLAB adds CD=.0064 at nominal Mach .7 and CD=.0075 at .8. These are postprocessing offsets, not raw solver predictions; they must not be silently fitted or added to OpenSwing.',
        'Archived speeds are prescribed approximately from the Mach labels; actual kinematic Mach must be computed using input sound speed340.21. The ISAE report explicitly says PG is activated; scripts do not record the exact PG value or initial K/F state. PG-off runs are diagnostics, not the reported experimental setup.',
        'Primary NASA coefficients use exposed semispan area .4648m2. Half the input Sref is .46645m2. Retain and quantify this difference rather than silently renormalizing.',
        'Primary tunnel wing/fuselage gap affects absolute axial force and both lift and drag; primary treats the effect as systematic across configurations at equal conditions. The apparatus includes nacelles, fillets and representative wing flexibility.',
        'Primary cruise repeats differ by about .0002 in CD, <.2% in CL and <.4% in rolling coefficient. These are repeatability indicators, not complete uncertainty bounds.',
        'ASWING chord and twist refer to the local swept beam section. Compare physical section frames and areas; raw chord values cannot be equated directly with streamwise chord dimensions.',
        'Primary upper/lower winglet spans, cant and incidence require reconciliation with the literal beam axes. Main input moment references also differ; no reference shift is chosen to minimize error.',
        'Experimental arrays remain ISAE digitizations; independent extraction and complete uncertainty propagation are outstanding.'
    ]
    report = dict(status='SOURCE_AUDIT_NO_PHYSICAL_VALIDATION', revision=REVISION, sources=pins,
        script_sha256=sha(Path(__file__)), models=models, derived=derived, archived=archived,
        commands=commands, experimental=experimental, limitations=notes,
        airfoil_coordinates=[dict(path=p.relative_to(CACHE).as_posix(), sha256=sha(p),
            title=p.read_text().splitlines()[0], rows=np.loadtxt(p, skiprows=1).tolist())
            for p in sorted((FOLDER/'KC_135_Airfoils').glob('*.txt'))],
        isae_report=dict(path='5 - Technical Reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.pdf',
            sha256=sha(CACHE/'5 - Technical Reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.pdf'),
            PG_reported_enabled=True, scope='SA-11, Figure22, AppendixD; transonic tendencies explicitly outside the ASWING design regime'),
        primary=dict(title='Effect of Winglets on a First-Generation Jet Transport Wing. I: Longitudinal Aerodynamic Characteristics of a Semispan Model at Subsonic Speeds',
            authors=['Peter F. Jacobs', 'Stuart G. Flechner', 'Lawrence C. Montoya'], year=1977,
            report='NASA-TN-D-8473', url='https://ntrs.nasa.gov/citations/19780012121', path=primary.relative_to(ROOT).as_posix(), sha256=sha(primary),
            review=json.loads((ROOT/'.reference/isae-sa11/primary-visual-review.json').read_text())),
        postprocessing=dict(path=(FOLDER/'Post_traitement.m').relative_to(CACHE).as_posix(), source=(FOLDER/'Post_traitement.m').read_text(),
            drag_offsets={'0.7': .0064, '0.8': .0075}, lift_csv_pairs_follow_headers=True))
    (DEST/'isae-sa11-sources.json').write_text(json.dumps(report, indent=2)+'\n')
    print('SA11 source audit:',len(pins),'files,',len(models),'literal models,',len(derived),'explicit reconstructions,',len(archived),'archived polars',flush=True)


if __name__ == '__main__': main()
