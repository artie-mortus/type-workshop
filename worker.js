importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js');
let engine,initializing;
async function getEngine(){
 if(!initializing)initializing=(async()=>{
  postMessage({status:'Loading browser Python and fontTools…'});
  const loaded=await loadPyodide();
  // engine.py carries the same release version as this worker.
  const [, response]=await Promise.all([
   loaded.loadPackage(['fonttools','brotli']),
   fetch(new URL('./engine.py'+location.search,location.href)),
  ]);
  if(!response.ok)throw Error(`Cannot load engine.py (HTTP ${response.status})`);
  loaded.runPython(await response.text());
  return loaded;
 })().catch(error=>{initializing=null;throw error});
 return initializing;
}
// Pyodide errors include a Python traceback; show its final exception to the user.
function processingError(error) {
 const lines=String(error.message||error).trim().split('\n');
 return lines.at(-1).replace(/^(?:[\w.]*Error|Exception):\s*/, '');
}
onmessage=async({data:m})=>{try{engine=await getEngine();engine.globals.set('input_bytes',m.bytes);if(m.type==='inspect'){postMessage({id:m.id,meta:JSON.parse(engine.runPython('inspect(input_bytes)'))})}else{engine.globals.set('options',JSON.stringify(m.options));let result=engine.runPython('generate(input_bytes,options)');let bytes=result.toJs();result.destroy();postMessage({id:m.id,bytes},[bytes.buffer])}}catch(e){postMessage({id:m.id,error:processingError(e)})}};
