"""Prepare a source-pinned, two-angle SA-11 native capture; never run a solver."""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
REVISION = "f62943df20e9e4d7d9f50e070477b22426b5f865"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(out):
    if out.exists() or out.with_suffix('.zip').exists():
        raise SystemExit('Refusing to overwrite an existing capture directory or ZIP')
    cache = ROOT / 'reference/isae-validation' / REVISION
    source = next(cache.glob('1 - Aerodynamics/SA*/SA - 11 - */Aswing_Simulations/Wing_tip_up'))
    upstream = json.loads((cache.parent / 'manifest.json').read_text())['files']
    names = ['wingtip_up.asw', 'wingtip_up_polar_Ma_0_70.sh', 'wingtip_up_Ma_0_70.txt']
    files = {}
    pins = {}
    for name in names:
        path = source / name
        data = path.read_bytes()
        assert sha(data) == upstream[str(path.relative_to(cache))]['sha256'], path
        files['source/' + name] = data
        pins[str(path.relative_to(ROOT))] = sha(data)

    original = files['source/wingtip_up.asw'].decode()
    old_joint = '*     1      1       0.1            0.1        1'
    assert original.count(old_joint) == 1
    joint = original.replace(old_joint, '*     0.1      0.1')
    # Anchor each replacement to the original station and remaining columns.
    pattern = r'(?m)^(\s*-?12\.(?:426|9705)\s+\S+\s+\S+\s+\S+\s+)4(\s+\S+\s+0\.0\s*)$'
    minus4, count = re.subn(pattern, r'\g<1>-4\2', joint)
    assert count == 4, count
    variants = {'original': original, 'joint-only': joint, 'report-minus4': minus4}
    for name, content in variants.items():
        files[f'{name}/wingtip_up.asw'] = content.encode()
        if name != 'original':
            delta = ''.join(difflib.unified_diff(original.splitlines(True), content.splitlines(True),
                fromfile='source/wingtip_up.asw', tofile=f'{name}/wingtip_up.asw'))
            files[f'{name}/changes.diff'] = delta.encode()

    driver = files['source/wingtip_up_polar_Ma_0_70.sh'].decode()
    body = driver.split('<<EOF\n', 1)[1].rsplit('EOF', 1)[0]
    prefix, rest = body.split('!A 0.0\n', 1)
    assert '!V 240' in prefix and rest.count('!A ') == 40
    footer = rest.split('!A 10.0\n', 1)[1]
    assert footer.count('wingtip_up_Ma_0_70.txt') == 1
    commands = prefix + '!A 0.0\n+\n!A 1.0\n' + footer.replace('wingtip_up_Ma_0_70.txt', 'capture-polar.txt')
    files['commands.proposed.txt'] = commands.encode()

    rows = []
    for line in files['source/wingtip_up_Ma_0_70.txt'].decode().splitlines():
        tokens = line.split()
        if len(tokens) == 82:
            try:
                alpha = float(tokens[71])
            except ValueError:
                continue
            if alpha in (0., 1.):
                assert float(tokens[69]) == 240.
                rows.append(tokens)
    assert len(rows) == 2
    columns = {'alpha': 71, 'Lift': 75, 'Drag': 76, 'CL': 77, 'CD': 78, 'CDi': 79, 'CM': 80, 'span_eff': 81}
    table = ','.join(columns) + '\n'
    table += ''.join(','.join(tokens[i] for i in columns.values()) + '\n' for tokens in rows)
    files['archived-targets.csv'] = table.encode()
    files['README.md'] = README.encode()
    files['prepare-used.py'] = Path(__file__).read_bytes()
    manifest = dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
        revision=REVISION, native_run_performed=False, primary_passes_added=0,
        source_pins=pins, files={name: dict(sha256=sha(data), bytes=len(data)) for name, data in files.items()},
        conditions=dict(requested_speed_mps=240, requested_alpha_deg=[0, 1],
            native_mesh='capture; unknown', native_PG='capture; unknown',
            native_frozen_influence='capture; unknown'),
        variants=dict(original='unchanged source', joint_only='one Joint multiplier row',
            report_minus4='Joint row plus four twist values; documented alternative, not authenticated generating input'))
    out.mkdir(parents=True)
    for name, data in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = shutil.make_archive(str(out), 'zip', out.parent, out.name)
    print(json.dumps(dict(directory=str(out), archive=archive, files=len(files),
        archive_sha256=sha(Path(archive).read_bytes()), native_runs=0)))


