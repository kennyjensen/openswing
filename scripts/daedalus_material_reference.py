"""Independent literal-table oracle for the published Daedalus input file.

This is validation code, not the application parser. It reads the literal text
without production imports. Cubic pieces use a separately solved, 50-digit
second-derivative system, not SciPy's spline implementation. Natural endpoint
conditions and exact one-sided evaluation are explicit OpenSwing conventions;
the published ASWING guide does not establish these as historical defaults.
Two-point pieces are evaluated directly as lines. Comment, scaling, per-field
reflection, missing-value and zero-stiffness rules follow the public guide.

No geometry, aerodynamic, structural, aircraft or harmonic solve is performed.
The only linear systems are the small independent material spline systems.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext
import math
import re

import numpy as np


# Transcribed from the guide's 'Variable Unit Default' table, not imported from
# the application. A missing chord identifies a body and has no numeric default.
ZERO_FIELDS = (
    'x y z twist EIcn EIcs EIsn mgcc mgnn mg Ccg Ncg Dmgcc Dmgnn Dmg DCcg DNcg '
    'Cea Nea Cta Nta tdeps tdgam Cshell Nshell Atshell radius Cdf Cdp alpha Cm'
).split()
RIGID_FIELDS = ('EIcc', 'EInn', 'GJ', 'EA', 'GKc', 'GKn')
DEFAULTS = {name:0. for name in ZERO_FIELDS}
DEFAULTS.update({name:math.inf for name in RIGID_FIELDS})
DEFAULTS.update(Xax=.5, CLmax=2., CLmin=-2., dCLda=2*math.pi)


def _numbers(text):
    """The literal fixture uses ordinary E notation and finite numbers only."""
    values = [float(word.replace('D','E').replace('d','e')) for word in text.split()]
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError('Expected finite literal numeric data: '+text)
    return values


def _decimal(value):
    # Reconstruct the exact binary input number; its arithmetic is then
    # independent of both native interpolation and NumPy/SciPy factorization.
    return Decimal.from_float(float(value))


class NaturalPiece:
    """Second-derivative cubic form with explicit natural end conditions."""

    def __init__(self, x, y):
        self.x, self.y = list(map(_decimal,x)), list(map(_decimal,y))
        n=len(self.x)
        if n<2 or len(self.y)!=n or any(b<=a for a,b in zip(self.x,self.x[1:])):
            raise ValueError('Each independent segment needs at least two increasing points')
        with localcontext() as context:
            context.prec=50
            h=[b-a for a,b in zip(self.x,self.x[1:])]
            slopes=[(b-a)/d for a,b,d in zip(self.y,self.y[1:],h)]
            self.linear = n==2 or all(v==slopes[0] for v in slopes[1:])
            self.slope=slopes[0]
            self.second=[Decimal(0)]*n
            self.system_size=0
            if not self.linear:
                # h[i-1] M[i-1] + 2(h[i-1]+h[i]) M[i] + h[i] M[i+1]
                #     = 6(slope[i]-slope[i-1]), M[0]=M[n-1]=0.
                diagonal=[2*(h[i-1]+h[i]) for i in range(1,n-1)]
                rhs=[6*(slopes[i]-slopes[i-1]) for i in range(1,n-1)]
                for j in range(1,n-2):
                    multiplier=h[j]/diagonal[j-1]
                    diagonal[j]-=multiplier*h[j]
                    rhs[j]-=multiplier*rhs[j-1]
                interior=[Decimal(0)]*(n-2)
                interior[-1]=rhs[-1]/diagonal[-1]
                for j in range(n-4,-1,-1):
                    interior[j]=(rhs[j]-h[j+1]*interior[j+1])/diagonal[j]
                self.second[1:-1]=interior
                self.system_size=n-2

    def evaluate(self, sample, derivative):
        x=_decimal(sample)
        if self.linear:
            if derivative==0:return self.y[0]+self.slope*(x-self.x[0])
            return self.slope if derivative==1 else Decimal(0)
        # Neighbor selection is independent of the native piecewise-polynomial
        # coefficients; extrapolation continues the nearest terminal interval.
        i=0
        while i<len(self.x)-2 and x>self.x[i+1]:i+=1
        h=self.x[i+1]-self.x[i]
        a=(self.x[i+1]-x)/h
        b=(x-self.x[i])/h
        m0,m1=self.second[i:i+2]
        if derivative==0:
            return (a*self.y[i]+b*self.y[i+1]
                    +((a*a*a-a)*m0+(b*b*b-b)*m1)*h*h/6)
        if derivative==1:
            return ((self.y[i+1]-self.y[i])/h
                    +((1-3*a*a)*m0+(3*b*b-1)*m1)*h/6)
        return a*m0+b*m1


class Table:
    """One declared variable; reflection is applied per table, not per beam."""

    def __init__(self,name,t,values,line):
        self.name,self.line=name,line
        self.t,self.values=list(t),list(values)
        if len(self.t)<2 or len(self.t)!=len(self.values):
            raise ValueError('A declared field needs at least two data rows')
        differences=[b-a for a,b in zip(self.t,self.t[1:])]
        self.reversed=any(v<0 for v in differences) and all(v<=0 for v in differences)
        if self.reversed:
            self.t.reverse();self.values.reverse()
        if any(b<a for a,b in zip(self.t,self.t[1:])):
            raise ValueError('Mixed increasing/decreasing stations')
        self.pieces=[]
        start=0
        for i in range(1,len(self.t)+1):
            if i==len(self.t) or self.t[i]==self.t[i-1]:
                self.pieces.append(NaturalPiece(self.t[start:i],self.values[start:i]))
                start=i
        self.starts=[float(piece.x[0]) for piece in self.pieces]
        self.ends=[float(piece.x[-1]) for piece in self.pieces]
        self.doubled=[a for a,b in zip(self.t,self.t[1:]) if a==b]
        self.scalar_evaluations=0

    def evaluate(self,t,*,surface=False,side='right',derivative=0):
        if side not in ('left','right') or derivative not in (0,1,2):
            raise ValueError('Only explicit left/right values and derivatives 0,1,2 are supported')
        points=np.asarray(t,dtype=float)
        if not np.isfinite(points).all():raise ValueError('Nonfinite query')
        values=[]
        reflected=surface and self.t[0]==0.
        with localcontext() as context:
            context.prec=50
            for raw in points.flat:
                negative=reflected and (raw<0 or (raw==0 and side=='left'))
                x=abs(raw) if reflected else raw
                branch_side=('left' if side=='right' else 'right') if negative else side
                candidates=[i for i,(a,b) in enumerate(zip(self.starts,self.ends)) if a<=x<=b]
                if candidates:
                    index=candidates[0] if branch_side=='left' else candidates[-1]
                else:
                    index=0 if x<self.starts[0] else len(self.pieces)-1
                value=self.pieces[index].evaluate(x,derivative)
                if negative:
                    if derivative%2:value=-value
                    if self.name=='y':
                        value=2*_decimal(self.values[0])-value if derivative==0 else -value
                values.append(float(value))
        self.scalar_evaluations+=points.size
        return np.asarray(values).reshape(points.shape)


@dataclass
class LiteralBeam:
    index:int
    physical_index:int
    name:str
    tables:dict
    headers:list

    @property
    def lifting(self):return 'chord' in self.tables

    @property
    def domain(self):
        name='chord' if self.lifting else next(k for k in ('x','y','z') if k in self.tables)
        table=self.tables[name]
        return (-table.t[-1] if self.lifting and table.t[0]==0 else table.t[0],table.t[-1])

    def value(self,name,t,*,side='right',derivative=0,raw=False):
        if name in self.tables:
            value=self.tables[name].evaluate(t,surface=self.lifting,side=side,derivative=derivative)
            if not raw and derivative==0 and name in RIGID_FIELDS:
                value=np.where(value==0,math.inf,value)
            return value
        if raw:raise KeyError(name)
        default=0. if re.fullmatch(r'dC[LMD]dF[1-9][0-9]*',name) else DEFAULTS[name]
        return np.full(np.asarray(t).shape,default if derivative==0 else 0.,dtype=float)


class LiteralModel:
    """Read the actual fixture's global and beam blocks without native objects."""

    def __init__(self,text):
        self.source=text
        lines=[]
        for number,line in enumerate(text.splitlines(),1):
            clean=line.split('!',1)[0].strip()
            if clean and clean[0] not in '#%':lines.append((number,clean))
        self.blocks=[];self.beams={};self.global_rows={};self.units={}
        i=0
        while i<len(lines):
            number,header=lines[i];i+=1
            body=[]
            while i<len(lines) and lines[i][1].lower()!='end':
                body.append(lines[i]);i+=1
            if i==len(lines):raise ValueError('Unterminated block '+header)
            i+=1
            self.blocks.append(dict(line=number,header=header,body=body))
            words=header.split();kind=words[0].lower()
            if kind=='beam':
                index=int(words[1]);physical=int(words[2]) if len(words)==3 else index
                if len(words) not in (2,3) or index in self.beams:raise ValueError('Invalid beam declaration')
                self.beams[index]=self._beam(index,physical,body)
            elif kind=='name':
                if len(body)!=1:raise ValueError('Expected one literal model name')
                self.name=body[0][1]
            elif kind in ('units','unit'):
                for _,line in body:
                    symbol,factor,label=line.split()
                    if symbol not in ('L','T','F'):raise ValueError('Unknown unit dimension')
                    self.units[symbol]=dict(factor=float(factor),label=label)
            elif kind in ('constant','reference','weight','engine','strut','joint','ground'):
                self.global_rows[kind]=self._global(kind,body)
            else:raise ValueError('Unsupported block outside actual Daedalus scope: '+kind)
        if sorted(self.beams)!=[1,2,3,4,5]:raise ValueError('Expected five literal Daedalus beams')

    def _beam(self,index,physical,body):
        name=body[0][1];tables={};headers=[];active=None
        def finish():
            if active is None:return
            labels=active['labels'];rows=active['rows']
            if len(rows)<2:raise ValueError('Insufficient rows in distribution')
            for column,label in enumerate(labels[1:],1):
                if label in tables:raise ValueError('Repeated field outside actual fixture scope')
                tables[label]=Table(label,[r[0] for r in rows],[r[column] for r in rows],active['line'])
            headers.append({k:v for k,v in active.items() if k!='rows'})
        for line,text in body[1:]:
            words=text.split()
            if words[0].lower()=='t':
                finish()
                active=dict(line=line,labels=words,rows=[],source_lines=[line])
                multiplier=[1.]*len(words);adder=[0.]*len(words)
                continue
            if active is None:raise ValueError('Data before field declaration')
            active['source_lines'].append(line)
            if words[0] in ('*','+'):
                values=_numbers(' '.join(words[1:]))
                if len(values)!=len(active['labels']):raise ValueError('Modifier width differs from header')
                if words[0]=='*':multiplier=values
                else:adder=values
            else:
                row=_numbers(text)
                if len(row)!=len(multiplier):raise ValueError('Data width differs from header')
                active['rows'].append([v*m+a for v,m,a in zip(row,multiplier,adder)])
        finish()
        return LiteralBeam(index,physical,name,tables,headers)

    def _global(self,kind,body):
        rows=[];multiplier=None;adder=None
        integer_columns={'weight':1,'strut':1,'joint':2,'ground':1,'engine':3}.get(kind,0)
        for _,text in body:
            words=text.split()
            if words[0] in ('*','+'):
                # Only Weight has a modifier in this literal fixture. Reject
                # broader layouts rather than infer unverified field semantics.
                if kind!='weight':raise ValueError('Global modifier outside actual fixture scope')
                values=_numbers(' '.join(words[1:]))
                if words[0]=='*':multiplier=values
                else:adder=values
                continue
            values=_numbers(text)
            if any(v!=int(v) for v in values[:integer_columns]):raise ValueError('Noninteger global index')
            tail=values[integer_columns:]
            if multiplier is not None and len(multiplier)!=len(tail):raise ValueError('Global modifier width')
            if adder is not None and len(adder)!=len(tail):raise ValueError('Global adder width')
            rows.append(values[:integer_columns]+[v*(multiplier[j] if multiplier is not None else 1.)
                +(adder[j] if adder is not None else 0.) for j,v in enumerate(tail)])
        return rows
