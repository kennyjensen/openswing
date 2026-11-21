"""Bounded scalar expression evaluator for implicit custom control equations.

No Python evaluation or code execution: only the documented syntax tree nodes
and literal measurement/state references are compiled into scalar functions.
"""
import ast
import operator
import numpy as np
from .aero import AnalysisError

FUNCTIONS = dict(sin=(np.sin,1),cos=(np.cos,1),tan=(np.tan,1),tanh=(np.tanh,1),
    asin=(np.arcsin,1),acos=(np.arccos,1),atan=(np.arctan,1),
    exp=(np.exp,1),log=(np.log,1),sqrt=(np.sqrt,1),abs=(np.abs,1),
    minimum=(np.minimum,2),maximum=(np.maximum,2),atan2=(np.arctan2,2))
BINARY = {ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:np.divide,ast.Pow:np.power}
COMPARE = {ast.Lt:operator.lt,ast.LtE:operator.le,ast.Gt:operator.gt,ast.GtE:operator.ge,ast.Eq:operator.eq,ast.NotEq:operator.ne}
ACCESSORS = {'measurement','error','integral','command','actuator','state','parameter'}


class Expression:
    def __init__(self, source, *, accessors=None, names=None, label='Controller'):
        self.label=label
        accessors=ACCESSORS if accessors is None else set(accessors)
        names={'speed','density','time','pi'} if names is None else set(names)
        if not isinstance(source,str) or not source.strip() or len(source)>4096:
            raise AnalysisError(f'{label} expression must contain 1–4096 characters.')
        try:tree=ast.parse(source,mode='eval')
        except (SyntaxError,RecursionError) as exc:raise AnalysisError(f'Invalid {label.lower()} expression.') from exc
        if sum(1 for _ in ast.walk(tree))>512:raise AnalysisError(f'{label} expression is too complex.')
        self.references=[];self.nonsmooth=False
        def compile_node(node):
            if isinstance(node,ast.Constant) and type(node.value) in (float,int):
                try:value=float(node.value)
                except (ValueError,OverflowError) as exc:raise AnalysisError(f'{label} constants must be finite.') from exc
                if not np.isfinite(value):raise AnalysisError(f'{label} constants must be finite.')
                return lambda env:value
            if isinstance(node,ast.Name) and node.id in names:
                return lambda env:env[node.id]
            if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
                f=compile_node(node.operand)
                return (lambda env:-f(env)) if isinstance(node.op,ast.USub) else f
            if isinstance(node,ast.BinOp) and type(node.op) in BINARY:
                a,b,op=compile_node(node.left),compile_node(node.right),BINARY[type(node.op)]
                return lambda env:op(a(env),b(env))
            if isinstance(node,ast.Compare) and len(node.ops)==1 and type(node.ops[0]) in COMPARE:
                self.nonsmooth=True
                a,b,op=compile_node(node.left),compile_node(node.comparators[0]),COMPARE[type(node.ops[0])]
                return lambda env:op(a(env),b(env))
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and not node.keywords:
                name=node.func.id
                if name in accessors and len(node.args)==1 and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
                    key=node.args[0].value;self.references.append((name,key))
                    return lambda env:env[name][key]
                if name in FUNCTIONS and len(node.args)==FUNCTIONS[name][1]:
                    args=[compile_node(a) for a in node.args];fn=FUNCTIONS[name][0]
                    self.nonsmooth |= name in ('abs','minimum','maximum','atan2')
                    return lambda env:fn(*(a(env) for a in args))
                if name=='where' and len(node.args)==3:
                    self.nonsmooth=True
                    condition,a,b=[compile_node(n) for n in node.args]
                    return lambda env:a(env) if condition(env) else b(env)
                if name=='clip' and len(node.args)==3:
                    self.nonsmooth=True
                    a,lo,hi=[compile_node(n) for n in node.args]
                    def clipped(env):
                        low,high=lo(env),hi(env)
                        if low>high:raise AnalysisError(f'{label} clip lower bound exceeds its upper bound.')
                        return np.clip(a(env),low,high)
                    return clipped
            raise AnalysisError(f'Unsupported {label.lower()} expression syntax or function; references need literal names.')
        try:self.function=compile_node(tree.body)
        except RecursionError as exc:raise AnalysisError(f'{label} expression nesting is too deep.') from exc

    def __call__(self, env):
        try:
            with np.errstate(all='ignore'):value=float(self.function(env))
        except (ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError) as exc:
            raise AnalysisError(f'{self.label} expression could not be evaluated: {exc}') from exc
        if not np.isfinite(value):raise AnalysisError(f'{self.label} expression produced a nonfinite value; check its domain and physical units.')
        return value


def check_sides(base, minus, plus, minus2, plus2, step):
    """Compare one-sided second-order slopes of complete control residuals.

Testing the composite residual permits smooth cancellations such as abs(x)^2.
The test is local and step-dependent; it does not certify a global smooth law.
"""
    left=(3*base-4*minus+minus2)/(2*step)
    right=(-3*base+4*plus-plus2)/(2*step)
    if np.any(abs(left-right)>1e-7+2e-3*np.maximum(abs(left),abs(right))):
        raise AnalysisError('Custom controller has inconsistent one-sided tangents at this base or difference step; move away from a switching boundary or refine the difference step.')
