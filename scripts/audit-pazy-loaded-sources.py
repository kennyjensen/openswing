"""Resolve primary Pazy mass/inertia conventions against original Nastran output."""
import json
import re
import sys
from pathlib import Path
import numpy as np
from pazy_primary_conm2 import ROOT,CACHE,source,model,sha
from pazy_primary_reference import skew,modes
from pazy_loaded import datasets,GRAVITY,MIDCHORD_OFFSET,payload,configuration
sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.inertia import point_tensor


def rigid_mass(data,inertia,origin):
    matrix=np.zeros((6,6))
    for mass,position,offset,j in zip(data['mass'],data['coordinates'],data['offset'],inertia):
        motion=np.eye(6);motion[:3,3:]=-skew(origin+position+offset)
        local=np.zeros((6,6));local[:3,:3]=mass*np.eye(3);local[3:,3:]=j
        matrix+=motion.T@local@motion
    return matrix


def main():
    manifest=json.loads((CACHE.parent/'manifest.json').read_text())
    for path,pin in manifest['files'].items():assert sha(CACHE/path)==pin['sha256'],path
    records=[];models={};pins={};origin=np.array([.043589,.00215,0.])
    for skin in [0,1]:
        data=source(skin);name='skin' if skin else 'noskin'
        folder='03_2023_JA_Riso_Cesnik/01_Modal_Undeformed/01_GFEM_FlexibleTip'
        f06=CACHE/folder/f'sol103_{name}.f06';bdf=CACHE/folder/f'fem_{name}.bdf'
        block=f06.read_text().split('G R I D   P O I N T   W E I G H T   G E N E R A T O R',1)[1]
        tokens=[line.split('*')[1].split() for line in block.splitlines() if '*' in line][:6]
        expected=np.array(tokens,dtype=float);assert expected.shape==(6,6)
        corrected=rigid_mass(data,data['inertia'],origin)
        historical=rigid_mass(data,data['conm2_products'],origin)
        bounds=np.array([[.5*10.**(int(v.split('E')[1])-6) for v in row] for row in tokens])
        # Original output has seven significant digits. Allow the much smaller
        # rounding of the independently tabulated equivalent point properties.
        bounds=np.maximum(bounds,5e-11)
        assert np.max(abs(corrected-expected)/bounds)<1.01
        assert np.max(abs(historical-expected)/bounds)>100
        extra=[]
        for line in bdf.read_text().splitlines():
            if line.startswith('CONM2 '):
                values=[line[i:i+8].strip() for i in range(0,80,8)]
                extra.append(dict(element=int(values[1]),grid=int(values[2]),mass_kg=float(values[4])))
        assert [r['mass_kg'] for r in extra]==([.01] if skin==0 else [.015,.0011])
        for p in [f06,bdf]:pins[p.relative_to(CACHE).as_posix()]=sha(p)
        for orientation in ['horizontal','upright']:
            text,_=model(skin,orientation);parsed=parse_asw(text)
            rotation=np.eye(3) if orientation=='horizontal' else np.array([[1.,0,0],[0,0,-1.],[0,1.,0]])
            for i,row in enumerate(parsed.records['weight']):
                assert abs(row[5]/9.81-data['mass'][i])<1e-15
                assert np.max(abs(point_tensor(row,9.81)-rotation@data['inertia'][i]@rotation.T))<1e-18
                assert np.max(abs(row[2:5]-rotation@(data['coordinates'][i]+data['offset'][i])))<1e-15
            path=ROOT/'examples'/f'pazy-primary-conm2-skin{skin}-{orientation}.asw';path.write_text(text)
            models[f'skin{skin}_{orientation}']=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path))
        records.append(dict(skin=skin,nodal_mass_kg=float(data['mass'].sum()),original_conm2_cards=extra,
            original_MO=expected.tolist(),corrected_MO=corrected.tolist(),historical_MO=historical.tolist(),
            printed_rounding_bounds=bounds.tolist(),corrected_max_rounding_units=float(np.max(abs(corrected-expected)/bounds)),
            historical_max_rounding_units=float(np.max(abs(historical-expected)/bounds)),
            corrected_tensor=data['inertia'].tolist(),source_products=data['conm2_products'].tolist(),
            zero_gravity_reference={key:modes(data,projected) for key,projected in [('full',False),('projected',True)]}))
    gravity_path=CACHE/'03_2023_JA_Riso_Cesnik/02_Modal_Gravity/01_GFEM/sol400_noskin_stiftip.dat'
    assert f'GRAV,2001,,{GRAVITY},0.0,0.0,-1.0' in gravity_path.read_text();pins[gravity_path.relative_to(CACHE).as_posix()]=sha(gravity_path)
    grid_path=gravity_path.parent/'reference_axis_grids.bdf';pins[grid_path.relative_to(CACHE).as_posix()]=sha(grid_path)
    first=next(l for l in grid_path.read_text().splitlines() if l.startswith('GRID,'));assert np.array_equal(np.array(first.split(',')[3:6],float),origin)
    for skin in [0,1]:
        for kind in ['bending','torsion']:
            spec=dict(analysis='static',skin=skin,kind=kind,mass_kg=2.,orientation='horizontal',refinement=1,gravity=GRAVITY)
            text,data,_=configuration(spec);p=parse_asw(text);assert len(p.records['weight'])==17
            assert abs(p.records['weight'][-1][5]/9.81-2.)<1e-15
            assert np.max(abs(p.records['weight'][-1][2:5]-data['coordinates'][-1]-payload(skin,kind)))<1e-15
    out=dict(status='PASS_PRIMARY_CONM2_CONVENTION_AND_GRAVITY_LOAD_AUDIT',script_sha256=sha(__file__),
        source_revision=manifest['revision'],source_sha256=pins,all_primary_files_verified=len(manifest['files']),
        records=records,models=models,nominal_chord_m=.1,paper_reference_axis_fraction=.441,
        observer_midchord_offset_m=MIDCHORD_OFFSET,gravity_m_s2=GRAVITY,gfem_origin_translation_m=origin.tolist(),
        static_datasets=datasets(),
        convention_correction=dict(supersedes='pazy-primary-comparison.json',
            issue='Earlier derived models treated spreadsheet off-diagonals as tensor entries. They are signed CONM2 products and must be negated in the tensor.',
            proof='Only the corrected convention reproduces all36 entries of the original Nastran rigid-body MO matrix within its printed precision for both skins.',
            authority='https://help.autodesk.com/cloudhelp/2023/ITA/NSTRN-Reference/files/GUID-6D916DB1-6C7D-4E2D-9ED6-3346C0BAEA79.htm'),
        publication=dict(doi='10.2514/1.C036869',
            load_convention='SectionIV.B: midchord bending load; torsion load0.04m/0.08m behind trailing edge for skin off/on. Remove zero-payload gravity displacement AND twist from sweep comparisons.',
            limitations='SectionIV.A suggests imperfect experimental in-plane clamping and discusses skin-stretch effects absent from constant-stiffness beams. These explanations are not independently proved here.'),
        limitations=['K12 intrinsic extension-torsion is still explicitly projected; this audit does not remove that constitutive limitation.',
            'Static load and observation geometry use the nominal0.1m chord and paper reference-axis fraction. Original UM/NAST load-input coordinates are not provided in this dataset.',
            'Reference-axis nodes are shifted from the GFEM origin. Structural mesh edges and the nominal aerodynamic outline need not coincide; exact experimental fixture geometry remains unresolved.',
            'The six original ISAE out-of-domain attachments are not repaired or validated by these generated inputs.',
            'No added10g/5g calibration mass is appended: primary inertia totals already include the original GFEM concentrated masses. Only requested bench payload is added.'])
    path=ROOT/'docs/validation/pazy-loaded-source-audit.json';path.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(status=out['status'],records=[{k:r[k] for k in ['skin','nodal_mass_kg','corrected_max_rounding_units','historical_max_rounding_units']} for r in records]),indent=2))


if __name__=='__main__':main()
