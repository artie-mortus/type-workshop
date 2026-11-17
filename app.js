const $=id=>document.getElementById(id);
// Keep the worker on the same release as this entry script.
const workerURL=new URL('./worker.js'+new URL(import.meta.url).search,import.meta.url);
let worker;
let original,meta,result,loadId=0,revision=0,timer,busy=false,pending=false;const jobs=new Map();let serial=0;
const themeColors={dark:'#e0e7f4',light:'#243452'};
function setTheme(theme,save=false,initial=false){
 const previous=document.documentElement.dataset.theme;
 document.documentElement.dataset.theme=theme;
 $('theme-switch').setAttribute('aria-checked',String(theme==='dark'));
 $('theme-label').textContent=theme==='dark'?'Dark':'Light';
 if(initial||$('color').value===themeColors[previous])$('color').value=themeColors[theme];
 if(save){try{localStorage.setItem('type-workshop-theme',theme)}catch{}preview()}
}
setTheme(document.documentElement.dataset.theme,false,true);
$('theme-switch').onclick=()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark',true);
window.addEventListener('storage',event=>{if(event.key==='type-workshop-theme'){setTheme(event.newValue==='light'?'light':'dark');preview()}});
function createWorker(){
 const active=new Worker(workerURL);
 active.onmessage=({data:d})=>{if(d.status){status(d.status);return}let j=jobs.get(d.id);if(!j)return;jobs.delete(d.id);d.error?j.reject(Error(d.error)):j.resolve(d)};
 active.onerror=e=>{
  e.preventDefault();active.terminate();worker=null;
  const error=Error('Processing engine failed: '+e.message);
  for(const job of jobs.values())job.reject(error);
  jobs.clear();status(error.message);
 };
 return active;
}
function request(type,options,bytes=original){return new Promise((resolve,reject)=>{
 let id=++serial;
 try{worker??=createWorker();jobs.set(id,{resolve,reject});worker.postMessage({id,type,bytes,options})}
 catch(error){jobs.delete(id);reject(error)}
})}
function status(s){$('status').textContent=s}
// data-state on <html> is the machine-readable status: empty, loading, generating, ready or error.
const waiters=new Set();
function setState(state,message){
 document.documentElement.dataset.state=state;
 if(message!==undefined)status(message);
 if(state==='ready'||state==='error')for(const settle of waiters){waiters.delete(settle);settle(state)}
}
function options(){let axes={};document.querySelectorAll('[data-axis]').forEach(e=>axes[e.dataset.axis]=+e.value);if(meta.axes.some(a=>a.tag==='wdth'))axes.wdth=+$('width').value;return{axes,tracking:+$('tracking').value,scale:meta.axes.some(a=>a.tag==='wdth')?1:+$('width').value/100,family:$('family').value,style:$('style').value}}
async function generate(){if(!original||!meta)return;if(busy){pending=true;return}busy=true;let rev=revision;const start=performance.now();$('download').disabled=true;setState('generating','Generating font…');try{let d=await request('generate',options());if(rev!==revision)return;let face=new FontFace('Adjusted'+rev,d.bytes);await face.load();if(rev!==revision)return;document.fonts.forEach(f=>{if(f.family.startsWith('Adjusted'))document.fonts.delete(f)});document.fonts.add(face);$('after').style.fontFamily=`"Adjusted${rev}"`;result=d.bytes;preview();$('download').disabled=false;$('copy').disabled=false;css();setState('ready',`Ready · ${Math.round(performance.now()-start)} ms processing time`)}catch(e){if(rev===revision)setState('error','Cannot process this font: '+e.message)}finally{busy=false;if(pending){pending=false;generate()}}}
function invalidateExport(){result=null;$('download').disabled=true;$('copy').disabled=true;$('after').textContent='';$('css').textContent='Generate a font to get its @font-face CSS.'}
function schedule(){revision++;clearTimeout(timer);invalidateExport();if(meta)setState('generating');timer=setTimeout(generate,75)}
async function load(file){if(!file)return;if(!/\.(ttf|otf|woff2?)$/i.test(file.name)){setState('error','Unsupported file extension. Choose TTF, OTF, WOFF or WOFF2.');return}const currentLoad=++loadId;setState('loading');revision++;clearTimeout(timer);pending=false;meta=null;original=null;result=null;invalidateExport();$('meta').textContent='';$('before').textContent='';$('controls').disabled=true;try{const bytes=new Uint8Array(await file.arrayBuffer());if(currentLoad!==loadId)return;original=bytes;status('Reading font…');const inspected=(await request('inspect',undefined,bytes)).meta;if(currentLoad!==loadId)return;let baseline=await request('generate',{axes:{},scale:1,tracking:0,family:'Workshop Baseline',style:'Regular'},bytes);if(currentLoad!==loadId)return;let face=new FontFace('Original'+currentLoad,baseline.bytes);await face.load();if(currentLoad!==loadId)return;meta=inspected;document.fonts.forEach(f=>{if(f.family.startsWith('Original'))document.fonts.delete(f)});document.fonts.add(face);$('before').style.fontFamily='Original'+currentLoad;$('meta').textContent=`${meta.family} / ${meta.style} · ${meta.upem} units per em · ${meta.glyphs} glyphs`;$('family').value=meta.family+' Workshop';$('style').value=meta.style;$('axes').replaceChildren();for(let a of meta.axes.filter(a=>a.tag!=='wdth')){let label=document.createElement('label');label.textContent=`${a.tag} (${a.min} to ${a.max})`;let input=document.createElement('input');Object.assign(input,{type:'range',min:a.min,max:a.max,step:'any',value:a.default});input.dataset.axis=a.tag;input.oninput=schedule;label.append(input);$('axes').append(label)}let wd=meta.axes.find(a=>a.tag==='wdth');$('widthLabel').querySelector('span').textContent=wd?'Width':'Stretch';const {tracking,stretch}=meta.adjustments;Object.assign($('width'),{min:wd?.min??stretch.min,max:wd?.max??stretch.max,value:wd?.default??stretch.default,step:'any'});Object.assign($('tracking'),{min:tracking.min,max:tracking.max,step:tracking.step,value:tracking.default});$('controls').disabled=false;labels();preview();schedule()}catch(e){if(currentLoad!==loadId)return;meta=null;setState('error','Cannot load this font: '+e.message)}}
function formatValue(value){return Number(Number(value).toFixed(3)).toString()}
function labels(){$('trackout').textContent=formatValue($('tracking').value)+' em';$('widthout').textContent=meta?.axes.some(a=>a.tag==='wdth')?formatValue($('width').value)+' units':formatValue(+$('width').value/100)+'×'}
$('file').onchange=e=>{const file=e.target.files[0];e.target.value='';load(file)};$('drop').ondragover=e=>e.preventDefault();$('drop').ondrop=e=>{e.preventDefault();load(e.dataTransfer.files[0])};$('tracking').oninput=()=>{labels();schedule()};$('width').oninput=()=>{labels();schedule()};function resetAdjustments(){const {tracking,stretch,axes}=meta.adjustments;$('tracking').value=tracking.default;$('width').value=axes.wdth?.default??stretch.default;document.querySelectorAll('[data-axis]').forEach(e=>e.value=axes[e.dataset.axis].default);labels();schedule()}$('reset').onclick=resetAdjustments;
function preview(){for(let id of ['before','after']){$(id).textContent=(id==='before'?meta:result)?$('sample').value:'';$(id).style.fontSize=Math.max(8,Math.min(240,+$('size').value))+'px';$(id).style.color=$('color').value}$('specimens').classList.toggle('overlay',$('overlay').checked)}for(let id of ['sample','size','color','overlay'])$(id).oninput=preview;preview();
const filename=()=>($('filename').value.replace(/[^a-zA-Z0-9_-]/g,'-')||'workshop')+(result?.[0]===79?'.otf':'.ttf');function css(){if(!result)return;$('css').textContent=`@font-face {\n  font-family: ${JSON.stringify($('family').value.trim())};\n  src: url(${JSON.stringify(filename())});\n  font-style: normal;\n  font-weight: 400;\n}`};for(let id of ['family','style'])$(id).oninput=schedule;$('filename').oninput=css;$('download').onclick=()=>{if(!result||$('download').disabled)return;let url=URL.createObjectURL(new Blob([result],{type:result[0]===79?'font/otf':'font/ttf'})),a=document.createElement('a');a.href=url;a.download=filename();a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};$('copy').onclick=async()=>{if(!result||$('copy').disabled)return;try{await navigator.clipboard.writeText($('css').textContent);status('CSS copied.')}catch{status('Clipboard unavailable. Select and copy the CSS directly.')}};

