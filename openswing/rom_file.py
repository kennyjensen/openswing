"""Annotated one-file ASWING ROM exchange, independently implemented.

The public ISAE examples store real poles and one representative per complex
pair. Their data are perturbations; no aircraft baseline is contained here.
Unknown variable/unit labels are preserved, not guessed or silently converted.
"""
import json
import re
import numpy as np
from scipy.linalg import block_diag
from .aero import AnalysisError
from .linear_dynamics import complex_data

NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:(?:[eEdD][+-]?\d+)|(?:[+-]\d{2,3}))?'
PAIR = re.compile(r'^\s*('+NUMBER+r')\s+('+NUMBER+r')\s+(.+?)\s*$')


def label(value):
    return re.sub(r'\[\s*(\d+)\s*\]', r'[\1]', ' '.join(value.split()))


def number(value):
    value = re.sub(r'(?<=\d)([+-]\d{2,3})$', r'e\1', value) if not re.search('[eEdD]', value) else value
    out = float(value.replace('D', 'e').replace('d', 'e'))
    if not np.isfinite(out):
        raise AnalysisError('ROM numbers must be finite.')
    return out


def array(value):
    return np.asarray(value['real'])+1j*np.asarray(value['imag'])


def matrices(model):
    n,u,y,v=len(model['modes']),len(model['inputs']),len(model['outputs']),len(model['state_names'])
    return tuple(array(model['matrices'][key]).reshape(shape) for key,shape in
                 [('B',(n,u)),('C',(y,n)),('D',(y,u)),('V',(v,n))])


def input_rates(model,b):
    """Express printed input-rate coefficients in the eigenvalue time unit."""
    seconds={'s':1.,'sec':1.,'second':1.,'ms':.001,'min':60.,'minute':60.,'h':3600.,'hr':3600.,'hour':3600.}
    target=model['time_unit'];out=b.copy()
    for j,item in enumerate(model['inputs']):
        unit=re.sub(r'\s+','',item['coefficient_unit'])
        if not unit.startswith('1/'):
            raise AnalysisError('ROM control-row coefficient unit must be an inverse time for response evaluation.')
        origin=unit[2:]
        if origin==target:continue
        if origin not in seconds or target not in seconds:
            raise AnalysisError('Cannot convert different ROM eigenvalue and input-rate time units.')
        out[:,j]*=seconds[target]/seconds[origin]
    return out


