const finite=value=>typeof value==='number'&&Number.isFinite(value);
const nodeFields=[...['z','x','y'].map(axis=>({value:`positions.${'xyz'.indexOf(axis)}`,label:`Position ${axis}`,unit:'input L',sampling:'nodes'})),
  ...['x','y','z'].map(axis=>({value:`rotations.${'xyz'.indexOf(axis)}`,label:`Rotation ${axis}`,unit:'rad',sampling:'nodes'}))];

export function structuralDerivativeOptions(result) {
  const options=nodeFields.map(field=>({...field}));
  for(const [key,field] of Object.entries(result?.section_output_fields??{})) {
    const components=field.components??[null];
    components.forEach((component,index)=>options.push({value:component===null?key:`${key}.${index}`,
      label:field.label+(component===null?'':` ${component}`),unit:field.unit,sampling:'sections',
      sampleLocation:field.sample_location??'material midpoint',axes:field.axes??'current local c,s,n'}));
  }
  return options;
}

export function structuralDerivativeSeries(result,beam,selection,column) {
  const field=structuralDerivativeOptions(result).find(field=>field.value===selection);
  if(!field)return null;
  const [key,component]=selection.split('.');
  const order=field.sampling==='nodes'?result.node_order:result.element_order;
  const points=(order??[]).flatMap((row,index)=>{
    if(row.beam!==Number(beam))return [];
    const matrix=result.matrices[key]?.[index];
    const values=component===undefined?matrix:matrix?.[Number(component)];
    return [{...row,values:result.parameters.map((_,i)=>finite(values?.[i])?values[i]:null),
      value:finite(values?.[column])?values[column]:null}];
  });
  return {...field,points,parameter:result.parameters[column]};
}

export function structuralDerivativeCSV(series,parameters) {
  const csv=row=>row.map(value=>'"'+String(value??'').replaceAll('"','""')+'"').join(',');
  return [csv(['beam','t','t0','t1','quantity','output unit','sample location',
    ...parameters.map(p=>`${p.name} / (${p.unit})`)]),
    ...series.points.map(p=>csv([p.beam,p.t,p.t0,p.t1,series.label,series.unit,
      series.sampling==='nodes'?'node':series.sampleLocation??'material midpoint',...p.values]))].join('\n')+'\n';
}
