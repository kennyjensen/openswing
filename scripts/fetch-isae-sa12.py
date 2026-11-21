"""Fetch and verify the two public NACA reports used by the SA-12 audit."""
from pathlib import Path
import hashlib, urllib.request

ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'.reference/isae-sa12'
SOURCES=[
    ('naca-tn-705.pdf','19930081443','e93b43f67058556a7e732c319a134128d5e40ba5e218b15b3a7d695e8ccd65ac'),
    ('naca-tr-664.pdf','19930091739','b34a8ed7e710b9baaa4c3bd0a138ba025cbb5b411cc095bde8ad6c68560139f6')]

if __name__=='__main__':
    DEST.mkdir(parents=True,exist_ok=True)
    for name,identifier,expected in SOURCES:
        path=DEST/name
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
        else:
            data=urllib.request.urlopen(f'https://ntrs.nasa.gov/api/citations/{identifier}/downloads/{identifier}.pdf',timeout=60).read()
            temporary=path.with_suffix('.download');temporary.write_bytes(data)
            assert hashlib.sha256(data).hexdigest()==expected,'Changed download retained for review; original pin not replaced.'
            temporary.replace(path)
        print('Verified',name,expected,flush=True)
