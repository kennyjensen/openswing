"""Validated edited-model ASW serialization and beam-distribution operations.

Unchanged models retain their exact source. Property edits update local source
tables in place; explicit canonical export normalizes the whole document.
"""
import hashlib
import json
import re
import numpy as np
from .asw import AswError,Distribution,SCHEMAS,DEFAULTS,RIGID,canonical,parse_asw,weight_station
from .beam_spline import NATURAL


KNOWN=set(SCHEMAS)|{'name','unit','beam','jangle'}
COMMENTS_HEADER='! Comments retained from original source; positions may have changed.'


def unknown_blocks(model):
    lines=(model._parsed_source if model._parsed_source is not None else model.source).splitlines(keepends=True)
    return [''.join(lines[b.line-1:b.end_line]) for b in model.blocks if b.kind not in KNOWN]


def model_data(model):
    def rows(values):
        return np.asarray(values,dtype=float).tolist()
    result = dict(name=model.name,units=model.units.declarations,constants=rows(model.constants),reference=rows(model.reference),
        beams=[dict(index=b.index,physical_index=b.physical_index,name=b.name,
            distributions={k:dict(name=d.name,t=rows(d.t),values=rows(d.values)) for k,d in b.distributions.items()}) for b in model.beams],
        records={k:[dict(header=rows(v['header']),curve=rows(v['curve'])) if k=='jangle' else rows(v) for v in values]
            for k,values in model.records.items() if values},unknown_blocks=unknown_blocks(model))
    if model.beam_interpolation != NATURAL:
        result['beam_interpolation'] = model.beam_interpolation
    return result


def signature(model):
    def scalar(value):
        if isinstance(value,np.generic):return value.item()
        raise AswError('Model contains a value that cannot be written to ASW.')
    return hashlib.sha256(json.dumps(model_data(model),sort_keys=True,separators=(',',':'),default=scalar).encode()).hexdigest()


def text_line(value,name,token=False):
    if not isinstance(value,str) or not value.strip() or value!=value.strip() or re.search(r'[\r\n!]',value) or value.startswith(('#','%')) or value.split()[0].lower()=='end' or (token and re.search(r'[\s#%]',value)):
        raise AswError(f'{name} must be a nonempty ASW {"token" if token else "line"} without comment delimiters or End.')
    return value


def integer(value,name):
    if isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,float,np.integer,np.floating)) or not np.isfinite(value) or value!=int(value):
        raise AswError(f'{name} must be an integer.')
    return str(int(value))


def numeric_row(value,width,name,integers=()):
    try:a=np.asarray(value,dtype=float)
    except (TypeError,ValueError) as exc:raise AswError(f'{name} requires numeric values.') from exc
    if a.shape!=(width,) or not np.all(np.isfinite(a)):raise AswError(f'{name} requires {width} finite values.')
    return ' '.join(integer(v,name) if i in integers else format(float(v),'.17g') for i,v in enumerate(a))


def validate_compiled(d):
    if (not np.array_equal(d.t,d._compiled_t) or not np.array_equal(d.values,d._compiled_values)
            or d.interpolation != d._compiled_interpolation):
        raise AswError(f'Distribution {d.name} changed without rebuilding its spline; replace it with a new Distribution.')


def beam_text(beam):
    lines=[f'Beam {integer(beam.index,"Beam index")} {integer(beam.physical_index,"Physical beam index")}',text_line(beam.name,'Beam name')]
    for key,d in beam.distributions.items():
        name=text_line(key,'Distribution name',True)
        if name!=canonical(name) or d.name!=name:raise AswError('Distribution keys and names must use the same canonical spelling.')
        validate_compiled(d)
        lines.append('t '+name)
        for t,v in zip(d.t,d.values):lines.append(numeric_row([t,v],2,name))
    return '\n'.join(lines+['End'])