// Automation API for browser agents and scripts. Documented in llms.txt.
// Validation messages match workshop.py except where the CLI names its flags.
function settled(){
 return new Promise((resolve,reject)=>{
  const finish=state=>state==='ready'?resolve(snapshot()):reject(Error($('status').textContent));
  const state=document.documentElement.dataset.state;
  if(state==='ready'||state==='error')finish(state);else waiters.add(finish);
 });
}
function axisInputs(){return new Map([...document.querySelectorAll('[data-axis]')].map(e=>[e.dataset.axis,e]))}
function snapshot(){
 const width=meta?.adjustments.axes.wdth;
 const axes={};
 for(const [tag,input] of axisInputs())axes[tag]=+input.value;
 if(width)axes.wdth=+$('width').value;
 return{
  state:document.documentElement.dataset.state,
  status:$('status').textContent,
  font:meta&&structuredClone(meta),
  settings:meta&&{tracking:+$('tracking').value,stretch:width?null:+$('width').value,axes,family:$('family').value,style:$('style').value,filename:$('filename').value},
  export:result&&{filename:filename(),format:result[0]===79?'otf':'ttf',bytes:result.length,css:$('css').textContent},
 };
}
function inRange(name,value,{min,max},unit=''){
 if(typeof value!=='number'||!Number.isFinite(value))throw TypeError(`${name} must be a number.`);
 if(value<min||value>max)throw RangeError(`${name} must be between ${min} and ${max}${unit}.`);
}
// Same rounding as workshop.py, so both send the engine the value the slider would hold.
function roundToStep(value,step){const n=Math.round(1/step);return Math.floor(value*n+0.5)/n}
const settingNames=['tracking','stretch','axes','family','style','filename'];
window.typeWorkshop={
 version:new URL(import.meta.url).searchParams.get('v'),
 state:snapshot,
 async load(source,name){
  const fontName=/\.(ttf|otf|woff2?)$/i;
  if(typeof source==='string'){
   const url=new URL(source,location.href);
   const response=await fetch(url);
   if(!response.ok)throw Error(`Cannot fetch ${url} (HTTP ${response.status})`);
   source=await response.arrayBuffer();
   // A URL without a font extension still loads; the engine reads the format from the bytes.
   if(name===undefined){const last=decodeURIComponent(url.pathname.split('/').pop());name=fontName.test(last)?last:'font.ttf'}
  }
  let bytes;
  if(source instanceof Blob){bytes=()=>source.arrayBuffer();name??=fontName.test(source.name??'')?source.name:'font.ttf'}
  else if(source instanceof ArrayBuffer)bytes=async()=>source;
  else if(ArrayBuffer.isView(source))bytes=async()=>source.buffer.slice(source.byteOffset,source.byteOffset+source.byteLength);
  else throw TypeError('load() takes a URL, File, Blob, ArrayBuffer or typed array.');
  load({name:name??'font.ttf',arrayBuffer:bytes});
  return settled();
 },
 async adjust(settings={}){
  if(!meta)throw Error('Load a font first.');
  if(settings===null||typeof settings!=='object')throw TypeError('adjust() takes an object of settings.');
  const unknown=Object.keys(settings).filter(key=>!settingNames.includes(key));
  if(unknown.length)throw TypeError(`Unknown setting ${unknown.map(key=>`"${key}"`).join(', ')}. Use ${settingNames.join(', ')}.`);
  const limits=meta.adjustments;
  const {tracking,stretch,axes={},family,style,filename:name}=settings;
  if(tracking!==undefined)inRange('Tracking',tracking,limits.tracking,' em');
  if(stretch!==undefined){
   const width=limits.axes.wdth;
   if(width)throw Error(`This font has a wdth axis. Use axes: {wdth: ${width.min} to ${width.max}} instead of stretch.`);
   inRange('Stretch',stretch,limits.stretch,' percent');
  }
  if(axes===null||typeof axes!=='object')throw TypeError('axes must be an object of axis tag to value, for example {wght: 700}.');
  for(const [tag,value] of Object.entries(axes)){
   if(!limits.axes[tag])throw Error(`This font has no "${tag}" axis. Available axes: ${Object.keys(limits.axes).join(', ')||'none'}.`);
   inRange(`Axis ${tag}`,value,limits.axes[tag]);
  }
  for(const [key,value] of Object.entries({family,style,filename:name}))if(value!==undefined&&typeof value!=='string')throw TypeError(`${key} must be a string.`);
  if((family!==undefined&&!family.trim())||(style!==undefined&&!style.trim()))throw Error('Family and style names cannot be empty.');
  if(tracking!==undefined)$('tracking').value=roundToStep(tracking,limits.tracking.step);
  if(stretch!==undefined)$('width').value=stretch;
  const inputs=axisInputs();
  for(const [tag,value] of Object.entries(axes))(tag==='wdth'?$('width'):inputs.get(tag)).value=value;
  if(family!==undefined)$('family').value=family;
  if(style!==undefined)$('style').value=style;
  if(name!==undefined)$('filename').value=name;
  labels();schedule();
  return settled();
 },
 async reset(){
  if(!meta)throw Error('Load a font first.');
  resetAdjustments();
  return settled();
 },
 getExport(){
  if(!result)throw Error('No current export. Wait for typeWorkshop.state().state to be "ready".');
  return{...snapshot().export,data:result.slice()};
 },
};
