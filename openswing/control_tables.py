"""Original .con gain-table syntax; explicit bindings avoid guessed INDEXC maps."""
import re
import numpy as np
from .asw import numbers, AswError
from .feedback import Gain


def parse_control_tables(source):
    if not isinstance(source,str):raise AswError('Control tables must be text.')
    lines=[]
    for number,raw in enumerate(source.splitlines(),1):
        line=raw.strip()
        if not line or line[0] in '!#$cC':continue
        line=re.split(r'[!#$]',line,maxsplit=1)[0].strip()
        if line:lines.append((number,line))
    cursor=0;tables=[];seen=set()
    def row(width):
        nonlocal cursor
        if cursor>=len(lines):raise AswError('Incomplete .con gain-table block.')
        line,text=lines[cursor];cursor+=1
        values=numbers(text,line)
        if len(values)!=width:raise AswError(f'Control table requires {width} values on this line.',line)
        return np.asarray(values,dtype=float),line
    while cursor<len(lines):
        head,line=row(4);i,j,s,factor=head
        if any(v!=int(v) for v in (i,j,s)) or min(i,j)<=0 or s<0:raise AswError('Invalid .con output/input/sensor indices.',line)
        identity=tuple(map(int,(i,j,s)))
        if identity in seen:raise AswError('Duplicate .con output/input/sensor table.',line)
        seen.add(identity)
        dims,line=row(2)
        if any(v!=int(v) or v<1 or v>10000 for v in dims) or np.prod(dims)>1000000:
            raise AswError('Invalid .con table dimensions.',line)
        nx,ny=map(int,dims)
        x,_=row(nx);y,_=row(ny)
        z=np.array([row(nx)[0] for _ in range(ny)])*factor
        gain=dict(speed=x.tolist(),density=y.tolist(),values=z.tolist())
        Gain(gain)
        tables.append(dict(output=identity[0],input=identity[1],sensor=identity[2],factor=float(factor),gain=gain))
    if not tables:raise AswError('No .con gain tables found.')
    return tables


def bind_control_tables(source,bindings,*,commands=None,initial_integrals=None):
    """Bind each (sensor,index) and output index, including explicit unit factors.

    Factor converts a named measurement to the table's input unit, or a table
    output to a file actuator setting. Unknown indices never silently acquire
    a default interpretation. Tables schedule on true airspeed and density.
    """
    if not isinstance(bindings,dict) or set(bindings)-{'outputs','inputs','outside'}:
        raise AswError('Control bindings require outputs and inputs, with optional outside policy.')
    outputs={};outside=bindings.get('outside','error')
    for table in parse_control_tables(source):
        output=bindings.get('outputs',{}).get(str(table['output']))
        signal=bindings.get('inputs',{}).get(f"{table['sensor']}:{table['input']}")
        if (not isinstance(output,dict) or set(output)-{'actuator','factor'} or 'actuator' not in output
            or not isinstance(signal,dict) or set(signal)-{'input','mode','factor'} or 'input' not in signal):
            raise AswError(f"Explicit input/output bindings are required for .con table {table['output']}, {table['input']}, {table['sensor']}.")
        factors=[output.get('factor',1.),signal.get('factor',1.)]
        if any(not isinstance(f,(int,float)) or not np.isfinite(f) for f in factors):raise AswError('Control binding unit factors must be finite.')
        gain={**table['gain'],'values':(np.asarray(table['gain']['values'])*np.prod(factors)).tolist(),'outside':outside}
        Gain(gain)
        outputs.setdefault(output['actuator'],[]).append(dict(input=signal['input'],mode=signal.get('mode','error'),gain=gain))
    return dict(outputs=[dict(actuator=name,terms=terms) for name,terms in outputs.items()],
                commands={} if commands is None else commands,initial_integrals={} if initial_integrals is None else initial_integrals)
