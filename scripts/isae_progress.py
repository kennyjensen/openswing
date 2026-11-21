"""Timestamp ISAE pass-count changes and regenerate standalone progress plots.

ISAE_STATUS.md remains the human-edited source. No tests or physics run here.
Counts describe their declared comparison scopes, not whole-family validation.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = [f'{prefix}-{i}' for prefix,n in [('SA',15),('UA',2),('P',5),('AP',2),('ST',6),('AE',7),('FFWT',5)]
            for i in range(1,n+1) if (prefix,i)!=('SA',9)]
FRACTION = re.compile(r'(?<![\d.,])(\d[\d,]*)/(\d[\d,]*)(?![\d.,])')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def atomic_write(path, text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd, temporary=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name+'.')
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write(text);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def write_json(path,value):
    atomic_write(path,json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def parse_status(text, config):
    if config.get('version')!=1:raise ValueError('Unknown progress scope format')
    rows={}
    for line in text.splitlines():
        if not re.match(r'^\| \[(?:SA|UA|P|AP|ST|AE|FFWT)-\d+\]',line):continue
        cells=[s.strip() for s in line.split('|')[1:-1]]
        if len(cells)!=5:raise ValueError('Expected five ISAE status table columns')
        match=re.fullmatch(r'\[([A-Z]+-\d+)\]\(([^)]+)\)',cells[0])
        if not match:raise ValueError('Invalid case link')
        key=match[1]
        if key in rows:raise ValueError('Duplicate case '+key)
        rows[key]=(cells,match[2])
    if set(rows)!=set(EXPECTED)|{'SA-9'}:raise ValueError('ISAE status must retain all 42 rows; SA-9 alone is excluded')
    if set(config['overrides'])-set(EXPECTED):raise ValueError('Unknown configured case')
    cases=[]
    for key in EXPECTED:
        cells,evidence=rows[key];rule=config['overrides'].get(key,{})
        fractions=[tuple(int(n.replace(',','')) for n in m) for m in FRACTION.findall(cells[2])]
        scope=rule.get('scope','Primary archived comparison in ISAE_STATUS.md')
        if rule.get('no_native_target'):
            passed=total=None;basis='no_native_target';acceptance='No native comparison'
        elif not fractions:
            if cells[2]!='Not registered':raise ValueError('Missing count for '+key+'; declare its scope explicitly')
            passed=total=None;basis='unregistered';acceptance='Not yet registered'
        else:
            if len(fractions)>1 and 'indices' not in rule:raise ValueError('Multiple scopes need an explicit selection for '+key)
            selected=rule.get('indices',[0])
            if len(set(selected))!=len(selected) or not selected or any(i<0 or i>=len(fractions) for i in selected):
                raise ValueError('Invalid scope selection for '+key)
            for p,n in fractions:
                if not 0<=p<=n or n<=0:raise ValueError('Invalid pass fraction for '+key)
            passed=sum(fractions[i][0] for i in selected);total=sum(fractions[i][1] for i in selected)
            basis='native'
            acceptance=rule.get('acceptance', 'Historical 3%' if 'Historical 3%' in cells[2] else
                'Original historical thresholds' if 'Historical original' in cells[2] else
                '5%' if '5%' in cells[2] else 'Original reference thresholds')
        cases.append(dict(id=key,name=cells[1],passed=passed,total=total,
            percent=100*passed/total if total else None,basis=basis,scope=scope,
            acceptance=acceptance,evidence=evidence,status_fraction=cells[2]))
    return cases


def signature(cases):
    return [{k:c[k] for k in ('id','passed','total','basis','scope','acceptance')} for c in cases]


def totals(cases):
    scored=[c for c in cases if c['total'] is not None]
    passed=sum(c['passed'] for c in scored);required=sum(c['total'] for c in scored)
    return dict(case_average_percent=sum(c['percent'] or 0 for c in cases)/len(cases),
        pooled_percent=100*passed/required if required else None,passed=passed,total=required,
        cases=len(cases),cases_with_counts=len(scored),unscored_cases=len(cases)-len(scored))


def read_history(path):
    if not path.exists():return dict(version=1,events=[])
    history=json.loads(path.read_text())
    if history.get('version')!=1:raise ValueError('Unknown history version')
    previous=None;last_time=None
    for event in history['events']:
        body={k:v for k,v in event.items() if k!='id'}
        if event['id']!=digest(body) or event['previous']!=previous:raise ValueError('Progress history integrity failure')
        timestamp=datetime.fromisoformat(event['timestamp'])
        if timestamp.tzinfo is None or last_time and timestamp<=last_time:raise ValueError('History timestamps must increase in UTC')
        if [c['id'] for c in event['cases']]!=EXPECTED or event['overall']!=totals(event['cases']):
            raise ValueError('History accounting differs')
        previous=event['id'];last_time=timestamp
    return history


def record(history,cases,*,timestamp,reason,source_sha256,scopes_sha256):
    events=history['events'];previous=events[-1] if events else None
    if previous and signature(previous['cases'])==signature(cases):return None
    when=datetime.fromisoformat(timestamp)
    if when.tzinfo is None:raise ValueError('Timestamp requires a timezone')
    when=when.astimezone(timezone.utc)
    if previous and when<=datetime.fromisoformat(previous['timestamp']):raise ValueError('New timestamp must follow the previous observation')
    old={c['id']:c for c in previous['cases']} if previous else {}
    changes=[dict(case=c['id'],before={k:old[c['id']][k] for k in ('passed','total','scope','acceptance')} if c['id'] in old else None,
                  after={k:c[k] for k in ('passed','total','scope','acceptance')})
             for c in cases if c['id'] not in old or signature([old[c['id']]])!=signature([c])]
    event=dict(timestamp=when.isoformat(timespec='microseconds').replace('+00:00','Z'),reason=reason,
        source_sha256=source_sha256,scopes_sha256=scopes_sha256,previous=previous['id'] if previous else None,
        changes=changes,cases=cases,overall=totals(cases))
    event['id']=digest(event);events.append(event)
    return event


def count_label(case):
    return f"{case['passed']:,}/{case['total']:,} · {case['percent']:.2f}%" if case['total'] else (
        'No native target' if case['basis']=='no_native_target' else 'Not registered')


def render_identity(history,root):
    return dict(revision=history['events'][-1]['id'],generator=digest(Path(__file__).read_text()),
                palette=digest((root/'web/plot-colors.js').read_text()))


def generated_files(destination):
    return [destination/name for name in ('overall.svg','overall.png','overall-mobile.svg','all-cases.svg','all-cases.png',
                                          'data.json','history.csv','index.html')]+[
        destination/'cases'/(key+'.svg') for key in EXPECTED]


def render(history,destination,root):
    # Plotting imports are deliberately absent from the unchanged-status path.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    events=history['events'];latest=events[-1];cases=latest['cases']
    destination.mkdir(parents=True,exist_ok=True);(destination/'cases').mkdir(exist_ok=True)
    palette=re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',(root/'web/plot-colors.js').read_text(),re.S)
    colors=re.findall(r'#[0-9a-fA-F]{6}',palette[1])
    families=list(dict.fromkeys(c['id'].split('-')[0] for c in cases))
    times=[datetime.fromisoformat(e['timestamp']) for e in events]
    start,end=times[0],times[-1];padding=max((end-start)*.04,timedelta(minutes=1))
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,
                         'svg.fonttype':'none','font.family':'DejaVu Sans'})
    def decorate(ax):
        ax.set_ylim(-3,103);ax.set_yticks([0,25,50,75,100]);ax.set_xlim(start-padding,end+padding)
        ax.grid(alpha=.18);locator=mdates.AutoDateLocator(minticks=2,maxticks=4,tz=timezone.utc)
        ax.xaxis.set_major_locator(locator);ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator,tz=timezone.utc))
        ax.set_ylabel('Passing (%)')
    def save(fig,path,png=False):
        fig.savefig(path.with_suffix('.svg'),bbox_inches='tight')
        if png:fig.savefig(path.with_suffix('.png'),dpi=130,bbox_inches='tight')
    fig,ax=plt.subplots(figsize=(10,3.4));decorate(ax)
    for field,label,color in [('case_average_percent','All 41 cases · equal weight',colors[0]),
                              ('pooled_percent','Known checks · pooled',colors[1])]:
        ax.step(times,[e['overall'][field] for e in events],where='post',marker='o',ms=4,color=color,label=label)
    ax.legend(loc='upper left',bbox_to_anchor=(0,1.2),ncol=2,frameon=False)
    ax.set_xlabel('Observation time (UTC)');save(fig,destination/'overall',True)
    fig.set_size_inches(5,3.4)
    ax.legend(loc='upper left',bbox_to_anchor=(0,1.25),ncol=1,frameon=False)
    save(fig,destination/'overall-mobile');plt.close(fig)
    grid,axes=plt.subplots(14,3,figsize=(15,30));axes=axes.flat
    for case,grid_ax in zip(cases,axes):
        key=case['id'];color=colors[families.index(key.split('-')[0])%len(colors)]
        values=[next(c['percent'] for c in e['cases'] if c['id']==key) for e in events]
        def draw(ax):
            decorate(ax)
            ax.step(times,[float('nan') if v is None else v for v in values],where='post',marker='o',ms=3,color=color)
            ax.set_title(key+'  '+count_label(case),loc='left',fontsize=10)
            if all(v is None for v in values):ax.text(.5,.5,count_label(case),transform=ax.transAxes,ha='center',color='#64748b')
        draw(grid_ax)
        fig,ax=plt.subplots(figsize=(4.5,2.2));draw(ax)
        save(fig,destination/'cases'/key);plt.close(fig)
    for ax in list(axes):ax.set_visible(False)
    grid.suptitle('ISAE native-reference passing checks · observation time (UTC)',fontsize=16)
    grid.tight_layout(rect=(0,0,1,.99));save(grid,destination/'all-cases',True);plt.close(grid)
    data=dict(version=1,updated=latest['timestamp'],revision=latest['id'],events=events)
    write_json(destination/'data.json',data)
    out=io.StringIO();writer=csv.writer(out)
    writer.writerow(['timestamp_utc','case','passed','total','percent','scope','acceptance','reason'])
    for event in events:
        for c in event['cases']:
            writer.writerow([event['timestamp'],c['id'],c['passed'],c['total'],c['percent'],c['scope'],c['acceptance'],event['reason']])
    atomic_write(destination/'history.csv',out.getvalue())
    atomic_write(destination/'index.html',dashboard(latest,events,families))
    write_json(destination/'rendered.json',render_identity(history,root))


def dashboard(latest,events,families):
    esc=html.escape;overall=latest['overall'];cards=[]
    def display_time(value):return datetime.fromisoformat(value).strftime('%Y-%m-%d %H:%M:%S UTC')
    for c in latest['cases']:
        cards.append(f'''<article data-family="{c['id'].split('-')[0]}"><h2>{c['id']} <span>{esc(c['name'])}</span></h2>
<img loading="lazy" src="cases/{c['id']}.svg?v={latest['id'][:12]}" alt="{c['id']}: {esc(count_label(c))}">
<p>{esc(c['scope'])}. {esc(c['acceptance'])}.</p></article>''')
    changes=[]
    for event in reversed(events[-30:]):
        details=[]
        for change in event['changes']:
            def pair(v):return 'unscored' if not v or v['total'] is None else f"{v['passed']:,}/{v['total']:,}"
            details.append(f"{change['case']}: {pair(change['before'])} → {pair(change['after'])}")
        changes.append(f"<li><time datetime=\"{esc(event['timestamp'])}\">{display_time(event['timestamp'])}</time> — {esc(event['reason'])}<p>{esc('; '.join(details))}</p></li>")
    options=''.join(f'<option>{f}</option>' for f in families)
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ISAE validation progress · OpenSwing</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f6fa;color:#172033;font:15px/1.5 system-ui,sans-serif}}main{{max-width:1400px;margin:auto;padding:24px}}
a{{color:#245cc1}}header p{{max-width:1000px}}h1{{margin:0;font-size:30px}}h2{{font-size:18px;margin:0 0 12px}}h2 span{{font-weight:400;font-size:14px;color:#536174}}
.stats{{display:flex;gap:16px;flex-wrap:wrap;margin:20px 0}}.stats div{{background:white;border:1px solid #dae0eb;border-radius:8px;padding:16px 22px;flex:1;min-width:200px}}
.stats strong{{font-size:28px;display:block}}.stats span,article p{{color:#536174}}section,article{{background:white;border:1px solid #dae0eb;border-radius:8px;padding:18px}}
img{{display:block;width:100%;height:auto}}.overall img{{max-width:1100px;margin:auto}}.toolbar{{display:flex;align-items:center;gap:16px;margin:24px 0 12px;flex-wrap:wrap}}select{{padding:8px;font:inherit}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,350px),1fr));gap:16px}}article p{{font-size:12px;margin-bottom:0}}article[hidden]{{display:none}}details{{margin:24px 0}}time{{font-family:monospace}}li p{{font-size:13px;color:#536174}}
@media(max-width:600px){{main{{padding:12px}}h1{{font-size:24px}}.stats{{gap:8px}}.stats div{{padding:12px;min-width:140px}}}}
</style><main><header><a href="/">← OpenSwing</a><h1>ISAE validation progress</h1>
<p>Passing native-reference checks over time. A point records when the status was observed, not when an older solve ran. Tracking begins {display_time(events[0]['timestamp'])}. No earlier progress is inferred.</p>
<p>Default allowance: <strong>5%</strong>. Historical rows keep their labeled thresholds until rescored. Passing comparisons does not by itself establish whole-case validation.</p></header>
<div class="stats"><div><strong>{overall['case_average_percent']:.2f}%</strong><span>All 41 cases, equally weighted</span></div>
<div><strong>{overall['pooled_percent']:.2f}%</strong><span>{overall['passed']:,}/{overall['total']:,} known checks</span></div>
<div><strong>{overall['cases_with_counts']}/41</strong><span>Cases with native counts</span></div></div>
<section class="overall"><h2>Overall progress</h2><picture><source media="(max-width:600px)" srcset="overall-mobile.svg?v={latest['id'][:12]}"><img src="overall.svg?v={latest['id'][:12]}" alt="Overall passing percentages versus UTC time"></picture>
<p>All-case progress averages the 41 case percentages, counting unscored cases as 0. Pooled progress divides known passing checks by known required checks; it excludes unknown denominators. SA-9 is absent upstream and excluded from both.</p>
<a href="overall.png" download>Overall PNG</a> · <a href="all-cases.svg" download>All cases SVG</a> · <a href="all-cases.png" download>All cases PNG</a> · <a href="history.csv" download>Timestamped CSV</a> · <a href="data.json" download>Full history JSON</a></section>
<div class="toolbar"><h2>Every case</h2><label>Family <select id="family"><option value="all">All</option>{options}</select></label><span>Latest observation: {display_time(latest['timestamp'])}</span></div>
<div class="grid">{''.join(cards)}</div><details><summary>Timestamped changes ({len(events)} observations)</summary><ol>{''.join(changes)}</ol></details>
<p>Source: ISAE_STATUS.md. Independent static scopes are combined for ST-5; alternate setups and computed-only subsets are kept separate. UA-1 and ST-6 analytical checks are not counted as native matches.</p>
</main><script>
const family=document.querySelector('#family');
function filter(){{document.querySelectorAll('article').forEach(el=>el.hidden=family.value!=='all'&&el.dataset.family!==family.value);history.replaceState(null,'','#'+family.value);}}
family.value=[...family.options].some(o=>o.value===location.hash.slice(1))?location.hash.slice(1):'all';filter();family.addEventListener('change',filter);
if(location.protocol!=='file:')setInterval(async()=>{{try{{const r=await fetch('rendered.json',{{cache:'no-store'}});if(!r.ok)return;const d=await r.json();if(d.revision!=={json.dumps(latest['id'])})location.reload();}}catch{{}}}},15000);
</script></html>'''


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(stream,fcntl.LOCK_UN)


def update(root=ROOT,*,reason='Status comparison counts changed',check=False):
    history_path=root/'docs/validation/isae-progress/history.json'
    status_path=root/'docs/validation/ISAE_STATUS.md';scopes_path=root/'docs/validation/isae-progress-scopes.json'
    destination=root/'public/isae-progress'
    with locked(history_path.with_suffix('.lock')):
        source=status_path.read_text();scopes=scopes_path.read_text()
        cases=parse_status(source,json.loads(scopes));history=read_history(history_path)
        if check:
            if not history['events'] or signature(history['events'][-1]['cases'])!=signature(cases):
                raise ValueError('Progress history is stale; run npm run isae:progress')
            rendered=json.loads((destination/'rendered.json').read_text())
            if rendered!=render_identity(history,root) or not all(p.is_file() for p in generated_files(destination)):
                raise ValueError('Plots are stale or missing')
            return dict(status='CURRENT',observations=len(history['events']))
        event=record(history,cases,timestamp=datetime.now(timezone.utc).isoformat(),reason=reason,
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),scopes_sha256=hashlib.sha256(scopes.encode()).hexdigest())
        if event:write_json(history_path,history)
        expected=render_identity(history,root)
        rendered=json.loads((destination/'rendered.json').read_text()) if (destination/'rendered.json').exists() else None
        if rendered!=expected or not all(p.is_file() for p in generated_files(destination)):render(history,destination,root)
        return dict(status='RECORDED' if event else 'UNCHANGED',observations=len(history['events']),
                    changed_cases=[] if event is None else [c['case'] for c in event['changes']],
                    overall=history['events'][-1]['overall'])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reason',default='Status comparison counts changed')
    ap.add_argument('--check',action='store_true')
    ap.add_argument('--watch',action='store_true',help='Lightweight one-second status-file watcher; no solver jobs')
    args=ap.parse_args()
    if args.check and args.watch:ap.error('--check and --watch are mutually exclusive')
    observed=None
    while True:
        watched=[ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/validation/isae-progress-scopes.json',Path(__file__),ROOT/'web/plot-colors.js']
        state=tuple((p.stat().st_mtime_ns,p.stat().st_size) for p in watched)
        if state!=observed:
            try:print(json.dumps(update(reason=args.reason,check=args.check)),flush=True);observed=state
            except Exception as exc:
                if not args.watch:raise
                print(f'Progress update failed: {exc}',flush=True);observed=state
        if not args.watch:break
        time.sleep(1)


if __name__=='__main__':main()
