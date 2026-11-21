import {PROJECT_LIMIT,emptyProject,parseProject,validateProject,projectName,changeCase,openProjectStore} from './project-data.js';
import {sealSolution,verifySolution} from './solution-data.js';
const $=id=>document.getElementById(id);
export const projectSettings=`
<details id="project-settings" class="advanced"><summary>Project & saved cases</summary>
  <p class="small muted">Save named cases with their ASW source, applied mesh, flight and analysis inputs, forcing, controller and loaded equilibrium. Saved cases stay in this browser; export a project to move or back them up. Update a case to retain changed inputs.</p>
  <label class="field-label" for="project-name">Project name</label><input id="project-name" type="text" maxlength="160" value="Untitled project">
  <div class="file-actions"><button id="project-rename" type="button">Set name</button><button id="project-open" type="button">Open project</button><button id="project-export" type="button">Export project</button><input id="project-file" type="file" accept=".json,application/json" hidden></div>
  <label class="field-label" for="project-cases">Saved cases</label><select id="project-cases" aria-label="Saved cases"></select>
  <div class="file-actions"><button id="project-load" type="button">Load case</button><button id="project-update" type="button">Update case</button><button id="project-undo-load" type="button" disabled>Undo load</button></div>
  <label class="field-label" for="project-case-name">Case name</label><input id="project-case-name" type="text" maxlength="160" placeholder="Cruise trim, gust response…">
  <div class="file-actions"><button id="project-add" type="button">Save as new case</button><button id="project-case-rename" type="button">Rename case</button><button id="project-delete" type="button">Remove case</button><button id="project-export-current" type="button">Export current case</button></div>
  <div class="file-actions"><button id="project-reload" type="button">Reload saved project</button><button id="project-undo" type="button">Undo project edit</button></div>
  <hr><label class="field-label" for="project-solutions">Computed solutions</label><select id="project-solutions" aria-label="Saved computed solutions"></select>
  <label class="field-label" for="project-solution-name">Solution name</label><input id="project-solution-name" type="text" maxlength="160" placeholder="Cruise results, flutter sweep…">
  <div class="file-actions"><button id="project-save-solution" type="button">Save computed solution</button><button id="project-load-solution" type="button">Open solution</button><button id="project-rename-solution" type="button">Rename solution</button><button id="project-delete-solution" type="button">Remove solution</button></div>
  <p class="small muted">Solutions retain their inputs, complete computed results, supplementary ROM/sweep/flow data and numerical version. Open solution restores saved values without recalculation. Project export includes every saved solution. Cases remain editable input presets; updating or removing a case leaves solutions intact.</p>
  <p id="project-status" class="small muted" role="status">Reading saved cases…</p>
  <p class="small muted">Load case restores inputs and clears computed results. Open solution restores saved results too. Undo load reverses the latest load. Apply ASW, beam-property and node edits first. Opening a project changes the saved lists; choose a case or solution to load afterward. This JSON format does not read ASWING .set, .pnt or binary .state files.</p>
</details>`;

