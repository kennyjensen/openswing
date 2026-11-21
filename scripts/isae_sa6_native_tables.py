"""Read author-labelled ASWING moments in SA-6's MATLAB/ODS tables.

This source inventory does not execute upstream code or run an aircraft. The
unpaired tables lack native run headers; they are not registered raw-export
comparisons. Experimental columns and synthetic zero rows are never targets.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
VARIANTS = {
    'chord': ('20b_15c', '20b_20c', '20b_30c', '20b_35c'),
    'span': ('10b_25c', '15b_25c', '20b_25c'),
}
NAMESPACE = {
    'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
    'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
    'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def numeric(token):
    require(bool(re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?', token)),
            'Invalid native numeric token: '+repr(token))
    try:
        value = Decimal(token)
    except InvalidOperation as exc:
        raise ValueError('Invalid native decimal.') from exc
    require(value.is_finite(), 'Nonfinite native decimal.')
    return value


def decode_matlab(text, kind):
    """Select ASWING columns using explicit plot and legend associations."""
    require(kind in VARIANTS, 'Unknown table family.')
    array = 'Clark_Y_Steady_' + ('Span' if kind == 'span' else 'chord')
    matches = list(re.finditer(r'^'+array+r'\s*=\s*\[([^\]]+)\]', text, re.M))
    require(len(matches) == 1, 'Expected one MATLAB matrix.')
    match = matches[0]
    rows = []
    for offset, raw in enumerate(match[1].splitlines()):
        if not raw.strip():
            continue
        tokens = raw.strip().split()
        require(len(tokens) == 1+4*len(VARIANTS[kind]), 'Unexpected matrix width.')
        require(tokens[0] == str(4*len(rows)), 'Unexpected control sequence.')
        # Only the control and author-labelled native columns are numeric inputs.
        rows.append(dict(tokens=tokens, line=text.count('\n',0,match.start(1))+1+offset))
    require(len(rows) == 12, 'Expected zero plus eleven control settings.')
    evidence = {}
    figures = (1,2) if kind == 'span' else (3,4)
    fractions = ('b/3','b/2','2b/3') if kind == 'span' else ('0.15c','0.20c','0.3c','0.35c')
    for channel, figure, label in zip(('Cl','Cn'), figures, ('Rolling','Yawing')):
        starts = list(re.finditer(r'^figure\('+str(figure)+r'\)\s*$',text,re.M))
        require(len(starts) == 1, 'Missing or ambiguous source plot.')
        begin = starts[0].end()
        after = re.search(r'^figure\(',text[begin:],re.M)
        section = text[begin:begin+after.start()] if after else text[begin:]
        xlabels = re.findall(r"^xlabel\('([^']+)'\)\s*$",section,re.M)
        ylabels = re.findall(r"^ylabel\('([^']+)'\)\s*$",section,re.M)
        require(len(xlabels)==1 and xlabels[0] in ('Aileron deflection in deg','Aileron delfeciton in deg'),
                'Missing native control units.')
        require(len(ylabels)==1 and ylabels[0].lower()==label.lower()+' moment coefficient',
                'Missing native coefficient label.')
        order = [line for line in section.splitlines() if line.startswith('legend(')]
        require(len(order)==1 and re.findall(r',leg([1-4])[,)]',order[0])==
                [str(i+1) for i in range(len(VARIANTS[kind]))], 'Native legend ordering changed.')
        for i,(variant,fraction,marker) in enumerate(zip(VARIANTS[kind],fractions,'sodv')):
            column = 4+4*i+(channel=='Cn')
            expression = f"plot({array}(1:end,1),{array}(1:end,{column}),'r{marker}','MarkerFaceColor','r',MarkerSize=10)"
            plots = list(re.finditer(r'^'+re.escape(expression)+r'\s*$',section,re.M))
            require(len(plots) == 1, 'Native plot column/marker changed.')
            legends = list(re.finditer(r'^leg'+str(i+1)+r'\s*=.*$',section,re.M))
            require(len(legends) == 1 and 'ASWING' in legends[0].group() and
                    ('= '+fraction+',') in legends[0].group(), 'Native variant legend changed.')
            evidence[(variant,channel)] = dict(column_1based=column,
                plot_line=text.count('\n',0,begin+plots[0].start())+1,
                legend_line=text.count('\n',0,begin+legends[0].start())+1,
                control_label=xlabels[0],coefficient_label=ylabels[0])
    outputs = []
    for i,variant in enumerate(VARIANTS[kind]):
        for row in rows[1:]:
            for channel in ('Cl','Cn'):
                binding = evidence[(variant,channel)]
                token = row['tokens'][binding['column_1based']-1]
                number = numeric(token)
                tolerance = Decimal(5).scaleb(number.as_tuple().exponent-1)
                outputs.append(dict(variant=variant,channel=channel,delta=int(row['tokens'][0]),
                    token=token,exact_decimal=str(number),original_absolute_tolerance=str(tolerance),
                    matlab_line=row['line'],**binding))
    return outputs


def decode_ods(content):
    """Preserve leading/repeated cells and the physical spreadsheet addresses."""
    root = ET.fromstring(content)
    tables = root.findall('.//table:table',NAMESPACE)
    require(len(tables) == 1, 'Expected one ODS sheet.')
    table = tables[0]
    rows = []
    for row in table.findall('table:table-row',NAMESPACE):
        cells = []
        for cell in row:
            text = ' '.join(''.join(p.itertext()) for p in cell.findall('text:p',NAMESPACE))
            repeat = int(cell.get('{'+NAMESPACE['table']+'}number-columns-repeated','1'))
            # Only columns A:Q and rows 1:14 belong to these declared matrices.
            item = dict(text=text,stored=cell.get('{'+NAMESPACE['office']+'}value'),
                        formula=cell.get('{'+NAMESPACE['table']+'}formula'))
            cells.extend([item.copy() for _ in range(min(repeat,17-len(cells)))])
            if len(cells) == 17:
                break
        repeated = int(row.get('{'+NAMESPACE['table']+'}number-rows-repeated','1'))
        rows.extend([cells[:] for _ in range(min(repeated,14-len(rows)))])
        if len(rows) == 14:
            break
    require(len(rows) == 14, 'Missing ODS control rows.')
    return dict(sheet=table.get('{'+NAMESPACE['table']+'}name'),rows=rows)


def catalog(root):
    root = Path(root).resolve()
    cache = root/'.reference/isae-validation'/REVISION
    parent = cache/'1 - Aerodynamics/SA - Steady Aerodynamics Cases'
    folders = list(parent.glob('SA - 6 - *'))
    require(len(folders) == 1, 'Missing/ambiguous original SA-6 archive.')
    folder = folders[0]
    manifest = json.loads((cache.parent/'manifest.json').read_text())
    sources = {}

    def original(path):
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        expected = manifest['files'][path.relative_to(cache).as_posix()]
        require(expected['sha256'] == digest and expected['bytes'] == len(data), 'Original source changed: '+str(path))
        sources[path.relative_to(root).as_posix()] = dict(sha256=digest,bytes=len(data))
        return data

    series, paired = [], 0
    for regime,script in (('Level','Post_Treatment_Level.m'),('Stall','Post_Treatment_Post_Stall.m')):
        mpath = folder/script
        mtext = original(mpath).decode()
        for kind,variants in VARIANTS.items():
            opath = folder/f'ClarkY_{regime}_{kind}_varying.ods'
            original(opath)
            with zipfile.ZipFile(opath) as archive:
                ods = decode_ods(archive.read('content.xml'))
            outputs = decode_matlab(mtext,kind)
            for value in outputs:
                row_index, column = value['delta']//4+3, value['column_1based']
                cell = ods['rows'][row_index-1][column-1]
                require(ods['rows'][1][column-1]['text'] == value['channel']+'_ASW', 'ODS native header changed.')
                require(numeric(ods['rows'][row_index-1][0]['text']) == value['delta'], 'ODS control binding changed.')
                require(not cell['formula'], 'Unreviewed computed native cell.')
                require(numeric(cell['text']) == Decimal(value['exact_decimal']), 'ODS/MATLAB native conflict.')
                if cell['stored'] is not None:
                    require(numeric(cell['stored']) == Decimal(value['exact_decimal']), 'ODS displayed/stored value conflict.')
                value['ods'] = dict(sheet=ods['sheet'],row_1based=row_index,column_1based=column,**cell)
            for variant in variants:
                path = folder/'Simulation'/('chordwise' if kind=='chord' else 'spanwize')/f'Straight_Wing_{variant}.asw'
                original(path)
                selected = [v for v in outputs if v['variant']==variant]
                raw_pairs = []
                if regime=='Stall' and kind=='chord':
                    for value in selected:
                        fpath=path.parent/path.stem/f'{path.stem}.fmat_{value["delta"]//4:03d}'
                        ftext=original(fpath).decode()
                        force=ftext.split('Normalized forces in: Stability axes, x fwd, z down',1)[1].split('Derivatives in:',1)[0]
                        tokens=re.findall(r'\b'+value['channel']+r'\s*=\s*(\S+)',force)
                        require(tokens == [value['token']], 'Native fmat witness does not match exactly.')
                        raw_pairs.append(dict(path=fpath.relative_to(root).as_posix(),channel=value['channel'],delta=value['delta']))
                        paired+=1
                series.append(dict(id=f'SA-6:tabulated:{regime.lower()}:{variant}',regime=regime.lower(),kind=kind,
                    variant=variant,model_path=path.relative_to(root).as_posix(),
                    matlab_path=mpath.relative_to(root).as_posix(),ods_path=opath.relative_to(root).as_posix(),
                    reference_kind='author-labelled ASWING moment table',values=selected,raw_export_witnesses=raw_pairs,
                    raw_export_metadata_available=bool(raw_pairs),synthetic_zero_excluded=True,
                    geometry_conflict='10b deck has 15-inch control spans; no geometry repair applied' if variant=='10b_25c' else None,
                    operating_point={'body_alpha':12,'authority':'paired raw fmat'} if raw_pairs else
                        {'body_alpha':None,'report_wing_incidence':4 if regime=='Level' else 16,
                         'qualification':'Report incidence is not a retained run header. Span post-stall experimental columns came from a different incidence.'},
                    historical_execution_authenticated=False,registered_acceptance=False))
    require(len(series)==14 and sum(len(s['values']) for s in series)==308 and paired==88,'Native inventory count changed.')
    return dict(status='native_tables_catalogued_with_setup_qualifications',revision=REVISION,sources=sources,
        series=series,summary=dict(series=14,native_scalar_references=308,exact_raw_export_witnesses=paired,
            additional_author_tabulated_scalars=308-paired,experimental_targets=0,synthetic_zero_targets=0,
            unregistered=True),new_aircraft_solves=0,goal_complete=False)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    result=catalog(args.root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result['summary'],indent=2))
