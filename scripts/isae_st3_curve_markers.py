"""Read Cairo EPS data markers without executing PostScript.

The old reader provides the visually reviewed axes. Marker shapes supply
sample centers; simplified lines and clipping intersections are not samples.
The 0.01 plot-unit coordinate envelope is declared before any solver run.
"""
import re

NUMBER = r'[-+]?(?:\d+\.?\d*|\.\d+)'
PAIR = rf'({NUMBER})\s+({NUMBER})'
POINT = rf'{PAIR}\s+([ml])'
TRANSFORM = r'q 1 0 0 -1 0 0 cm\s+(.*?)\s+S Q'
PIXEL_ENVELOPE = .01
LAYUPS = ('0_3_90', 'p15_0', 'm15_0')


def marker_centers(text):
    """Filled squares, diamonds and circles; exclude outlines and lines."""
    rows=[]
    for match in re.finditer(rf'{PAIR}\s+({NUMBER})\s+({NUMBER})\s+re\s+f\b',text):
        x,y,w,h=map(float,match.groups())
        if abs(w-6)<.002 and abs(h-6)<.002:
            rows.append(dict(x=x+w/2,y=y+h/2,kind='square',offset=match.start()))
    diamond=rf'{PAIR}\s+m\s+{PAIR}\s+l\s+{PAIR}\s+l\s+{PAIR}\s+l\s+h\s+{PAIR}\s+m\s+f\b'
    for match in re.finditer(diamond,text):
        values=list(map(float,match.groups()));points=list(zip(values[::2],values[1::2]))
        assert points[0]==points[-1]
        xs,ys=zip(*points[:4]);w=max(xs)-min(xs);h=max(ys)-min(ys)
        if abs(w-8)<.01 and abs(h-10.64)<.02:
            rows.append(dict(x=(min(xs)+max(xs))/2,y=(min(ys)+max(ys))/2,
                             kind='diamond',offset=match.start()))
    cubic=rf'(?:{NUMBER}\s+){{6}}c\s*'
    circle=rf'{NUMBER}\s+{NUMBER}\s+m\s+(?:{cubic}){{4}}f\b'
    for match in re.finditer(circle,text):
        values=list(map(float,re.findall(NUMBER,match.group())))
        xs,ys=values[::2],values[1::2]
        if abs(max(xs)-min(xs)-8)<.01 and abs(max(ys)-min(ys)-8)<.01:
            rows.append(dict(x=(min(xs)+max(xs))/2,y=(min(ys)+max(ys))/2,
                             kind='circle',offset=match.start()))
    return sorted(rows,key=lambda row:row['offset'])


def extract(text, figure):
    colors=list(re.finditer(r'(?m)^((?:[-\d.]+ ){2}[-\d.]+ rg|[-\d.]+ g)\s*$',text))
    curves=[]
    for k,color in enumerate(colors):
        if color[1]!='1 0 0 rg':continue
        end=colors[k+1].start() if k+1<len(colors) else len(text)
        segment=text[color.end():end]
        paths=[]
        for match in re.finditer(TRANSFORM,segment,re.S):
            content=match[1];points=re.findall(POINT,content)
            if len(points)<2 or re.sub(POINT,'',content).strip():continue
            assert points[0][2]=='m' and all(p[2]=='l' for p in points[1:])
            paths.append((match,[(float(p[0]),-float(p[1])) for p in points]))
        for j,(match,vertices) in enumerate(paths):
            hits=[]
            for i,axis in enumerate(figure['axes']):
                x,y,w,h=axis['rectangle']
                if all(x-.1<=px<=x+w+.1 and y-.1<=py<=y+h+.1 for px,py in vertices):hits.append(i)
            if not hits:continue  # Legend strokes lie outside data axes.
            assert len(hits)==1
            axis=figure['axes'][hits[0]];x,y,w,h=axis['rectangle']
            following=paths[j+1][0].start() if j+1<len(paths) else len(segment)
            markers=marker_centers(segment[match.end():following]);assert markers
            markers=[m for m in markers if x-PIXEL_ENVELOPE<=m['x']<=x+w+PIXEL_ENVELOPE
                     and y-PIXEL_ENVELOPE<=m['y']<=y+h+PIXEL_ENVELOPE]
            assert markers and len({m['kind'] for m in markers})==1
            scale,offset=axis['y_affine'];samples=[]
            for m in markers:
                samples.append(dict(**m,
                    plotted_load=(m['x']-x)/w*figure['x_range'][1],
                    expected=scale*m['y']+offset,
                    x_tolerance=PIXEL_ENVELOPE/w*figure['x_range'][1],
                    original_absolute_tolerance=abs(scale)*PIXEL_ENVELOPE+axis['max_tick_fit_error'],
                    source_line=text[:color.end()+match.end()+m['offset']].count('\n')+1))
            assert len({(r['x'],r['y']) for r in samples})==len(samples)
            name=LAYUPS[hits[0] if len(figure['axes'])==3 else len(curves)]
            curves.append(dict(name=name,axis=hits[0],samples=samples,
                stroke_vertices=vertices,source_line=text[:color.end()+match.start()].count('\n')+1))
    assert len(curves)==3 and [c['name'] for c in curves]==list(LAYUPS)
    return dict(kind=figure['kind'],quantity=figure['quantity'],axes=figure['axes'],
                x_range=figure['x_range'],pixel_envelope=PIXEL_ENVELOPE,curves=curves)
