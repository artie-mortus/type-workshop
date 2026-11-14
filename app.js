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
function status(s){$('status').textContent=s}function options(){let axes={};document.querySelectorAll('[data-axis]').forEach(e=>axes[e.dataset.axis]=+e.value);if(meta.axes.some(a=>a.tag==='wdth'))axes.wdth=+$('width').value;return{axes,tracking:+$('tracking').value,scale:meta.axes.some(a=>a.tag==='wdth')?1:+$('width').value/100,family:$('family').value,style:$('style').value}}
async function generate(){if(!original||!meta)return;if(busy){pending=true;return}busy=true;let rev=revision;const start=performance.now();$('download').disabled=true;status('Generating font…');try{let d=await request('generate',options());if(rev!==revision)return;let face=new FontFace('Adjusted'+rev,d.bytes);await face.load();if(rev!==revision)return;document.fonts.forEach(f=>{if(f.family.startsWith('Adjusted'))document.fonts.delete(f)});document.fonts.add(face);$('after').style.fontFamily=`"Adjusted${rev}"`;result=d.bytes;preview();$('download').disabled=false;$('copy').disabled=false;status(`Ready · ${Math.round(performance.now()-start)} ms processing time`);css()}catch(e){if(rev===revision)status('Cannot process this font: '+e.message)}finally{busy=false;if(pending){pending=false;generate()}}}
function invalidateExport(){result=null;$('download').disabled=true;$('copy').disabled=true;$('after').textContent='';$('css').textContent='Generate a font to get its @font-face CSS.'}
function schedule(){revision++;clearTimeout(timer);invalidateExport();timer=setTimeout(generate,75)}
async function load(file){if(!file)return;if(!/\.(ttf|otf|woff2?)$/i.test(file.name)){status('Unsupported file extension. Choose TTF, OTF, WOFF or WOFF2.');return}const currentLoad=++loadId;revision++;clearTimeout(timer);pending=false;meta=null;original=null;result=null;invalidateExport();$('meta').textContent='';$('before').textContent='';$('controls').disabled=true;try{const bytes=new Uint8Array(await file.arrayBuffer());if(currentLoad!==loadId)return;original=bytes;status('Reading font…');const inspected=(await request('inspect',undefined,bytes)).meta;if(currentLoad!==loadId)return;let baseline=await request('generate',{axes:{},scale:1,tracking:0,family:'Workshop Baseline',style:'Regular'},bytes);if(currentLoad!==loadId)return;let face=new FontFace('Original'+currentLoad,baseline.bytes);await face.load();if(currentLoad!==loadId)return;meta=inspected;document.fonts.forEach(f=>{if(f.family.startsWith('Original'))document.fonts.delete(f)});document.fonts.add(face);$('before').style.fontFamily='Original'+currentLoad;$('meta').textContent=`${meta.family} / ${meta.style} · ${meta.upem} units per em · ${meta.glyphs} glyphs`;$('family').value=meta.family+' Workshop';$('style').value=meta.style;$('axes').replaceChildren();for(let a of meta.axes.filter(a=>a.tag!=='wdth')){let label=document.createElement('label');label.textContent=`${a.tag} (${a.min} to ${a.max})`;let input=document.createElement('input');Object.assign(input,{type:'range',min:a.min,max:a.max,step:'any',value:a.default});input.dataset.axis=a.tag;input.oninput=schedule;label.append(input);$('axes').append(label)}let wd=meta.axes.find(a=>a.tag==='wdth');$('widthLabel').querySelector('span').textContent=wd?'Width':'Stretch';Object.assign($('width'),{min:wd?.min??50,max:wd?.max??200,value:wd?.default??100,step:'any'});$('tracking').value=0;$('controls').disabled=false;labels();preview();schedule()}catch(e){if(currentLoad!==loadId)return;meta=null;status('Cannot load this font: '+e.message)}}
function formatValue(value){return Number(Number(value).toFixed(3)).toString()}
function labels(){$('trackout').textContent=formatValue($('tracking').value)+' em';$('widthout').textContent=meta?.axes.some(a=>a.tag==='wdth')?formatValue($('width').value)+' units':formatValue(+$('width').value/100)+'×'}
$('file').onchange=e=>{const file=e.target.files[0];e.target.value='';load(file)};$('drop').ondragover=e=>e.preventDefault();$('drop').ondrop=e=>{e.preventDefault();load(e.dataTransfer.files[0])};$('tracking').oninput=()=>{labels();schedule()};$('width').oninput=()=>{labels();schedule()};$('reset').onclick=()=>{$('tracking').value=0;$('width').value=meta.axes.find(a=>a.tag==='wdth')?.default??100;document.querySelectorAll('[data-axis]').forEach(e=>e.value=meta.axes.find(a=>a.tag===e.dataset.axis).default);labels();schedule()};
function preview(){for(let id of ['before','after']){$(id).textContent=(id==='before'?meta:result)?$('sample').value:'';$(id).style.fontSize=Math.max(8,Math.min(240,+$('size').value))+'px';$(id).style.color=$('color').value}$('specimens').classList.toggle('overlay',$('overlay').checked)}for(let id of ['sample','size','color','overlay'])$(id).oninput=preview;preview();
const filename=()=>($('filename').value.replace(/[^a-zA-Z0-9_-]/g,'-')||'workshop')+(result?.[0]===79?'.otf':'.ttf');function css(){if(!result)return;$('css').textContent=`@font-face {\n  font-family: ${JSON.stringify($('family').value)};\n  src: url(${JSON.stringify(filename())});\n  font-style: normal;\n  font-weight: 400;\n}`};for(let id of ['family','style'])$(id).oninput=schedule;$('filename').oninput=css;$('download').onclick=()=>{if(!result||$('download').disabled)return;let url=URL.createObjectURL(new Blob([result],{type:result[0]===79?'font/otf':'font/ttf'})),a=document.createElement('a');a.href=url;a.download=filename();a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};$('copy').onclick=async()=>{if(!result||$('copy').disabled)return;try{await navigator.clipboard.writeText($('css').textContent);status('CSS copied.')}catch{status('Clipboard unavailable. Select and copy the CSS directly.')}};