README = """# SA-11 native capture — prepared, not run

Purpose: distinguish original input interpretation, span sampling, startup
settings and root-flow treatment at 240 m/s and alpha 0/1 degrees. No native
ASWING executable or new native results are supplied. The original archive
is pinned to ISAE revision f62943df20e9e4d7d9f50e070477b22426b5f865.

## Three separate inputs

- original/: byte-identical archived input, including the questionable Joint
  multiplier row and +4 degree upper-winglet twist. Preserve import failures.
- joint-only/: only that multiplier row becomes 0.1 0.1; no geometry changes.
- report-minus4/: Joint correction and four upper-winglet twist values -4
  instead of +4, following Jan Part I Appendix D pp65-68 Fig40. This is a
  disclosed alternative, not a claim about the historical generating input.

source/ retains the exact archived input, full driver and output. Each change
has a unified diff. archived-targets.csv preserves printed tokens for 0/1
degrees; these are archived targets, not results from this package.

## Capture procedure (requires licensed native ASWING)

1. Record executable SHA-256, startup banner/version, compiler/build dimensions
   when available, and whether this is original or ISAE-modified ASWING.
2. Copy one variant into a new empty working directory. Record its hash and
   confirm there is no wingtip_up.set/.pnt/.con. Start a fresh native process
   with argument wingtip_up. Log the complete terminal session including
   startup warnings and integrated geometry/normalization. Never reuse another
   variant's settings. Fresh defaults do not establish historical defaults.
3. Before changing settings, capture NODE counts/distributions, circulation
   variable counts and all OPER settings, especially K/F, global Mach/PG,
   constraints, stiffness, core and stall controls. Record coordinates of
   computed nodes, not just the input geometry stations.
4. Step through commands.proposed.txt while checking each prompt. This is an
   UNVERIFIED reduced version of the original driver, not an automatic shell
   script: only 0/1-degree requests remain and the output filename changes.
   The inherited kk/mm tokens must be interpreted using the actual displayed
   menus. Capture the settings before/after them. Stop on an unexpected prompt,
   import failure, nonconvergence or loss of progress, and retain the transcript.
   Do not run source/*.sh: it contains the original executable path and full
   41-angle sweep. A two-angle run need not reproduce full-stack iteration.
5. After each converged point, capture node xyz and section chord/cl/cm/f_aero
   through documented V/D output, with D interpolation increments zero. Save
   all beams. Derived section values belong to interval midpoints although
   they are printed beside the preceding node; retain this distinction.
6. If the licensed build exposes circulation, force/control-point coordinates,
   section-relative velocity or local Mach, capture those directly and state
   how they were obtained. They are not guaranteed standard menu exports.
   Do not infer induced velocity from state ux/uy/uz or from cl alone.
7. Save the native polar, terminal log, actual entered commands, and native
   SSAV/PSAV sidecars. Preserve files from failures too. Native .set/.pnt are
   build-dependent memory dumps; keep executable identity with them and never
   fabricate them. Use separate directories/processes for the other variants,
   running serially with one BLAS thread.

## Decision evidence

- Input rejected: keep the exact message; do not silently repair original/.
- Native valid but OpenSwing root Mach >1 on matched settings: compare actual
  receiver/source positions, circulation and section-velocity/moment rules.
- Native also fails: record the version/settings; this alone does not refute
  the archived result or identify its historical setup.
- Native aggregate coefficients agree: still check local quantities and input
  identity before declaring the whole case validated.

References: Drela user documentation, 'Saving/recalling Settings, Operating
Points', 'Displayed Variables - V, D', 'Discrete Variable location'; Jan Part I
Table2 p23 and AppendixD pp65-68; MIT ASWING FAQ for sidecar compatibility.
No guard relaxation, core tuning, strip removal or fitted input is proposed.
"""


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    prepare(parser.parse_args().out.resolve())