def parse_rom(source):
    if not isinstance(source, str) or not source.strip() or len(source) > 20*1024*1024:
        raise AnalysisError('ROM input must be nonempty text, at most 20 MiB.')
    modes, direct, input_units = [], {}, {}
    name = None; point = None; mode = None; section = None; forcing = None; direct_seen = False
    def fail(message):
        raise AnalysisError(f'ROM line {line_number}: {message}')
    for line_number, raw in enumerate(source.lstrip('\ufeff').splitlines(), 1):
        text = raw.strip()
        if not text:
            continue
        if text.startswith('#'):
            text = text[1:].strip()
            if name is None and text:
                name = text
            if match := re.fullmatch(r'Op\.Point\s*:\s*(\d+)', text, re.I):
                if point is not None:fail('Duplicate operating point.')
                point = int(match[1])
            elif match := re.fullmatch(r'Mode\s*:\s*([1-9]\d*)', text, re.I):
                if direct_seen:fail('A mode follows the final direct matrix.')
                if any(m['index'] == int(match[1]) for m in modes):fail('Duplicate mode index.')
                mode = dict(index=int(match[1]), state={}, B={}, C={}, sections=set())
                modes.append(mode);section = None
            elif text.lower().startswith('eigenvalue:'):
                if mode is None or 'eigenvalue' in mode:fail('Missing mode or duplicate eigenvalue.')
                match = PAIR.fullmatch(text.split(':', 1)[1])
                if not match:fail('Expected real/imaginary eigenvalue and inverse-time unit.')
                mode['eigenvalue'] = [number(match[1]), number(match[2])]
                unit = re.sub(r'\s+', '', match[3])
                if not unit.startswith('1/') or len(unit) <= 2:fail('Eigenvalue unit must be 1 / time-unit.')
                mode['unit'] = unit
            elif text.lower().startswith('eigenvector'):
                if mode is None:fail('Eigenvector without a mode.')
                section = 'state'
            elif match := re.fullmatch(r'Control variable influence-matrix row\s+(\d+)', text, re.I):
                if mode is None or int(match[1]) != mode['index']:fail('Input row refers to the wrong mode.')
                if 'B' in mode['sections']:fail('Duplicate input section.')
                mode['sections'].add('B');section = 'B'
            elif match := re.fullmatch(r'Output variable dependence-matrix column\s+(\d+)', text, re.I):
                if mode is None or int(match[1]) != mode['index']:fail('Output column refers to the wrong mode.')
                if 'C' in mode['sections']:fail('Duplicate output section.')
                mode['sections'].add('C');section = 'C'
            elif re.match(r'Output-variable dependence-matrix\s+D\s*\+', text, re.I):
                if direct_seen:fail('Duplicate direct matrix.')
                direct_seen = True;section = 'D';mode = None;forcing = None
            elif match := re.fullmatch(r'Column for forcing variable\s*:\s*(.+)', text, re.I):
                if not direct_seen:fail('Direct column before the direct matrix header.')
                forcing = label(match[1])
                if forcing in direct:fail('Duplicate direct-matrix input.')
                direct[forcing] = {};section = 'D'
            elif text.startswith('OpenSwing input-unit:'):
                try:
                    item = json.loads(text.split(':', 1)[1])
                    key, unit = label(item['name']), item['unit']
                    if not isinstance(unit, str) or not unit:raise ValueError()
                    if key in input_units:fail('Duplicate input-unit metadata.')
                    input_units[key] = unit
                except (KeyError, TypeError, ValueError, AttributeError):fail('Invalid input-unit metadata.')
            continue
        match = PAIR.fullmatch(text)
        if not match:fail('Expected two finite numeric columns and an annotated variable.')
        value = complex(number(match[1]), number(match[2]));tail = match[3]
        if section == 'state' and mode is not None:
            key, unit, target = label(tail), None, mode['state']
        elif section == 'B' and mode is not None:
            row = re.fullmatch(r'(.*?)\s*=\s*d\(\s*zdot\s*(\d+)\s*\)\s*/\s*d\(\s*(.*?)\s*\)', tail)
            if not row or int(row[2]) != mode['index']:fail('Invalid control-row annotation or mode index.')
            unit, key, target = label(row[1]), label(row[3]), mode['B']
        elif section == 'C' and mode is not None:
            row = re.fullmatch(r'(.*?)\s*=\s*d\(\s*(.*?)\s*\)\s*/\s*d\(\s*z\s*(\d+)\s*\)', tail)
            if not row or int(row[3]) != mode['index']:fail('Invalid output-column annotation or mode index.')
            unit, key, target = label(row[1]), label(row[2]), mode['C']
        elif section == 'D' and forcing is not None:
            row = re.fullmatch(r'(.*?)\s*=\s*d\(\s*(.*?)\s*\)\s*/\s*d\(\s*(.*?)\s*\)', tail)
            if not row or label(row[3]) != forcing:fail('Direct row refers to the wrong forcing variable.')
            unit, key, target = label(row[1]), label(row[2]), direct[forcing]
        else:
            fail('Numeric data outside a recognized ROM section.')
        if not key or (unit is not None and not unit):fail('Missing variable label or unit.')
        if key in target:fail('Duplicate variable in a ROM section.')
        target[key] = (value, unit)
    if not modes or not direct_seen:
        raise AnalysisError('Incomplete ROM: mode and final direct-matrix sections are required.')
    if any('eigenvalue' not in m or m['sections'] != {'B', 'C'} for m in modes):
        raise AnalysisError('Incomplete ROM mode: eigenvalue, input row and output column are required.')
    if len({m['unit'] for m in modes}) != 1:
        raise AnalysisError('ROM eigenvalue time units differ between modes.')
    inputs, outputs, states = (list(modes[0][key]) for key in ('B', 'C', 'state'))
    if set(direct) != set(inputs) or set(input_units)-set(inputs):
        raise AnalysisError('ROM direct matrix or input metadata does not match the mode inputs.')
    for m in modes:
        for section, keys in [('B', inputs), ('C', outputs), ('state', states)]:
            if set(m[section]) != set(keys):raise AnalysisError('ROM variable sets differ between modes.')
            if any(m[section][key][1] != modes[0][section][key][1] for key in keys):
                raise AnalysisError('ROM coefficient units differ between modes.')
    for values in direct.values():
        if set(values) != set(outputs) or any(values[k][1] != modes[0]['C'][k][1] for k in outputs):
            raise AnalysisError('ROM direct-matrix output labels or units do not match the modal outputs.')
    return dict(format='aswing-rom', format_version=1, name=name or 'Imported ROM', operating_point=point,
        time_unit=modes[0]['unit'][2:],
        modes=[dict(index=m['index'], eigenvalue=m['eigenvalue']) for m in modes],
        inputs=[dict(name=k, unit=input_units.get(k), coefficient_unit=modes[0]['B'][k][1]) for k in inputs],
        outputs=[dict(name=k, unit=modes[0]['C'][k][1]) for k in outputs],
        state_names=states,
        matrices=dict(B=complex_data(np.array([[m['B'][k][0] for k in inputs] for m in modes]).reshape(len(modes),len(inputs))),
            C=complex_data(np.array([[m['C'][k][0] for m in modes] for k in outputs]).reshape(len(outputs),len(modes))),
            D=complex_data(np.array([[direct[k][o][0] for k in inputs] for o in outputs]).reshape(len(outputs),len(inputs))),
            V=complex_data(np.array([[m['state'][k][0] for m in modes] for k in states]).reshape(len(states),len(modes)))),
        source=source,
        limitations=[
            'One stored representative supplies both members of each nonreal conjugate pair. Real poles contribute once.',
            'Response uses the matrices printed in this file. The aircraft baseline, full descriptor and ASWING-specific Bode reconstruction corrections are not contained in a ROM file.',
            'Unknown variable and unit labels are preserved. Original files generally do not specify physical input units; these remain unspecified rather than inferred.',
            'Importing an external ROM does not validate the underlying aircraft physics or attach it to the current .asw model.'
        ])


