/** Keep one set of controls and one viewer across desktop and mobile layouts. */
export function createResponsiveWorkbench({onLeavePlots=()=>{}}={}) {
  const $=id=>document.getElementById(id);
  const media=matchMedia('(max-width: 720px)');
  const desktop=$('desktop-workbench'),mobile=$('mobile-workbench'),nav=$('workspace-tabs');
  const actionBar=$('mobile-action-bar');
  new ResizeObserver(() => {
    document.documentElement.style.setProperty('--mobile-actions-height', `${actionBar.getBoundingClientRect().height}px`);
  }).observe(actionBar);
  const tabs=[...nav.querySelectorAll('[data-workspace]')];
  const details=[...desktop.querySelectorAll('[data-tab]')];
  const groups={
    editor:['editor'],
    plots:['loading','modes','time','frequency'],
    output:['report'],
  };
  const owner=Object.fromEntries(Object.entries(groups).flatMap(([group,names])=>names.map(name=>[name,group])));
  let activeWorkspace='plots';
  let activeDetail=details.find(tab=>tab.getAttribute('aria-selected')==='true')?.dataset.tab??'loading';
  let compact=false;
  const anchors=new Map();
  const scrollPositions=new Map();
  const panelStates=new Map();
  const availability=new Map();

  function setAvailable(values={}) {
    for(const [name,value] of Object.entries(values))availability.set(name,Boolean(value));
    for(const tab of details) {
      const enabled=availability.get(tab.dataset.tab)!==false;
      tab.disabled=!enabled;
      const card=$(`workspace-section-${tab.dataset.tab}`);
      if(!card)continue;
      const wasDisabled=card.getAttribute('aria-disabled')==='true';
      if(!enabled) {
        if(!wasDisabled)panelStates.set(card.id,card.open);
        card.open=false;
      }else if(wasDisabled)card.open=panelStates.get(card.id)??true;
      card.setAttribute('aria-disabled',String(!enabled));
      const summary=card.firstElementChild;
      summary.setAttribute('aria-disabled',String(!enabled));summary.tabIndex=enabled?0:-1;
      summary.onclick=event=>{if(!enabled)event.preventDefault();};
      summary.onkeydown=event=>{if(!enabled&&['Enter',' '].includes(event.key))event.preventDefault();};
    }
    if(details.find(tab=>tab.dataset.tab===activeDetail)?.disabled) {
      const next=details.find(tab=>owner[tab.dataset.tab]==='plots'&&!tab.disabled);
      if(next)activeDetail=next.dataset.tab;
    }
    syncDetails();
  }

  function move(node,destination) {
    if(!anchors.has(node)) {
      const anchor=document.createComment(`desktop:${node.id||node.className}`);
      node.before(anchor);anchors.set(node,anchor);
    }
    destination.append(node);
  }
  function panel(parent,name,text,className='') {
    const card=document.createElement('details');
    card.id=`workspace-section-${name}`;
    card.className=`workspace-card${className?' '+className:''}`;
    card.open=panelStates.get(card.id)??true;
    const title=document.createElement('summary');title.id=`heading-${name}`;
    title.textContent=text;card.append(title);parent.append(card);
    return card;
  }
  function showWorkspace(name,{remember=true,scroll=true}={}) {
    if(!tabs.some(tab=>tab.dataset.workspace===name))return;
    if(compact&&remember)scrollPositions.set(activeWorkspace,window.scrollY);
    if(compact&&activeWorkspace==='plots'&&name!=='plots')onLeavePlots();
    activeWorkspace=name;
    for(const tab of tabs) {
      const selected=tab.dataset.workspace===name;
      tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;
      $(tab.getAttribute('aria-controls')).hidden=!selected;
    }
    if(compact&&scroll)window.scrollTo({top:scrollPositions.get(name)??0,behavior:'instant'});
  }
  function syncDetails() {
    for(const tab of details) {
      const selected=tab.dataset.tab===activeDetail&&!tab.disabled;
      tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;
      const pane=$(`pane-${tab.dataset.tab}`);
      pane.hidden=compact?false:!selected;
      // In the stacked mobile view these are labelled sections, not separate tabs.
      pane.setAttribute('role',compact?'region':'tabpanel');
      pane.setAttribute('aria-labelledby',compact?(tab.dataset.tab==='editor'?'workspace-tab-editor':`heading-${tab.dataset.tab}`):tab.id);
    }
  }
  function selectDetail(tab) {
    if(tab.disabled)return;
    activeDetail=tab.dataset.tab;syncDetails();
    if(compact) {
      const card=$(`workspace-section-${activeDetail}`);
      if(card)card.open=true;
      showWorkspace(owner[activeDetail]);
    }
  }
  function keyboardTabs(event,items,select) {
    items=items.filter(tab=>!tab.disabled);
    const index=items.indexOf(event.target);
    if(index<0)return;
    const next=event.key==='Home'?0:event.key==='End'?items.length-1:
      event.key==='ArrowRight'?(index+1)%items.length:event.key==='ArrowLeft'?(index+items.length-1)%items.length:null;
    if(next===null)return;
    event.preventDefault();items[next].focus();select(items[next]);
  }
  for(const tab of tabs)tab.onclick=()=>showWorkspace(tab.dataset.workspace);
  nav.addEventListener('keydown',event=>keyboardTabs(event,tabs,tab=>showWorkspace(tab.dataset.workspace)));
  for(const tab of details)tab.onclick=()=>selectDetail(tab);
  desktop.querySelector('.tabbar').addEventListener('keydown',event=>keyboardTabs(event,details,selectDetail));

  function layout() {
    if(media.matches===compact)return;
    const focused=document.activeElement;
    const focusedCard=focused.closest('.workspace-card');
    compact=media.matches;
    if(compact) {
      if(focused.closest('#analysis-settings'))activeWorkspace='settings';
      else if(focused.closest('#model-configuration'))activeWorkspace='editor';
      else if(focused.closest('.results-panel'))activeWorkspace='output';
      else if(focused.closest('.tab-pane'))activeWorkspace=owner[focused.closest('.tab-pane').id.replace('pane-','')];
      else if(focused.matches('[data-tab]'))activeWorkspace=owner[focused.dataset.tab];
      move($('analysis-settings'),$('workspace-settings'));
      const plots=$('workspace-plots');
      const geometry=panel(plots,'aircraft','Aircraft','workspace-geometry');
      move(desktop.querySelector('.viewport-header'),geometry);
      move(desktop.querySelector('.viewport-container'),geometry);
      if($('flow-failure'))move($('flow-failure'),geometry);
      for(const id of ['time-transport','mode-transport','frequency-transport','solution-provenance'])move($(id),geometry);
      move(desktop.querySelector('.results-panel'),panel($('workspace-output'),'results','Total Forces'));
      for(const [group,names] of Object.entries(groups))for(const name of names) {
        if(group==='editor') {
          move($(`pane-${name}`),$('workspace-editor'));
          continue;
        }
        const card=panel($(`workspace-${group}`),name,details.find(tab=>tab.dataset.tab===name).textContent);
        move($(`pane-${name}`),card);
      }
      move($('analysis-actions'),$('mobile-action-bar'));
      desktop.hidden=true;mobile.hidden=false;nav.hidden=false;
      setAvailable();showWorkspace(activeWorkspace,{remember:false,scroll:false});
      if(activeWorkspace!=='plots')onLeavePlots();
      if(focused.matches('[data-tab]'))$(`workspace-tab-${activeWorkspace}`).focus({preventScroll:true});
    } else {
      for(const card of mobile.querySelectorAll('.workspace-card'))if(card.getAttribute('aria-disabled')!=='true')panelStates.set(card.id,card.open);
      for(const [node,anchor] of anchors){anchor.replaceWith(node);}
      anchors.clear();
      for(const card of mobile.querySelectorAll('.workspace-card'))card.remove();
      mobile.hidden=true;nav.hidden=true;desktop.hidden=false;syncDetails();
      if(focusedCard&&focused===focusedCard.firstElementChild) {
        const name=focusedCard.id.replace('workspace-section-','');
        const destination=name==='aircraft'?$('fit'):name==='results'?$('tab-report'):$(`tab-${name}`);
        if(destination.matches('[data-tab]'))selectDetail(destination);
        destination.focus({preventScroll:true});
      } else if(nav.contains(focused)) {
        const destination=activeWorkspace==='settings'?($('solution-type-panel').open?$('mode'):$('solution-type-panel').querySelector('summary')):activeWorkspace==='editor'?$('tab-editor'):
          activeWorkspace==='output'?$('tab-report'):$(`tab-${activeDetail}`);
        if(destination.matches('[data-tab]'))selectDetail(destination);
        destination.focus({preventScroll:true});
      }
    }
  }
  media.addEventListener('change',layout);
  syncDetails();
  layout();
  return {show:name=>{if(compact)showWorkspace(name);},current:()=>compact?activeWorkspace:null,setAvailable};
}
