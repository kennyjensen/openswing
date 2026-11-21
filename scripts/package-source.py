"""Build source; opt in explicitly to the large raw-validation download."""
import argparse
import json
from pathlib import Path
from distribution import checksum, description, package

NOTES = '''Optional OpenSwing raw validation archives

The source and local-app downloads include code, tests, examples, documentation
and validation summaries. Large raw experiment ZIPs are distributed separately
as openswing-validation.zip only in builds made with npm run build:validation.
When available, download it from Validation & scope in the same hosted build
that supplied the source. Extract it beside the source ZIP so its
openswing/docs/validation files merge into the existing source directory.

docs/validation/archive-index.json lists the recorded paths, byte sizes and
SHA-256 checksums. A normal build does not read or package the raw archives.
An opted-in build includes only archives actually present in that checkout.
Missing catalog entries remain recorded. To reproduce a study requiring an
archive, obtain that archive first and follow its own README and source pins.
Numerical regression tests and application builds do not require the raw bundle.
'''


def build_source(*, include_validation=False):
    validation = Path('docs/validation')
    catalog_path = validation / 'archive-index.json'
    catalog = dict(format='openswing-validation-archives', version=1, archives={})
    if catalog_path.exists():
        catalog = json.loads(catalog_path.read_text())
        if catalog.get('format') != 'openswing-validation-archives' or catalog.get('version') != 1:
            raise SystemExit('Unsupported validation archive catalog.')
    # Hashing these inputs alone can read many gigabytes. It is unnecessary
    # for the application and source downloads, which retain the last catalog.
    raw = sorted(p for p in validation.rglob('*.zip') if p.is_file()) if include_validation else []
    for path in raw:
        catalog['archives'][path.as_posix()] = dict(bytes=path.stat().st_size, sha256=checksum(path))
    validation.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog, sort_keys=True, indent=2) + '\n')
    raw_destination = Path('public/openswing-validation.zip')
    raw_description = None
    if raw:
        package(raw_destination, [('openswing/' + p.as_posix(), p) for p in raw] +
                [('openswing/' + catalog_path.as_posix(), catalog_path)],
                {'openswing/VALIDATION-ARCHIVES.txt': NOTES.encode()})
        raw_description = dict(description(raw_destination), archives=len(raw), catalog_archives=len(catalog['archives']))
        print(f'Packaged {len(raw)} optional raw validation archives ({raw_destination.stat().st_size/1048576:.1f} MiB)')
    else:
        # Vite copies public into dist. Remove only the generated download so a
        # normal build cannot silently copy an earlier multi-gigabyte bundle.
        # All original docs/validation archives and their catalog remain intact.
        raw_destination.unlink(missing_ok=True)
        if not include_validation:
            print('Skipped optional raw validation bundle (use npm run build:validation to include it).')

    roots = ["openswing", "web", "tests", "examples", "scripts", "docs",
             "third_party/machupx", "third_party/vortex_step_method",
             "public/licenses", "public/fonts", ".github"]
    files = [Path(p) for p in ["README.md", "LICENSE", "THIRD_PARTY.md", "package.json", "package-lock.json", "pyproject.toml", "index.html", "vite.config.js", "playwright.config.js", ".gitignore"] if Path(p).is_file()]
    # Include branding/domain assets needed to rebuild a source download,
    # without recursively packing generated runtime files or download ZIPs.
    files += [p for p in Path('public').iterdir() if p.is_file() and
              (p.suffix in {'.svg', '.png', '.ico', '.webmanifest'} or p.name in {'CNAME', '.nojekyll'})]
    for root in roots:
        files += [p for p in Path(root).rglob("*") if p.is_file() and "__pycache__" not in p.parts
                  and '.pytest_cache' not in p.parts and '.source-data' not in p.parts
                  and not (p.suffix == '.zip' and validation in p.parents)]
    source = Path('public/openswing-source.zip')
    package(source, [('openswing/' + p.as_posix(), p) for p in files],
            {'openswing/VALIDATION-ARCHIVES.txt': NOTES.encode()})
    metadata = dict(format='openswing-distribution', version=1, kind='hosted',
                    source=description(source), validation=raw_description)
    Path('public/distribution.json').write_text(json.dumps(metadata, sort_keys=True, indent=2) + '\n')
    print(f'Packaged {len(files)} source files ({source.stat().st_size/1048576:.1f} MiB)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-validation', action='store_true',
                        help='Read, hash and package the optional raw validation archives (potentially many GB).')
    build_source(include_validation=parser.parse_args().include_validation)