def real_rom(model):
    b, c, d, v = matrices(model)
    b=input_rates(model,b)
    blocks, rows, columns, vectors, groups = [], [], [], [], []
    if np.max(abs(d.imag), initial=0.) > 1e-9*max(np.max(abs(d.real), initial=0.), 1e-300):
        raise AnalysisError('The printed direct matrix is complex; a real constant-input realization is not established.')
    poles = [complex(*mode['eigenvalue']) for mode in model['modes']]
    for k, pole in enumerate(poles):
        bk, ck, vk = b[k].copy(), c[:,k].copy(), v[:,k].copy()
        start = sum(block.shape[0] for block in blocks)
        if pole.imag == 0:
            combined = np.r_[ck, vk]
            pivot = combined[np.argmax(abs(combined))] if len(combined) and np.max(abs(combined)) else 0.
            phase = pivot/abs(pivot) if pivot else (np.conj(bk[np.argmax(abs(bk))])/np.max(abs(bk)) if len(bk) and np.max(abs(bk)) else 1.)
            ck, vk, bk = ck/phase, vk/phase, bk*phase
            for x in (ck, vk, bk):
                if np.max(abs(x.imag), initial=0.) > 1e-8*max(np.max(abs(x.real), initial=0.),1e-300):
                    raise AnalysisError('A real pole has incompatible complex residues; its real normalization is unresolved.')
            blocks.append(np.array([[pole.real]]));rows.append(bk.real[None,:]);columns.append(ck.real[:,None]);vectors.append(vk.real[:,None])
        else:
            if any(j != k and abs(other-pole.conjugate()) <= 1e-8*abs(pole) for j,other in enumerate(poles)):
                raise AnalysisError('The ROM lists both conjugate signs; representative-pair counting is ambiguous.')
            if pole.imag < 0:pole,bk,ck,vk = pole.conjugate(),bk.conj(),ck.conj(),vk.conj()
            blocks.append(np.array([[pole.real,pole.imag],[-pole.imag,pole.real]]))
            rows.append(np.array([2*bk.real,-2*bk.imag]));columns.append(np.column_stack((ck.real,ck.imag)));vectors.append(np.column_stack((vk.real,vk.imag)))
        groups.append(dict(index=model['modes'][k]['index'],coordinates=list(range(start,start+len(blocks[-1])))))
    return dict(A=block_diag(*blocks).tolist(),B=np.vstack(rows).tolist(),C=np.column_stack(columns).tolist(),
                D=d.real.tolist(),V=np.column_stack(vectors).tolist(),groups=groups,time_unit=model['time_unit'])


