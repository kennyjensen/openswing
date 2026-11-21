"""Pin primary ST-3 frequency data without redistributing the thesis PDF."""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,urllib.request,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
REVISION='f62943df20e9e4d7d9f50e070477b22426b5f865'
FOLDER='3 - Structure/CASE - ST3 Low aspect ratio'


def main():
    dest=ROOT/'.reference/isae-st3';dest.mkdir(parents=True,exist_ok=True)
    url='https://dspace.mit.edu/server/api/core/bitstreams/3cdc2180-37e0-4691-95fb-fad8627dbbe9/content'
    pdf=dest/'dunn-1992.pdf'
    if not pdf.exists():
        with urllib.request.urlopen(url,timeout=60) as response:pdf.write_bytes(response.read())
    data=pdf.read_bytes()
    assert hashlib.md5(data).hexdigest()=='e711cca509a0dee318347d6689d3a52c'
    assert hashlib.sha256(data).hexdigest()=='4a2f76f6d51b5562a9a7ab7390c71adea8c792235eb4266bef38205d335d8e0d'
    primary=dict(url=url,publication='https://dspace.mit.edu/entities/publication/55aa429a-7a4a-4908-87e6-7ecc1ece5ae5',
        bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),table=2,printed_page=99,pdf_page=125,
        extraction='Manually transcribed and visually checked against original table; no frequency fitting.',
        order=['1B','1T','2B'],experiment_Hz={'0_3_90':[4.,21.4,27.1],'p15_0':[3.6,22.7,27.1],'m15_0':[3.6,24.5,27.4]},
        author_analysis_Hz={'0_3_90':[4.3,24.6,27.2],'p15_0':[3.9,23.5,28.6],'m15_0':[4.,24.1,27.8]},
        fft_sample_count=2048,fft_sample_interval_s=.005,reported_frequency_resolution_Hz=.1,
        setup_pages=[83,84,96,97],setup='Vertically clamped pluck tests between wind-tunnel runs; no statement of evacuated air. Mode labels are approximate for coupled laminates. Frequency resolution is not a measurement uncertainty bound.')
    name=FOLDER+'/Vaccum_anaysis/Comparaison.xlsx';path=ROOT/'.reference/isae-validation'/REVISION/name
    manifest=json.loads((ROOT/'.reference/isae-validation/manifest.json').read_text())
    digest=hashlib.sha256(path.read_bytes()).hexdigest();assert digest==manifest['files'][name]['sha256']
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(path) as z:
        strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
        cells={}
        for c in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//s:c',ns):
            v=c.find('s:v',ns)
            if v is not None:cells[c.attrib['r']]=strings[int(v.text)] if c.get('t')=='s' else float(v.text)
    def rows(offset):return {key:[cells[f'{col}{row+offset}'] for col in ['C','D','E']] for key,row in [('0_3_90',2),('p15_0',8),('m15_0',14)]}
    upstream=dict(path=name,sha256=digest,order=[cells[k] for k in ['C1','D1','E1']],experiment_Hz=rows(0),aswing_Hz=rows(1),author_analysis_Hz=rows(3),cells=cells)
    report=dict(revision=REVISION,primary=primary,upstream_workbook=upstream,
        conflicts=['ISAE workbook/report label columns 1B,2B,1T but coupled-laminate values follow primary order 1B,1T,2B.',
            'ISAE author-analysis first-bending values4.5/3.6Hz conflict with primary3.9/4.0Hz for positive/negative layups.',
            'ISAE report Table10 and literal files differ in mass, stiffness and reference-axis properties. Literal files are retained.',
            'Archived ASWING mode shapes/settings are absent; scalar table labels do not prove branch correspondence.'],
        full_suite_validated=False)
    (ROOT/'docs/validation/isae-st3-sources.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Primary PDF checksum and upstream workbook verified; mode-label conflicts retained.')


if __name__=='__main__':main()