def serialize(model,*,canonical=False):
    # Check even on the lossless path: arrays could have been restored to their
    # original values after compiling a different spline.
    for b in model.beams:
        for d in b.distributions.values():
            validate_compiled(d)
            if d.interpolation != model.beam_interpolation:
                raise AswError('Beam distribution interpolation does not match its model; rebuild with the model policy.')
    if not canonical and model.source==model._parsed_source and signature(model)==model._parsed_signature:
        return model.source
    blocks=[]
    def add(kind,lines):blocks.append('\n'.join([kind,*lines,'End']))
    # Retain user annotations, with explicit relocation in normalized output.
    raw=(model._parsed_source if model._parsed_source is not None else model.source).splitlines()
    unknown_lines={i for b in model.blocks if b.kind not in KNOWN for i in range(b.line-1,b.end_line)}
    name_lines={ln for b in model.blocks if b.kind=='name' for ln,_ in b.lines}
    name_lines.update(b.lines[0][0] for b in model.blocks if b.kind=='beam' and b.lines)
    comments=[]
    for i,line in enumerate(raw):
        found=re.search(r'!.*' if i+1 in name_lines else r'[!#%].*',line)
        if i not in unknown_lines and found and found.group()!=COMMENTS_HEADER:comments.append(found.group())
    if comments:blocks.append(COMMENTS_HEADER+'\n'+'\n'.join(comments))
    add('Name',[text_line(model.name,'Aircraft name')])
    if set(model.units.declarations)-set('LTFM'):raise AswError('Unknown unit declaration.')
    add('Unit',[f'{key} {numeric_row([factor],1,"Unit magnitude")} {text_line(label,"Unit label",True)}'
        for key in 'LTFM' if key in model.units.declarations for factor,label in [model.units.declarations[key]]])
    add('Constant',[numeric_row(model.constants,3,'Constant')])
    if np.shape(model.reference)!=(4,3):raise AswError('Reference requires four xyz/area-chord-span rows in the model.')
    add('Reference',[numeric_row(r,3,'Reference') for r in model.reference])
    for kind,values in model.records.items():
        if kind=='jangle':
            for value in values:
                add('Jangle',[numeric_row(value['header'],4,'Jangle header',{0})]+[numeric_row(r,2,'Jangle curve') for r in value['curve']])
        elif kind in SCHEMAS and kind not in ('constant','reference'):
            width,ints,_=SCHEMAS[kind]
            if values:
                # Canonical output must retain a proven exact attachment when
                # source scaling is replaced by explicit binary64 values.
                # Never mutate the original parsed record arrays.
                rows = values
                if kind == 'weight':
                    rows = [row.copy() for row in values]
                    for original, row in zip(values, rows):
                        row[1] = weight_station(model, original)
                add(kind.capitalize(),[numeric_row(row,width,kind,ints) for row in rows])
        else:raise AswError(f'Unknown model record group {kind!r}; edit its original source block.')
    blocks.extend(beam_text(b) for b in model.beams)
    blocks.extend(unknown_blocks(model))
    result='\n\n'.join(blocks)+'\n'
    parse_asw(result, beam_interpolation=model.beam_interpolation)
    return result