def rom_response(model, frequencies):
    omega = np.asarray(frequencies,dtype=float)
    if omega.ndim != 1 or not len(omega) or not np.all(np.isfinite(omega)) or np.any(omega < 0) or np.any(np.diff(omega) <= 0):
        raise AnalysisError('ROM frequencies must be finite, nonnegative and strictly increasing, in the printed inverse-time unit.')
    # This also establishes real-pole phases, direct reality and pair counting.
    real = real_rom(model)
    b,c,d,_ = matrices(model)
    b=input_rates(model,b)
    samples=[]
    for w in omega:
        response=d.copy();error=None
        for k,mode in enumerate(model['modes']):
            pole=complex(*mode['eigenvalue']);residue=np.outer(c[:,k],b[k])
            for root,value in [(pole,residue)]+([] if pole.imag == 0 else [(pole.conjugate(),residue.conj())]):
                divisor=1j*w-root
                if abs(divisor) <= 1e-12*max(abs(root),w,np.finfo(float).tiny):
                    error='Frequency lies on a retained pole; no unique harmonic state is defined.';break
                with np.errstate(over='ignore',invalid='ignore'):response += value/divisor
            if error:break
        if not np.all(np.isfinite(response)):error='Nonfinite ROM response; inspect coefficient scaling and pole proximity.'
        samples.append(dict(omega=float(w),converged=error is None,**(dict(error=error) if error else dict(response=complex_data(response)))))
    return dict(analysis='imported_rom',model=model,real_matrices=real,samples=samples,
                converged=all(s['converged'] for s in samples),normalized_text=write_rom(model))


def write_rom(model):
    def safe(text):
        if not isinstance(text,str) or not text or any(x in text for x in ('\n','\r','#',' = ',' / d(')):
            raise AnalysisError('ROM labels must be nonempty single-line annotations.')
        return text
    def pair(value):return f'{value.real: .16e} {value.imag: .16e}'
    inputs,outputs=model['inputs'],model['outputs']
    b,c,d,v=matrices(model)
    lines=['# '+safe(model['name']),'#']
    if model.get('operating_point') is not None:lines.append(f"#   Op.Point  :    {model['operating_point']}")
    for item in inputs:
        if item.get('unit'):lines.append('# OpenSwing input-unit: '+json.dumps(dict(name=item['name'],unit=item['unit']),ensure_ascii=True))
    for k,mode in enumerate(model['modes']):
        n=mode['index'];pole=complex(*mode['eigenvalue'])
        lines += ['#','# ======================================================',f'#   Mode:    {n}','#',
            f"#   Eigenvalue: {pair(pole)} 1/{safe(model['time_unit'])}",'#','#   Eigenvector...','#','#   Real(x)      Imag(x)']
        lines += [pair(v[j,k])+'  '+safe(name) for j,name in enumerate(model['state_names'])]
        lines += ['#','# ------------------------------------------------------',f'# Control variable influence-matrix row  {n}','#','#   Real(w*B)    Imag(w*B)']
        lines += [f"{pair(b[k,j])}  {safe(item['coefficient_unit'])} =  d(zdot {n}) / d({safe(item['name'])})" for j,item in enumerate(inputs)]
        lines += ['#','# ------------------------------------------------------',f'# Output variable dependence-matrix column    {n}','#','# Real(Cv+Qvl) Imag(Cv+Qvl)']
        lines += [f"{pair(c[j,k])}  {safe(item['unit'])} =  d( {safe(item['name'])} ) / d(z {n})" for j,item in enumerate(outputs)]
    lines += ['#','# ======================================================','#  Output-variable dependence-matrix  D + QVW*B','#   generated using above modes']
    for j,item in enumerate(inputs):
        name=safe(item['name']);lines += ['#','# ------------------------------------------------------',f'#  Column for forcing variable: {name}','#','# Real(D+QVW*B) Imag(D+QVW*B)']
        lines += [f"{pair(d[k,j])}  {safe(output['unit'])} =  d( {safe(output['name'])} ) / d({name})" for k,output in enumerate(outputs)]
    return '\n'.join(lines)+'\n'


_LABELS = dict(V='V',A='alpha',B='beta',Ex='Phi',Ey='Theta',Ez='Psi',Cr='Gamma')
for prefix,description,axes in [('A','dU{} Lacc','xyz'),('G','dW{} Aacc','xyz'),('W','W{} rate','xyz'),
    ('R','R{} pos','XYZ'),('U','U{} vel','XYZ'),('r','r{} pos','xyz'),('u','u{} vel','xyz'),('F','F{} for','csn'),('M','M{}` mom','csn')]:
    _LABELS.update({prefix+axis:description.format(axis) for axis in axes})