export function createProjectSettings({capture,load,validate,captureSolution,serializeSolution=async value=>value,loadSolution,hasSolution,download,showError,isBusy}){
  let project=emptyProject(),store=null,revision=0,busy=false,serial=0,previous=null,undoWorkspace=null,storageMessage='';
  function message(value){$('project-status').textContent=value;}
  function render(){
    $('project-name').value=project.name;const select=$('project-cases');select.replaceChildren();
    if(!project.cases.length){const o=document.createElement('option');o.value='';o.textContent='No cases saved';select.append(o);}
    for(const c of project.cases){const o=document.createElement('option');o.value=c.id;o.textContent=c.name;select.append(o);}
    select.value=project.selected??'';$('project-case-name').value=project.cases.find(c=>c.id===project.selected)?.name??'';
    const solutions=$('project-solutions');solutions.replaceChildren();
    for(const s of project.solutions){const o=document.createElement('option');o.value=s.id;o.textContent=`${s.name} · ${s.kind}`;solutions.append(o);}
    solutions.value=project.selected_solution??'';$('project-solution-name').value=project.solutions.find(s=>s.id===project.selected_solution)?.name??'';refresh();
  }
  function refresh(){
    const disabled=busy||isBusy();for(const e of $('project-settings').querySelectorAll('input,select,button'))e.disabled=disabled;
    for(const id of ['project-load','project-update','project-case-rename','project-delete'])$(id).disabled=disabled||!project.selected;
    $('project-undo-load').disabled=disabled||!undoWorkspace;
    $('project-reload').disabled=disabled||!store;
    $('project-undo').disabled=disabled||(!store&&!previous);
    $('project-save-solution').disabled=disabled||!hasSolution();
    for(const id of ['project-load-solution','project-rename-solution','project-delete-solution'])$(id).disabled=disabled||!project.selected_solution;
  }
  async function checkedProject(candidate){
    const clean=validateProject(candidate);for(const c of clean.cases)validate(c.configuration);
    for(const s of clean.solutions){validate(s.configuration);await verifySolution(s);}
    return clean;
  }
  async function commit(candidate,label){
    const clean=await checkedProject(candidate);
    if(store){const record=await store.write(clean,revision);revision=record.revision;}
    previous=project;project=clean;render();message(label+(store?' Saved in this browser.':' Memory only. Export the project to keep it.'));
  }
  async function action(fn){if(busy||isBusy())return;busy=true;refresh();try{await fn();}catch(error){message(error.message);showError(error);}finally{busy=false;refresh();}}
  function selected(){const c=project.cases.find(c=>c.id===$('project-cases').value);if(!c)throw new Error('Select a saved case.');return c;}
  $('project-add').onclick=()=>action(async()=>{const configuration=capture();await commit(changeCase(project,'add',{id:crypto.randomUUID(),name:$('project-case-name').value,configuration}),'New case saved.');});
  $('project-update').onclick=()=>action(async()=>{const c=selected(),configuration=capture();await commit(changeCase(project,'update',{id:c.id,configuration}),'Case updated.');});
  $('project-case-rename').onclick=()=>action(async()=>{await commit(changeCase(project,'rename',{id:selected().id,name:$('project-case-name').value}),'Case renamed.');});
  $('project-delete').onclick=()=>action(async()=>{await commit(changeCase(project,'delete',{id:selected().id}),'Case removed. Undo project edit restores it.');});
  $('project-rename').onclick=()=>action(async()=>{await commit({...project,name:projectName($('project-name').value)},'Project renamed.');});
  const solution=()=>{const s=project.solutions.find(s=>s.id===$('project-solutions').value);if(!s)throw new Error('Select a computed solution.');return s;};
  $('project-save-solution').onclick=()=>action(async()=>{
    const saved=await sealSolution({...await serializeSolution(captureSolution()),id:crypto.randomUUID(),name:projectName($('project-solution-name').value),created_at:new Date().toISOString()});
    await commit({...project,solutions:[...project.solutions,saved],selected_solution:saved.id},'Computed solution saved.');
  });
  $('project-solutions').onchange=()=>action(async()=>{try{await commit({...project,selected_solution:solution().id},'Solution selected. Open it to display saved results.');}catch(error){render();throw error;}});
  $('project-load-solution').onclick=()=>action(async()=>{
    const saved=solution(),backup=capture(),previousResult=hasSolution()?captureSolution():null;
    await loadSolution(saved);undoWorkspace={configuration:backup,solution:previousResult};message(`Opened ${saved.name}. Displaying saved results without recomputation.`);
  });
  $('project-rename-solution').onclick=()=>action(async()=>{const id=solution().id,name=projectName($('project-solution-name').value);await commit({...project,solutions:project.solutions.map(s=>s.id===id?{...s,name}:s)},'Solution renamed.');});
  $('project-delete-solution').onclick=()=>action(async()=>{const id=solution().id,solutions=project.solutions.filter(s=>s.id!==id);await commit({...project,solutions,selected_solution:solutions[0]?.id??null},'Solution removed. Undo project edit restores it.');});
  $('project-cases').onchange=()=>action(async()=>{const id=$('project-cases').value;try{await commit(changeCase(project,'select',{id}),'Case selected. Load it to restore the workbench.');}catch(error){render();throw error;}});
  $('project-load').onclick=()=>action(async()=>{const c=selected(),backup=capture();await load(c.configuration);undoWorkspace={configuration:backup,solution:null};message(`Loaded ${c.name}. Run analysis to compute new results.`);});
  $('project-undo-load').onclick=()=>action(async()=>{if(!undoWorkspace)return;const current={configuration:capture(),solution:hasSolution()?captureSolution():null};await load(undoWorkspace.configuration,undoWorkspace.solution);undoWorkspace=current;message('Previous workbench inputs restored.');});
  $('project-export').onclick=()=>{try{download('openswing-project.json',JSON.stringify(validateProject(project),null,2)+'\n','application/json');message('Exported saved cases and computed solutions. Save or update records before exporting changed workbench data.');}catch(error){showError(error);}};
  $('project-export-current').onclick=()=>action(async()=>{
    const one=changeCase({...emptyProject(),name:projectName($('project-name').value)},'add',{id:crypto.randomUUID(),name:$('project-case-name').value.trim()||'Current inputs',configuration:capture()});
    download('openswing-case.json',JSON.stringify(one,null,2)+'\n','application/json');message('Current inputs exported as a one-case project. The saved case list is unchanged.');
  });
  $('project-open').onclick=()=>$('project-file').click();
  $('project-file').onchange=event=>{const file=event.target.files[0],token=++serial;event.target.value='';if(!file)return;action(async()=>{
    if(file.size>PROJECT_LIMIT)throw new Error('Project exceeds the 64 MiB file limit.');const candidate=parseProject(await file.text());if(token!==serial)return;
    await commit(candidate,'Project opened. Load a case to restore its inputs.');
  });};
  $('project-reload').onclick=()=>action(async()=>{const record=await store.read(),clean=record?await checkedProject(record.project):emptyProject();project=clean;revision=record?.revision??0;render();message('Saved project reloaded. Workbench inputs are unchanged.');});
  $('project-undo').onclick=()=>action(async()=>{
    if(store){const record=await store.undo(revision,checkedProject);project=record.project;revision=record.revision;}
    else {if(!previous)throw new Error('No previous project edit is available.');const current=project;project=previous;previous=current;}
    render();message('Previous project restored. Workbench inputs are unchanged.');
  });
  async function start(){busy=true;refresh();try{store=await openProjectStore();const record=await store.read();revision=record?.revision??0;project=record?await checkedProject(record.project):emptyProject();
      message(project.cases.length||project.solutions.length?`${project.name} · ${project.cases.length} saved cases · ${project.solutions.length} computed solutions. Load a case or open a solution to restore it.`:'Save the current inputs as a named case to start a project.');
    }catch(error){storageMessage=error.message;message(storageMessage+' Export projects to keep portable copies.');}
    finally{busy=false;render();}
  }
  render();return {start,refresh};
}
