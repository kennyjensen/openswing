// Source-local Weight edits. The numerical kernel still validates the edited
// ASW document before it is committed; no mass or inertia physics lives here.
const split=line=>{const i=line.search(/[!#%\r\n]/);return i<0?[line,'']:[line.slice(0,i),line.slice(i)];};
function number(token){
  let value=Number(token.replace(/[dD]/g,'e'));
  if(!Number.isFinite(value))value=Number(token.replace(/^([+-]?(?:\d+(?:\.\d*)?|\.\d+))([+-]\d+)$/,'$1e$2'));
  if(!Number.isFinite(value))throw new Error('Invalid number in Weight block.');return value;
}
const tokens=code=>[...code.matchAll(/[^\s,]+/g)];
const defaults=value=>Array(17).fill(value);
export function weightRecords(source){
  const lines=source.match(/[^\r\n]*(?:\r\n|\r|\n|$)/g).filter(Boolean),records=[];
  let block=null,multiply=defaults(1),add=defaults(0),label='';
  for(let line=0;line<lines.length;line++){
    const [code,tail]=split(lines[line]),body=code.trim(),key=body.split(/\s/)[0].toLowerCase();
    if(!body){if(block==='weight'&&/^[!#%]/.test(tail)){const note=tail.replace(/^[!#%]+/,'').trim();if(note&&!/^(?:[-=]+|Nbeam\b)/i.test(note))label=note;}continue;}
    if(key==='end'){block=null;continue;}
    if(block===null){block=key;multiply=defaults(1);add=defaults(0);label='';continue;}
    if(block!=='weight')continue;
    if(body[0]==='*'||body[0]==='+'){
      const values=tokens(body.slice(1)).map(t=>number(t[0])),target=defaults(body[0]==='*'?1:0);
      values.forEach((v,i)=>target[i+1]=v);if(body[0]==='*')multiply=target;else add=target;continue;
    }
    const fields=tokens(code),values=defaults(0);
    if(fields.length<6||fields.length>17)throw new Error('A Weight row needs 6–17 values.');
    fields.forEach((t,i)=>values[i]=number(t[0])*multiply[i]+add[i]);
    records.push({line,values,multiply:[...multiply],add:[...add],label:label||`Point mass ${records.length+1}`});label='';
  }
  return {lines,records};
}
const encode=(value,multiply,add)=>{
  if(multiply===0)return value===add?0:null;
  const raw=(value-add)/multiply;
  return Number.isFinite(raw)&&Math.abs(raw*multiply+add-value)<=16*Number.EPSILON*Math.max(Math.abs(value),1)?raw:null;
};

export function editWeight(source,index,changes){
  const {lines,records}=weightRecords(source),record=records[index];
  if(!record)throw new Error('Select a point mass.');
  const values=[...record.values];
  for(const [column,value] of Object.entries(changes)){
    const i=Number(column);
    if(!Number.isInteger(i)||i<0||i>16||!Number.isFinite(value)||(i===0&&!Number.isInteger(value)))throw new Error('Enter finite mass properties and a valid beam.');
    values[i]=value;
  }
  if(values.every((v,i)=>v===record.values[i]))return source;
  let [code,tail]=split(lines[record.line]);const fields=tokens(code);
  const last=Math.max(fields.length-1,...Object.keys(changes).map(Number));
  const raw=values.slice(0,last+1).map((v,i)=>encode(v,record.multiply[i],record.add[i]));
  if(raw.some(v=>v===null)){
    // A zero multiplier cannot encode a changed value. Isolate this row with
    // identity scaling, then restore the original directives for later rows.
    const nl=source.includes('\r\n')?'\r\n':'\n';
    const directive=(kind,a)=>kind+' '+a.slice(1).join(' ')+nl;
    lines[record.line]=directive('*',defaults(1))+directive('+',defaults(0))+
      values.slice(0,last+1).join(' ')+tail+(tail.endsWith('\n')||tail.endsWith('\r')?'':nl)+
      directive('*',record.multiply)+directive('+',record.add);
  }else{
    for(let i=fields.length-1;i>=0;i--){
      if(!(i in changes)||values[i]===record.values[i])continue;
      const field=fields[i];code=code.slice(0,field.index)+String(raw[i]).padStart(field[0].length)+code.slice(field.index+field[0].length);
    }
    if(last>=fields.length)code+=' '+raw.slice(fields.length).join(' ');
    lines[record.line]=code+tail;
  }
  return lines.join('');
}

export function deleteWeight(source,index){
  const {lines,records}=weightRecords(source),row=records[index];if(!row)throw new Error('Select a point mass.');
  const [,tail]=split(lines[row.line]);lines[row.line]=/^[!#%]/.test(tail)?tail:'';
  return lines.join('');
}
export function appendWeight(source,{beam,t,position}){
  if(!Number.isInteger(beam)||!Number.isFinite(t)||position.length!==3||!position.every(Number.isFinite))throw new Error('Choose a valid beam and point position.');
  // A separate block has identity scaling and leaves every existing row and
  // annotation untouched. Multiple Weight blocks are part of the ASW format.
  const nl=source.includes('\r\n')?'\r\n':'\n';
  return source+(source.endsWith('\n')?'':nl)+nl+'Weight'+nl+[beam,t,...position,0].join(' ')+nl+'End'+nl;
}

export function massDisplayUnits(model){
  const g=model.constants?.[0],si=model.si;
  const metric=Number.isFinite(si?.M)&&si.M>0&&Number.isFinite(si?.L)&&si.L>0;
  const mass=metric?si.M:1,length=metric?si.L:1;
  return {mass,length,massLabel:metric?'kg':'input M',lengthLabel:metric?'m':'input L',inertiaLabel:metric?'kg·m²':'input M·L²',
    factor:column=>column===5?mass/g:column>=11?mass*length**2/g:column>=2&&column<=4?length:1};
}
