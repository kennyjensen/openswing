/** Share one selection sequence across example, file-picker and drop reads. */
export function createAircraftLoader({inspect,showError}){
  let selection=0;
  return async function load(read){
    const current=++selection;
    try{
      const {source,filename,example=''}=await read();
      // A slower previous read must not replace a newer aircraft selection.
      if(current!==selection)return;
      await inspect(source,filename,example,null,false,true);
    }catch(error){
      if(current===selection)showError(error);
    }
  };
}
