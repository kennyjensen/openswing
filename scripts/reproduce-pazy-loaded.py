"""Re-extract evidence and reproduce its deterministic comparison artifacts."""
from pathlib import Path
from zipfile import ZipFile
import argparse
import json
import os
import subprocess
import sys
from distribution import checksum

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args();archive=ROOT/'docs/validation/pazy-loaded-evidence.zip'
    target=args.work/'reproduction';target.mkdir(exist_ok=False)
    with ZipFile(archive) as z:
        manifest=json.loads(z.read('MANIFEST.json'));z.extractall(target)
    for name,pin in manifest['files'].items():
        path=target/name;assert path.stat().st_size==pin['bytes'] and checksum(path)==pin['sha256'],name
    names=['pazy-loaded-comparison.json','pazy-loaded-comparison.md','pazy-loaded-checks.json',
           'pazy-loaded-static-comparison.png','pazy-loaded-static-comparison.svg']
    base=target/'openswing';before={name:checksum(base/'docs/validation'/name) for name in names}
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with (args.work/'reproduction.log').open('w') as output:
        subprocess.run([sys.executable,'scripts/summarize-pazy-loaded.py'],cwd=base,env=env,stdout=output,stderr=subprocess.STDOUT,check=True)
    after={name:checksum(base/'docs/validation'/name) for name in names};assert before==after,(before,after)
    result=dict(status='PASS_ARCHIVE_REEXTRACTION_AND_IDENTICAL_POSTPROCESSING',archive_sha256=checksum(archive),
        verified_members=len(manifest['files']),identical_generated_files=after,script_sha256=checksum(__file__))
    (args.work/'reproduction-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
