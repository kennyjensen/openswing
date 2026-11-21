"""SA-6 primary tables, read as data; never execute upstream MATLAB/shell files."""
from pathlib import Path
import hashlib, json, re, zipfile
import xml.etree.ElementTree as ET
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
REVISION='f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE=ROOT/'.reference/isae-validation'/REVISION
FOLDER=next(CACHE.glob('1 - Aerodynamics/SA*/SA - 6 - *'))
PRIMARY=ROOT/'.reference/isae-sa6'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
IDS=['20b_15c','20b_20c','20b_30c','20b_35c','10b_25c','15b_25c','20b_25c']
# Manually transcribed from scanned primary tables, with zero row appended below.
# Each line: 11 roll entries (delta=4:4:44), then 11 ORIGINAL tail-normalized yaw entries.
TABLES={
0:'''205 408 554 703 835 885 995 1098 1184 1271 1340 / -48 -92 -132 -165 -192 -214 -235 -255 -271 -286 -301
270 492 672 840 975 1050 1157 1249 1340 1419 1494 / -64 -111 -165 -208 -235 -254 -267 -283 -290 -302 -310
345 620 870 1083 1272 1385 1490 1576 1670 1745 1806 / -65 -133 -206 -263 -302 -310 -317 -318 -316 -308 -296
379 686 952 1211 1420 1520 1595 1671 1745 1853 1956 / -68 -135 -213 -285 -317 -330 -336 -331 -337 -317 -288
158 303 430 550 676 710 765 816 857 897 930 / -35 -72 -113 -145 -175 -193 -209 -220 -224 -231 -230
225 440 645 845 975 1032 1086 1142 1200 1251 1306 / -41 -90 -144 -187 -212 -227 -242 -254 -270 -269 -260
275 530 765 980 1125 1205 1315 1408 1502 1583 1655 / -55 -118 -161 -215 -250 -270 -282 -294 -299 -306 -310''',
8:'''148 292 430 570 621 668 728 788 842 895 947 / -63 -115 -153 -182 -215 -245 -278 -302 -316 -327 -325
167 330 488 643 738 775 837 890 942 982 1020 / -73 -136 -180 -206 -227 -250 -271 -287 -306 -322 -337
245 465 666 855 1020 1160 1250 1281 1300 1340 1372 / -88 -163 -213 -252 -269 -287 -306 -320 -325 -325 -320
253 475 686 890 1081 1275 1315 1339 1394 1440 1480 / -82 -155 -215 -268 -318 -324 -336 -345 -341 -269 -285
124 241 358 465 568 661 680 690 736 764 766 / -53 -102 -145 -174 -195 -208 -220 -225 -228 -230 -228
180 345 492 625 750 850 881 915 965 1020 1080 / -59 -112 -160 -205 -247 -274 -295 -302 -297 -289 -263
212 400 568 723 852 973 1007 1032 1095 1145 1186 / -77 -155 -225 -275 -311 -333 -349 -356 -351 -340 -318''',
12:'''95 195 295 420 455 460 463 468 476 485 509 / -81 -147 -213 -270 -320 -370 -410 -445 -468 -490 -510
115 217 308 394 478 508 527 550 580 616 673 / -90 -175 -240 -290 -330 -365 -390 -410 -425 -433 -435
147 270 388 502 625 752 790 822 883 942 1011 / -117 -212 -294 -362 -410 -422 -420 -430 -457 -515 -665
126 232 335 480 636 760 843 904 893 942 990 / -145 -260 -350 -430 -485 -500 -500 -510 -545 -600 -700
83 161 234 300 370 430 440 445 460 474 485 / -65 -120 -155 -145 -226 -245 -258 -260 -260 -265 -273
117 235 326 401 458 525 528 540 565 583 595 / -95 -178 -247 -295 -325 -350 -366 -379 -384 -375 -370
125 236 340 427 504 571 582 597 621 648 683 / -100 -187 -260 -320 -375 -418 -437 -437 -447 -468 -497'''}


def primary_tables():
    out=[]
    for alpha,table in TABLES.items():
        for ident,line in zip(IDS,table.splitlines(),strict=True):
            roll,yaw=[np.r_[0,np.array([int(s) for s in part.split()])*1e-4] for part in line.split('/')]
            assert len(roll)==len(yaw)==12
            report=298 if alpha==0 else 343
            out.append(dict(id=ident,body_alpha=alpha,wing_incidence=alpha+4,report=report,
                pdf_page=20 if alpha==0 else (23 if alpha==8 else 29),
                printed_page=18 if alpha==0 else (21 if alpha==8 else 27),
                table=('V' if ident in IDS[:4] else 'VI') if alpha!=12 else ('XIII' if ident in IDS[:4] else 'XIV'),
                delta=list(range(0,45,4)),Cl_body=roll.tolist(),CN_tail_body=yaw.tolist(),Cn_body=(yaw*25/60).tolist()))
    return out


def number(raw):
    s=re.sub(r'\s+','',raw)
    return float(s) if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?',s) else None


