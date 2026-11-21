"""Source declarations for ST-4's published mechanical comparison.

Table6 was read from PartIII PDF p48, with positions kept as printed. Original
input mappings are declared before solving. Workbook/CSV conflicts stay separate.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REVISION='f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE=ROOT/'reference/isae-validation'/REVISION
CASE=CACHE/'3 - Structure/CASE - ST4 Concentrated weight'
MODELS=CASE/'Simulation_files'
# id, printed y/b, fb1, fb2, ft. These are ASWING columns, never experiments.
PAPER=[
    ('WING','0','6.6','40.54','48.8'),
    ('7a_b8','.17','6.6','36.5','26.5'),
    ('7a_b11','.23','6.5','34.6','23.2'),
    ('7a_b17','.35','6.2','31.5','19.2'),
    ('7a_b46','.96','3.1','33.3','17'),
    ('7a_b48','1','3.0','31.3','16.8'),
    ('7b_b11','.23','6.5','28','38'),
    ('7b_b21','.44','5.8','21.6','33'),
    ('7c_b11','.23','6.5','27.6','32.9'),
    ('7c_b21','.44','5.8','22.2','28.8'),
    ('7c_b28','.58','5.0','30.4','21.8'),
    ('7d_b11','.23','6.5','29.3','31.9'),
    ('7d_b21','.44','5.8','24.3','26.8'),
    ('7d_b27','.56','5.1','28.6','23.5'),
    ('7d_b33','.69','4.4','39.1','21.4'),
    ('7e_b11','.23','6.5','29.6','31.6'),
    ('7e_b21','.44','5.8','25.6','25.2'),
    ('7e_b29','.60','4.9','30.2','23.1'),
    ('7e_b35','.72','4.2','37.7','21.9'),
    ('7e_b40','.83','3.6','38.5','21.1'),
    ('7f_b11','.23','6.5','33.8','26.7'),
    ('7f_b16','.33','6.3','31.0','22.9'),
    ('7f_b24','.5','5.82','28.3','22.2'),
    ('7f_b40','.83','4.5','34.9','21.5'),
]
LABELS=('fb1','fb2','ft')
QUALIFICATIONS={
    'WING':'Original zero-weight WING.asw is a declared unloaded comparison; the W0.asw named by the root driver is absent, so exact generating-file identity is unproved.',
    '7e_b35':'Paper .72 differs from supplied35in/48in=.72917 beyond nearest rounding. Original35in model is retained; position correspondence remains qualified.',
    '7d_b33':'Paper .69 row combines fb1 like33in with fb2/ft like39in in the CSV. Keep the printed position and all three original targets; do not move individual modes to another model.',
    '7f_b40':'Paper .83 row values resemble the32in workbook row, but .83 denotes40in. Keep the printed position and targets;32in is a separate diagnostic.',
    '7f_b24':'Its workbook triplet repeats the7c_b21 values with fb2/ft exchanged. Preserve the24in original model and all source values.',
}


def classify(torsion_fractions):
    """Label the first three positive modes using elastic strain energy only."""
    assert len(torsion_fractions)==3
    order=sorted(range(3),key=lambda i:torsion_fractions[i],reverse=True)
    torsion=order[0];bending=[i for i in range(3) if i!=torsion]
    valid=torsion_fractions[torsion]>.5+1e-6 and all(torsion_fractions[i]<.5-1e-6 for i in bending)
    return dict(valid=valid,indices=dict(fb1=bending[0],fb2=bending[1],ft=torsion),
        torsion_fractions=torsion_fractions,
        scope='First three positive roots in the declared local16-root search; labels use strain energy, never nearest target frequency.')
