"""Inventory original AE-2 exports without importing or running the solver.

The A15 ``_dist`` filename is not evidence of a span distribution: its bytes
must be checked against the sensor export. Original sources remain immutable.
This audit neither changes comparison scope nor supplies new reference votes.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CASE = '4 - Aeroelasticity/AE - Aeroelastic Cases/AE-2-S Low Aspect Ratio Wing - Steady Deflection'


def pin(path):
    data = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def audit():
    cache = ROOT/'reference/isae-validation'/REVISION
    base = cache/CASE
    manifest_path = ROOT/'reference/isae-validation/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['revision'] == REVISION
    original = {name: item for name, item in manifest['files'].items()
                if name.startswith(CASE+'/')}
    actual = {p.relative_to(cache).as_posix(): p
              for p in base.rglob('*') if p.is_file()}
    assert actual.keys() == original.keys(), 'Original AE-2 inventory changed.'
    sources = []
    for name, path in sorted(actual.items()):
        item = pin(path)
        assert all(item[k] == original[name][k] for k in ('bytes', 'sha256'))
        blob = path.read_bytes()
        assert hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest() == original[name]['git_blob_sha1']
        sources.append(item)

    authoritative = ROOT/'docs/validation/aswing-authoritative-sources.json'
    authority = json.loads(authoritative.read_text())
    references = []
    for item in authority['files']:
        if item['id'] not in ('isae-part-4', 'extended-manual'):
            continue
        for field, digest in [('local_pdf', 'sha256'), ('local_text', 'text_sha256')]:
            checked = pin(ROOT/item[field])
            assert checked['sha256'] == item[digest]
            references.append(checked)
    assert len(references) == 4

    pairs = []
    for driver in sorted(base.rglob('*.sh')):
        lines = driver.read_text().splitlines()
        launch = re.fullmatch(r'.*/aswing (\S+)\s*<<EOF', lines[1])
        assert launch is not None
        token = launch.group(1)
        # Decode shell quoting without executing a command. The uncoupled
        # scripts escape the opening bracket; retain the literal token too.
        stem, = shlex.split(token)
        model = driver.parent/(stem+'.asw')
        assert model.is_file()
        writes = [(i+1, lines[i+1].strip()) for i, line in enumerate(lines)
                  if line.strip().lower() == 'w']
        assert len(writes) == 1
        line, name = writes[0]
        output = driver.parent/name
        beta, = [float(s.split()[1]) for s in lines if s.strip().startswith('!B ')]
        speeds = [float(s.split()[1]) for s in lines if s.strip().startswith('!V ')]
        rows = [s.split() for s in output.read_text().splitlines()[3:] if s.strip()]
        assert len(rows) == len(speeds) and all(len(row) == 6 for row in rows)
        assert all(int(row[0]) == i+1 and float(row[1]) == i+1 for i, row in enumerate(rows))
        assert rows[0][2:] == ['NaN']*4 and speeds[0] == 0
        assert 'RY pos[ 1]' in output.read_text().splitlines()[2]
        assert all('NaN' not in row for row in rows[1:])
        pairs.append(dict(driver=pin(driver), model=pin(model), output=pin(output),
                          literal_launch_token=token, shell_unquoted_stem=stem,
                          write_line_1based=line, beta_deg=beta, speeds=speeds,
                          rows=len(rows), channels=['RY', 'Psi', 'V', 'beta']))
    assert len(pairs) == 12 and sum(p['rows'] for p in pairs) == 275
    assert len({p['output']['sha256'] for p in pairs}) == 12

    steady = base/'Steady_deflection'
    primary = steady/'[m15_02]_S_A15.txt'
    duplicate = steady/'[m15_02]_S_A15_dist.txt'
    assert duplicate.read_bytes() == primary.read_bytes()
    driver = steady/'[m15_02]_s_A15.sh'
    assert driver.read_text().splitlines()[53:55] == ['ww', duplicate.name]
    texts = {p.relative_to(ROOT).as_posix() for p in base.rglob('*.txt')}
    assert texts == {p['output']['path'] for p in pairs} | {pin(duplicate)['path']}
    analysis = steady/'Analysis.m'
    reads = re.findall(r"readtable\('([^']+\.txt)'", analysis.read_text())
    assert set(reads) == {Path(p['output']['path']).name for p in pairs}
    assert len(reads) == 12 and duplicate.name not in analysis.read_text()

    paired_models = {p['model']['path'] for p in pairs}
    extras = [pin(p) for p in sorted(base.rglob('*.asw'))
              if p.relative_to(ROOT).as_posix() not in paired_models]
    assert {Path(p['path']).name for p in extras} == {'[03_90]_flat.asw', '[03_90]_S.asw'}
    assert (base/'[0_3_90]_S/[03_90]_S.asw').read_text().rstrip().endswith('Engine')
    for item in extras:
        item.update(paired_shell_drivers=[], independent_native_reference_established=False)

    return dict(
        status='SOURCE_INVENTORY_CHECK_PASS', observed_utc=datetime.now(timezone.utc).isoformat(),
        auditor=pin(Path(__file__)), revision=REVISION,
        manifest=pin(manifest_path), authority_catalog=pin(authoritative),
        authoritative_files=references, verified_original_files=sources,
        counts=dict(original_files=len(sources), extensions=dict(sorted(Counter(p.suffix.lower() for p in actual.values()).items())),
                    shell_drivers=len(pairs), native_text_files=len(texts),
                    unique_sensor_sweeps=12, original_sensor_records=275,
                    two_mesh_required_values=2200, unavailable_values=96,
                    duplicate_exports=1, additional_models_without_run_pairing=len(extras)),
        sensor_pairs=pairs,
        supplemental=dict(source=pin(duplicate), byte_identical_to=pin(primary),
                          script=pin(driver), command_line_1based=54, command='ww',
                          classification='EXACT_DUPLICATE_SENSOR_SWEEP',
                          distinct_span_values=0, extra_comparison_slots=0),
        plot_script=pin(analysis), native_files_read_by_plot_script=reads,
        extra_models=extras, source_policy='Keep all source bytes; do not count duplicate exports twice.',
        qualifications=[
            'Drela documents WW as a span-distribution export, but the archived file has sensor-sequence content. The exact cause is unknown without the native executable or run transcript.',
            'Part IV section 3.2 and Figure 3 concern tip deflection and twist. Their existing comparisons remain required.',
            'No independent span reference exists in these thirteen text exports. Figures and CSV candidates are not promoted to new native targets by this audit.',
            'Two additional ASW files lack a generating shell-script/output pairing in this directory; one ends with an unterminated Engine block. No input repair or alternate result is substituted.',
            'Shell quoting is decoded without running any driver; source pairing does not recover a historical producing-input checksum or executable build.',
        ], production_imports=0, physics_calls=0, primary_votes_added=0,
        completion_fraction_changed=False, registered_scope_changed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Keep previous source observations immutable.'
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=result['status'], counts=result['counts'],
                          supplemental=result['supplemental']['classification'])))