def ods(path):
    ns={'t':'urn:oasis:names:tc:opendocument:xmlns:table:1.0','o':'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
        'x':'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
    with zipfile.ZipFile(path) as z:root=ET.fromstring(z.read('content.xml'))
    sheets=[]
    for table in root.findall('.//t:table',ns):
        rows=[]
        for row in table.findall('t:table-row',ns):
            cells=[]
            for c in row:
                raw=' '.join(''.join(p.itertext()) for p in c.findall('x:p',ns))
                if not raw and not cells:continue
                cell=dict(raw=raw,value=number(raw),stored_value=c.get('{'+ns['o']+'}value'),formula=c.get('{'+ns['t']+'}formula'))
                repeat=int(c.get('{'+ns['t']+'}number-columns-repeated','1'))
                if not raw and repeat>50:break
                assert repeat<1000
                cells.extend([cell.copy() for _ in range(repeat)])
            if any(c['raw'] for c in cells):rows.append(cells)
        sheets.append(dict(name=table.get('{'+ns['t']+'}name'),rows=rows))
    return sheets


def matlab(path):
    text=path.read_text();out={}
    for name,block in re.findall(r'(Clark_Y_Steady_\w+)\s*=\s*\[([^\]]+)\]',text):
        rows=[[number(t) for t in line.split()] for line in block.strip().splitlines() if line.strip()]
        assert len(rows)==12 and len(set(map(len,rows)))==1 and all(v is not None for r in rows for v in r)
        out[name]=rows
    assert len(out)==2
    return out


def fmat(path):
    text=path.read_text();assert 'Normalized forces in: Stability axes, x fwd, z down' in text
    vals={name:float(re.search(r'\b'+name+r'\s*=\s*([-+0-9.Ee]+)',text).group(1)) for name in ['CX','CY','CL','Cl','Cm','Cn','CXdF1','CLdF1','CldF1','CmdF1','CndF1']}
    alpha=float(re.search(r'\balpha =\s*([-+0-9.Ee]+)',text).group(1));assert alpha==12
    return dict(path=path.relative_to(CACHE).as_posix(),sha256=sha(path),id=re.search(r'Straight_Wing_(\d+b_\d+c)',path.name).group(1),
        delta=4*int(path.suffix.split('_')[-1]),body_alpha=alpha,mach=float(re.search(r'Mach =\s*([-+0-9.Ee]+)',text).group(1)),coefficients=vals)


def audit():
    from openswing.asw import parse_asw
    manifest=json.loads((CACHE.parent/'manifest.json').read_text());sources={}
    for p in FOLDER.rglob('*'):
        if p.is_file():
            name=p.relative_to(CACHE).as_posix();pin=manifest['files'][name];assert sha(p)==pin['sha256'];sources[name]=pin
    models=[]
    for p in sorted(FOLDER.rglob('*.asw')):
        m=parse_asw(p.read_text());b=m.beams[0]
        models.append(dict(path=p.relative_to(CACHE).as_posix(),sha256=sha(p),id=p.stem.removeprefix('Straight_Wing_'),
            right_dCLdF1=float(b.value('dCLdF1',.7)),physical_delta_to_F1=-float(np.sign(b.value('dCLdF1',.7))),
            control_stations=b.distributions['dCLdF1'].t.tolist(),control_values=b.distributions['dCLdF1'].values.tolist(),reference=m.reference.tolist()))
    primary_manifest=json.loads((PRIMARY/'primary-manifest.json').read_text())
    for row in primary_manifest:assert sha(PRIMARY/f"naca-tr-{row['report']}.pdf")==row['sha256']
    result=dict(status='SOURCE_CONFLICTS_RETAINED_PRIMARY_TABLES_SEPARATELY_TRANSCRIBED',revision=REVISION,
        script_sha256=sha(Path(__file__)),sources=sources,primary_manifest=primary_manifest,primary=primary_tables(),models=models,
        matlab={p.name:matlab(p) for p in FOLDER.glob('Post_Treatment_*.m')},ods={p.name:ods(p) for p in FOLDER.glob('*.ods')},
        csv={p.name:p.read_text() for p in FOLDER.glob('*.csv')},fmat=[fmat(p) for p in sorted(FOLDER.rglob('*.fmat_*'))],
        conventions=dict(experiment_axes='body x forward, z down',archive_axes='stability x forward, z down',
            primary_roll='L/(q S b)',primary_yaw='N/(q S f)',span_in=60,tail_reference_in=25,CN_tail_to_Cn_span=25/60,
            positive_delta='Right aileron up, left down',table_values='Fairings through observations at three speeds; not individual raw observations',
            uncertainty='No coefficient uncertainty inferred from the tunnel speed-uniformity statement.'),
        findings=[
            '10b_25c control table has cutoffs +/-0.381 m, identical to 15b_25c: it defines 15-inch ailerons. A separate reconstruction changes only these knots to +/-0.508 m.',
            'Span-file F1 signs are opposite chord-file signs; physical right-up/left-down delta maps to -F1 for span files and +F1 for chord files.',
            'TR298 Table VI confirms 10-inch roll coefficients .0816 at 32 degrees and .0897 at 40 degrees. CSV has .016/.097. Additional MATLAB table truncations are retained.',
            'Post-stall MATLAB span measurements come from TR343 Table VI (body pitch 8 degrees, wing incidence 12), while chord measurements come from Table XIII (body pitch 12, wing incidence 16).',
            'Post-stall 20-inch span MATLAB yaw entries repeat the level-flight series instead of TR343 Table VI. Primary tables are compared separately.',
            'Primary yaw normalizes on f=25 inches; ASWING uses b=60 inches. Primary body moments and archived stability moments must not be compared without conversion.',
            'ISAE scripts plot the mixed conventions directly. Chord model 15c uses .040 instead of report .039; 35c uses .071 instead of the report table .71. Literal model values are retained.',
            'The Post_Stall_15c.sh script actually launches 35c. Archived fmat index-to-control mapping uses the 4-degree sweep and is cross-checked against MATLAB tables; mesh and frozen/current startup state are unrecorded.',
            'Primary apparatus includes a fuselage; literal ASW models are wing-only. No parameters are fitted to these measurements.' ])
    (ROOT/'docs/validation/isae-sa6-sources.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    import sys
    sys.path.insert(0,str(ROOT));r=audit();print('audited',len(r['models']),'models',len(r['fmat']),'fmat outputs',len(r['primary']),'primary series')