def export_rom(result, units, name='OpenSwing ROM'):
    """Convert the generated real model to annotated complex representatives.

    Physical measurements and time are exported in SI; actuator settings remain
    in the original file units. Custom command/gust/frame/global-Earth-velocity labels are
explicit OpenSwing extensions, never relabeled as legacy body velocities.
"""
    from .feedback import CHANNELS
    si=units.si_scales();L,T,F=si['L'],si['T'],si['F']
    conversion={'input L':(L,'m'),'input L/T':(L/T,'m/s'),'input L/T^2':(L/T**2,'m/s^2'),
        'input L^2/T':(L*L/T,'m^2/s'),'input F':(F,'N'),'input F L':(F*L,'N*m'),
        'input F/L':(F/L,'N/m'),'input F/L^2':(F/L**2,'Pa'),
        '1/input L':(1/L,'1/m'),'dimensionless':(1.,'dimensionless'),
        'rad':(1.,'rad'),'rad/input T':(1/T,'rad/s'),
        'rad/input T^2':(1/T**2,'rad/s^2'),'deg':(1.,'deg'),'deg/input T':(1/T,'deg/s'),'deg/input T^2':(1/T**2,'deg/s^2')}
    outputs=[];scales=[]
    for item in result['outputs']:
        if 'selector' in item:
            if item['unit'] not in conversion:
                raise AnalysisError('No SI conversion for this physical ROM output.')
            scale,unit=conversion[item['unit']];scales.append(scale)
            outputs.append(dict(name='OpenSwing '+item['name'],unit=unit))
            continue
        match=re.fullmatch(r'([A-Za-z]+)(\[\d+\])?',item['name'])
        if not match or match[1] not in _LABELS:raise AnalysisError('No ROM file label mapping for this output.')
        key,sensor=match[1],match[2] or ''
        scale,unit=conversion[CHANNELS[key][2]];scales.append(scale)
        legacy=_LABELS[key]
        if key in ('UX','UY','UZ') and not sensor:legacy=key+' Earth vel'
        outputs.append(dict(name=legacy+(' '+sensor if sensor else ''),unit=unit))
    scales=np.asarray(scales)
    ar,br,cr,dr,rate=(np.asarray(result['matrices'][key]) for key in ('A','B','C','D','D_rate'))
    frequency=max(np.linalg.norm(ar,2),np.finfo(float).tiny)
    reference=np.maximum(abs(dr),abs(cr)@abs(br)/frequency)
    if np.any(abs(rate)*frequency > 1e-8*np.maximum(reference,1e-300)):
        raise AnalysisError('The ROM has derivative-input output feedthrough; the observed .rom layout cannot represent D_rate. Use JSON or matrix text.')
    inputs=[];input_scales=[]
    for item in result['inputs']:
        match=re.fullmatch(r'(control|power)\.(\d+)',item['name'])
        input_name=(('Flap_' if match[1]=='control' else 'Peng_')+f'{int(match[2]):02d}') if match else item['name']
        input_scale,input_unit=conversion.get(item['unit'],(1.,item['unit']))
        input_scales.append(input_scale)
        inputs.append(dict(name=input_name,unit=input_unit,coefficient_unit='1 / s'))
    input_scales=np.asarray(input_scales)
    modes=[];b=[];c=[];expected=np.zeros_like(ar)
    for group in result['diagnostics']['retained']:
        ids=group['coordinates'];pole=complex(*group['eigenvalue'])
        if len(ids)==1:
            bk,ck=br[ids[0]],cr[:,ids[0]];expected[ids[0],ids[0]]=pole.real
        else:
            i,j=ids;bk=(br[i]-1j*br[j])/2;ck=cr[:,i]+1j*cr[:,j]
            expected[np.ix_(ids,ids)]=[[pole.real,pole.imag],[-pole.imag,pole.real]]
        modes.append(dict(index=group['source_index']+1,eigenvalue=[pole.real/T,pole.imag/T]))
        b.append(bk/T/input_scales);c.append(ck*scales)
    if np.linalg.norm(ar-expected) > 1e-8*max(np.linalg.norm(ar),np.finfo(float).tiny):
        raise AnalysisError('Reduced dynamics are not resolved independent real/complex modal blocks; .rom export would change the dynamics.')
    model=dict(format='aswing-rom',format_version=1,name=name,operating_point=1,time_unit='s',modes=modes,
        inputs=inputs,outputs=outputs,state_names=[],matrices=dict(B=complex_data(b),C=complex_data(np.column_stack(c)),
        D=complex_data(scales[:,None]*dr/input_scales),V=complex_data(np.empty((0,len(modes))))))
    # Reparse what is actually delivered, enforcing the same grammar and checks.
    text=write_rom(model);parsed=parse_rom(text);real_rom(parsed)
    return text
