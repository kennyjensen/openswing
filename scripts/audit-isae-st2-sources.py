"""Pin Pazy source files and expose setup conflicts before comparison."""
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import json
import numpy as np
from isae_st2 import ROOT, CACHE, FOLDER, sha, measurements
from openswing.asw import parse_asw
from openswing.network import StaticNetwork

PRIMARY_REVISION = '396710a19a80004c65c767e9955fe60d59565c39'
PRIMARY = ROOT/'.reference/pazy-primary'/PRIMARY_REVISION


def cells(path):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    out={}
    with ZipFile(path) as z:
        strings=[''.join(t.itertext()) for t in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)] if 'xl/sharedStrings.xml' in z.namelist() else []
        for name in z.namelist():
            if not (name.startswith('xl/worksheets/sheet') and name.endswith('.xml')):continue
            sheet={}
            for c in ET.fromstring(z.read(name)).findall('.//s:c',ns):
                value=c.find('s:v',ns)
                if value is not None:
                    if c.get('t') == 's':
                        parsed = strings[int(value.text)]
                    elif c.get('t') in ('e', 'str'):
                        parsed = value.text  # Preserve upstream spreadsheet errors.
                    else:
                        parsed = float(value.text)
                    sheet[c.get('r')] = parsed
            out[name]=sheet
    return out


