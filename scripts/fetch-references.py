"""Fetch publicly linked documentation/fixtures, without redistributing them.

Run explicitly for local scientific development and compatibility validation.
"""
from pathlib import Path
from urllib.request import urlopen
import hashlib
import json

base = "https://web.mit.edu/drela/Public/web/aswing/"
names = ["aswing_doc.txt", "version_notes.txt", "asw_theory.pdf", "asw_uns_theory.pdf",
         "ASWING_Extended_User_Manual.pdf", "CG_Calc.pdf", "root_map_fw.pdf", "dae.asw", "usa.asw", "fw.asw"]
root = Path(".reference")
root.mkdir(exist_ok=True)
manifest = {}
urls = {name: base+name for name in names}
urls["us_standard_atmosphere_1976.pdf"] = "https://ntrs.nasa.gov/api/citations/19770009539/downloads/19770009539.pdf"
for name, url in urls.items():
    data = urlopen(url, timeout=60).read()
    (root / name).write_bytes(data)
    manifest[name] = dict(url=url, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    print(f"Fetched {name}: {len(data)} bytes")
(root / "manifest.json").write_text(json.dumps(manifest, indent=2))