def edit_distribution(model,beam_index,name,*,points=None,multiplier=1.,adder=0.,remove=False,symmetry='keep',graft=None,delete_station=None):
    """Return an independent, validated model; no edits commit on failure.

    Points are file-space (t,value) pairs. A leading zero retains the documented
    property-wise surface symmetry, including y reflection about its center.
    Doubled t values retain their distinct left/right values and spline segments.
    Inserting one station without changing existing points adds a row to every
    property in the same source table, sampling its companion distributions.
    Deleting one station also removes its row from every property in that table.
    delete_station identifies the original ascending row for doubled stations.
    """
    integer(beam_index,'Beam index');name=canonical(text_line(name,'Distribution name',True))
    if name not in DEFAULTS and name!='chord' and not re.fullmatch(r'dC[LMD]dF[1-9]\d*',name):
        raise AswError('Edit a documented distribution or an indexed flap derivative; unknown properties remain in source.')
    from .asw_source_edit import distribution_source, resolve_weight_aliases
    edited=parse_asw(model.dumps(), beam_interpolation=model.beam_interpolation)
    # Resolve proven attachment aliases locally while station provenance still
    # exists, retaining the established semantics without relocating comments.
    source=resolve_weight_aliases(edited)
    if source!=edited.source:
        edited=parse_asw(source, beam_interpolation=model.beam_interpolation)
    beam=next((b for b in edited.beams if b.index==beam_index),None)
    if beam is None:raise AswError('No beam with that index.')
    if delete_station is not None:
        integer(delete_station,'Station row');delete_station=int(delete_station)
        if remove or name not in beam.distributions or not 0<=delete_station<len(beam.distributions[name].t):
            raise AswError('Select an existing station row to delete.')
    edit_report=None
    if remove:
        if points is not None or multiplier!=1 or adder!=0 or symmetry!='keep' or graft is not None:raise AswError('Removal cannot also replace, scale, mirror, or graft a distribution.')
        if name not in beam.distributions:raise AswError('That distribution is already omitted.')
        del beam.distributions[name]
    else:
        try:
            multiplier=float(multiplier);adder=float(adder)
        except (TypeError,ValueError) as exc:raise AswError('Scale and offset must be finite numbers.') from exc
        if not np.all(np.isfinite([multiplier,adder])):raise AswError('Scale and offset must be finite.')
        if points is None:
            if name not in beam.distributions:raise AswError('Supply station/value pairs to add a distribution.')
            old=beam.distributions[name];data=np.column_stack((old.t,old.values))
        else:
            try:data=np.asarray(points,dtype=float)
            except (TypeError,ValueError) as exc:raise AswError('Stations require numeric (t,value) pairs.') from exc
        if data.ndim!=2 or data.shape[1]!=2 or not np.all(np.isfinite(data)):raise AswError('Stations require finite (t,value) pairs.')
        with np.errstate(over='ignore',invalid='ignore'):values=data[:,1]*multiplier+adder
        if not np.all(np.isfinite(values)):raise AswError('Scaled distribution values must remain finite.')
        from .distribution_curve import symmetry as apply_symmetry, graft as apply_graft
        distribution=Distribution(name,data[:,0],values,0,interpolation=model.beam_interpolation)
        distribution=apply_symmetry(distribution,symmetry,beam.lifting or name=='chord')
        beam.distributions[name]=distribution
        if graft is not None:
            domain=beam.domain
            if beam.lifting and distribution.t[0]==0:domain=(0.,max(abs(domain[0]),abs(domain[1])))
            distribution,edit_report=apply_graft(distribution,graft,domain)
            beam.distributions[name]=distribution
    source,shared=distribution_source(edited,beam_index,name,delete_station=delete_station)
    beam.distributions.update(shared)
    result=parse_asw(source, beam_interpolation=model.beam_interpolation)
    if signature(result)!=signature(edited):
        raise AswError('Property edit could not be saved without changing other model data.')
    result._distribution_edit=edit_report
    return result


def distribution_report(model,beam_index,name):
    """Original samples and the compiled property across the actual beam domain."""
    name=canonical(name);beam=next((b for b in model.beams if b.index==beam_index),None)
    if beam is None or name not in beam.distributions:raise AswError('Select an explicitly defined beam distribution.')
    d=beam.distributions[name];validate_compiled(d);segments=[]
    lo,hi=beam.domain;mirrored=bool(not d.constant_rigid and beam.lifting and d.t[0]==0)
    breaks=list(d.breaks)+([-float(t) for t in d.breaks]+[0.] if mirrored else [])
    boundaries=sorted({lo,hi,*[t for t in breaks if lo<t<hi]})
    for left,right in zip(boundaries,boundaries[1:]):
        t=np.linspace(left,right,81);values=d.evaluate(t,mirror=beam.lifting)
        values[-1]=d.evaluate(right,mirror=beam.lifting,side='left')
        if not np.all(np.isfinite(values)):raise AswError('Distribution spline has nonfinite values; revise its stations.')
        query=np.abs(t) if mirrored else t
        segments.append(dict(t=t.tolist(),values=values.tolist(),extrapolated=bool(not d.constant_rigid and np.any((query<d.t[0])|(query>d.t[-1])))))
    result=dict(beam=beam.index,name=name,points=np.column_stack((d.t,d.values)).tolist(),segments=segments,
        mirrored=mirrored,rigid_zero=name in RIGID,
        editing=getattr(model,'_distribution_edit',None),
        domain=list(beam.domain),limitations=[('Natural spline endpoint conditions remain an ASWING parity gap.'
            if d.interpolation == NATURAL else
            'Explicit drela-segspl-v1 beam interpolation; the historical ASWING caller remains unverified.'),
            'Plot values are raw file values; zero stiffness denotes the rigid limit. Refine nodes independently to assess solution accuracy.'])
    if d.constant_rigid:
        result['constant_rigid']=True
        result['limitations'][0]='Constant rigid override across the beam domain; the single file sample is retained without spline fitting or extrapolation.'
    return result