def main():
    manifest=json.loads((CACHE.parent/'manifest.json').read_text())
    primary=json.loads((PRIMARY.parent/'manifest.json').read_text())
    assert primary['revision']==PRIMARY_REVISION
    source={k:v for k,v in manifest['files'].items() if k.startswith(FOLDER+'/')}
    for k,pin in source.items():assert sha(CACHE/k)==pin['sha256']
    for k,pin in primary['files'].items():assert sha(PRIMARY/k)==pin['sha256']
    rows=[]
    for name in source:
        if not name.endswith('.asw'):continue
        text=(CACHE/name).read_text();model=parse_asw(text);beam=model.beams[0]
        r=dict(path=name,sha256=sha(CACHE/name),unchanged_roundtrip=model.dumps()==text,
            domain=list(beam.domain),weights=[v.tolist() for v in model.records.get('weight',[])],
            fields={key:beam.value(key,[.1,.3,.53,.55]).tolist() for key in ['mg','mgcc','mgnn','EIcc','GJ','EInn','EIcn','Cea','Cta','Ccg']})
        try:StaticNetwork(model,8,None,[0.,0.,-9.81],[],allow_signed_point_weights=True)
        except (ValueError,RuntimeError) as e:r.update(construction='rejected',error=type(e).__name__+': '+str(e))
        else:r['construction']='constructed'
        assert r['construction']=='rejected' and 'Attachment station' in r['error']
        rows.append(r)
    correspondence=[]
    for name,pin in source.items():
        rel=Path(name).relative_to(FOLDER).as_posix();key='03_2023_JA_Riso_Cesnik/'+rel
        if key in primary['files']:
            correspondence.append(dict(isae=name,primary=key,identical=pin['sha256']==primary['files'][key]['sha256']))
    workbooks={}
    for path in sorted((CACHE/FOLDER).rglob('*.xlsx')):
        workbooks[path.relative_to(CACHE).as_posix()]=cells(path)
    modal=workbooks[FOLDER+'/01_Modal_Undeformed/00_Comparisons/GFEM_vs_Beam_VS_ASWING.xlsx']['xl/worksheets/sheet1.xml']
    assert modal['A9']=='With skin'
    expected=dict(OOP1=4.26,OOP2=28.5,T1=42.,IP1=60.7,OOP3=81.5)
    assert {modal[f'B{i}']:modal[f'C{i}'] for i in range(11,16)}==expected
    archival={modal[f'B{i}']:modal[f'I{i}'] for i in range(11,16)}
    # Match types, not row positions: primary IP1 and OOP3 appear in a different
    # order in the GVT and numerical columns of this same workbook.
    primary_um={modal[f'D{i}']:modal[f'G{i}'] for i in range(11,16)}
    mass_totals={}
    for skin in [0,1]:
        name=f'00_Models/01_Pazy_Technion/02_Models_Beam/02_Inertia_Distributions/inertia_skin{skin}.xlsx'
        sheet=cells(PRIMARY/name)['xl/worksheets/sheet1.xml']
        mass_totals[str(skin)]=sum(v for k,v in sheet.items() if k.startswith('B') and k!='B1')
    primary_refs=dict(
        experiment=dict(doi='10.2514/1.J060621',url='https://www.researchgate.net/profile/Ariel-Drachinsky/publication/357596316_Experimental_Aeroelastic_Benchmark_of_a_Very_Flexible_Wing/links/61e12588c5e31033759184f7/Experimental-Aeroelastic-Benchmark-of-a-Very-Flexible-Wing.pdf',
            details='Tables 3 and 4: skin-on upright/horizontal GVT. Table 5: separate skin-off horizontal GVT. Static experimental data were used in model adaptation.'),
        beam=dict(doi='10.2514/1.C036869',url='https://www.researchgate.net/profile/Cristina-Riso/publication/366714346_Impact_of_Low-Order_Modeling_on_Aeroelastic_Predictions_for_Very_Flexible_Wings/links/63b33896c3c99660ebc28c0c/Impact-of-Low-Order-Modeling-on-Aeroelastic-Predictions-for-Very-Flexible-Wings.pdf',
            details='Author preprint, section IV.B: bending masses at tip midchord, torsion masses 0.04 m behind trailing edge without skin and 0.08 m behind trailing edge with skin. Projected chord twist and midchord displacement are compared.'),
        coordinate_caveat='ASWING x is aft-positive and Xax=.5 places the reference line at midchord. Positive x=0.09/0.13 is aft of trailing edge; archived negative x is forward of leading edge.')
    out=dict(status='PASS_SOURCE_INTEGRITY_WITH_EXPLICIT_SETUP_CONFLICTS',modules={p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))},
        script_sha256=sha(__file__),upstream_revision=manifest['revision'],sources=source,primary=primary,literal_models=rows,
        correspondence=correspondence,workbooks=workbooks,primary_references=primary_refs,
        measured_modal_Hz=dict(skin1_upright=expected,skin1_horizontal_strain_PSD=dict(OOP1=4.39,OOP2=29.8,T1=41.,OOP3=82.5),
            skin0_horizontal_strain_PSD=dict(OOP1=4.2,OOP2=29.2,T1=40.)),
        archived_modal_Hz=dict(upright=archival,horizontal=dict(OOP1=4.67,OOP2=29.2,T1=43.2,IP1=116.,OOP3=81.4)),
        primary_um_skin1_upright_Hz=primary_um,primary_mass_kg=mass_totals,
        asw_distributed_mass_kg=dict(static=.3745*.55,modal=.6787*.55),
        experimental_datasets=[{k:v for k,v in r.items() if k!='requests'} for r in measurements()],
        conflicts=['All six literal models have t=.558 weights outside the t=.55 beam endpoint.',
            'ISAE report Table 4 caption calls the measurements skin-off; the source workbook and primary experimental Tables 3/4 identify skin-on.',
            'ISAE report Table 4 interchanges primary UM/NAST IP1 and OOP3 values when transferring rows with different mode orders.',
            'ISAE description says forward of leading edge; primary static load positions are behind trailing edge. Archived MATLAB changes x to -0.09/-0.13.',
            'Archived bending x=0.05 is offset from the midchord reference line x=0.',
            'Static and modal files have different uniform mass per length; neither reproduces the full primary inertia distribution.',
            'The plotting script removes the zero-load vertical displacement and negates local ASWING twist. Those operations do not recover the primary signed projected chord angle.',
            'The same simplified static material properties are used for both skin conditions; no fit is performed here.'])
    dest=ROOT/'docs/validation/isae-st2-source-audit.json';dest.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(status=out['status'],isae_files=len(source),primary_files=len(primary['files']),identical_primary_files=sum(r['identical'] for r in correspondence),literal_rejections=len(rows),primary_mass_kg=mass_totals),indent=2))


if __name__=='__main__':main()
