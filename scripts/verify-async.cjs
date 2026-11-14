// Run with node --experimental-vm-modules scripts/verify-async.cjs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const tick = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b }); return {promise, resolve, reject}; };
async function appChecks() {
 const elements = new Map();
 const element = id => { if(!elements.has(id)) elements.set(id, {value:'',disabled:true,textContent:'',style:{},dataset:{},setAttribute(){},replaceChildren(){},querySelector(){return element(id+' span')},classList:{toggle(){}}}); return elements.get(id); };
 const workers=[]; const listeners={}; const copied=[];
 class Worker {
  constructor(url){ this.url=String(url); this.messages=[]; workers.push(this); }
  postMessage(message){this.messages.push(message);}
  terminate(){this.terminated=true;}
  reply(message,data){this.onmessage({data:{id:message.id,...data}});}
 }
 const context=vm.createContext({URL,Worker,Uint8Array,Map,Error,performance,clearTimeout,setTimeout,localStorage:{getItem:()=>null},window:{addEventListener(name,handler){listeners[name]=handler;}},document:{getElementById:element,documentElement:{dataset:{theme:'dark'}},querySelectorAll:()=>[],fonts:new Set()},faceLoads:[],FontFace:class {constructor(family){this.family=family;} async load(){await context.faceLoads.shift();return this;}},navigator:{clipboard:{async writeText(text){copied.push(text);}}}});
 const module=new vm.SourceTextModule(fs.readFileSync('app.js','utf8')+'\nglobalThis.runApp = code => eval(code);',{context,initializeImportMeta(meta){meta.url='http://localhost/app.js?v=test-release';}});
 await module.link(()=>{});await module.evaluate();
 const run = code => context.runApp(code);
 await element('copy').onclick();
 assert.equal(copied.length,0,'Copy must not publish a stale or placeholder export');
 element('color').value='#ff9900';listeners.storage({key:'type-workshop-theme',newValue:'light'});
 assert.equal(element('color').value,'#ff9900','Cross-tab theme changes must preserve custom specimen colors');
 const first=deferred();context.firstBytes=first.promise;
 const slow=run("load({name:'old.ttf',arrayBuffer:()=>firstBytes})");
 const latest=run("load({name:'new.ttf',arrayBuffer:async()=>new Uint8Array([2])})");await tick();
 first.resolve(new Uint8Array([1]));await tick();
 assert.equal(workers[0].messages.length,1,'A superseded file read must not start an inspect job');
 const inspect=workers[0].messages[0];assert.equal(inspect.bytes[0],2);
 const meta={family:'New',style:'Regular',axes:[],upem:2048,glyphs:2};
 workers[0].reply(inspect,{meta});await tick();workers[0].reply(workers[0].messages[1],{bytes:new Uint8Array([2])});await latest;await slow;
 assert.equal(element('controls').disabled,false);assert.match(element('meta').textContent,/New/);
 run('clearTimeout(timer)');
 const generation=run('generate()');const stale=workers[0].messages.at(-1);
 const replacement=run("load({name:'replacement.ttf',arrayBuffer:async()=>new Uint8Array([3])})");await tick();
 const current=workers[0].messages.at(-1);
 assert.equal(element('meta').textContent,'','Loading another font must clear previous metadata');
 workers[0].reply(stale,{error:'old generation failed'});await generation;
 assert(!element('status').textContent.includes('old generation failed'),'Stale generation error overwrites the active load status');
 workers[0].reply(current,{meta});await tick();
 workers[0].reply(workers[0].messages.at(-1),{bytes:new Uint8Array([3])});await replacement;run('clearTimeout(timer)');
 assert.equal(element('controls').disabled,false);
 const faceReady=deferred();context.faceLoads.push(faceReady.promise);
 const oldFace=run("load({name:'old-face.ttf',arrayBuffer:async()=>new Uint8Array([4])})");await tick();
 workers[0].reply(workers[0].messages.at(-1),{meta});await tick();
 workers[0].reply(workers[0].messages.at(-1),{bytes:new Uint8Array([4])});await tick();
 const newFace=run("load({name:'new-face.ttf',arrayBuffer:async()=>new Uint8Array([5])})");await tick();
 faceReady.resolve();await oldFace;
 assert.equal(element('controls').disabled,true,'An old FontFace must not enable controls during a newer load');
 assert.equal(run('meta'),null);
 workers[0].reply(workers[0].messages.at(-1),{meta});await tick();
 workers[0].reply(workers[0].messages.at(-1),{bytes:new Uint8Array([5])});await newFace;run('clearTimeout(timer)');
 const oldError=run("load({name:'bad.ttf',arrayBuffer:async()=>new Uint8Array([6])})");await tick();const bad=workers[0].messages.at(-1);
 const newError=run("load({name:'good.ttf',arrayBuffer:async()=>new Uint8Array([7])})");await tick();
 const good=workers[0].messages.at(-1);
 workers[0].reply(good,{meta});await tick();workers[0].reply(workers[0].messages.at(-1),{bytes:new Uint8Array([7])});await newError;run('clearTimeout(timer)');
 workers[0].reply(bad,{error:'stale inspection failed'});await oldError;
 assert.equal(run('meta.family'),'New');assert(!element('status').textContent.includes('stale inspection failed'));
 const pending=run("request('inspect')");const rejected=assert.rejects(pending,/crashed/);
 workers[0].onerror({message:'crashed',preventDefault(){}});await rejected;
 const retry=run("request('inspect')");assert.equal(workers.length,2,'Fatal worker errors must allow retry');
 workers[1].reply(workers[1].messages[0],{meta});await retry;
 assert.equal(workers[1].url,'http://localhost/worker.js?v=test-release');
 console.log('PASS: stale reads/errors/FontFace results, worker crash recovery, release URL');
}
async function workerChecks() {
 const ready=deferred();let loads=0;const replies=[];
 const engine={loadPackage:()=>ready.promise,globals:{set(){}},runPython(code){if(code==='inspect(input_bytes)')return '{}';}};
 const context=vm.createContext({importScripts(){},loadPyodide:async()=>{loads++;return engine;},postMessage:m=>replies.push(m)});
 vm.runInContext(fs.readFileSync('worker.js','utf8'),context);
 const first=context.onmessage({data:{id:1,type:'inspect',bytes:[]}});await tick();
 const second=context.onmessage({data:{id:2,type:'inspect',bytes:[]}});await tick();
 assert(!replies.some(r=>r.id),'Concurrent jobs must wait until packages and Python definitions are ready');
 ready.resolve();await Promise.all([first,second]);assert.equal(loads,1);assert.equal(replies.filter(r=>r.meta).length,2);
 let attempts=0;
 const retryReplies=[];
 const retryContext=vm.createContext({importScripts(){},loadPyodide:async()=>{if(++attempts===1)throw Error('download failed');return engine;},postMessage:m=>retryReplies.push(m)});
 vm.runInContext(fs.readFileSync('worker.js','utf8'),retryContext);
 await retryContext.onmessage({data:{id:3,type:'inspect',bytes:[]}});
 assert.equal(retryReplies.at(-1).error,'download failed');
 await retryContext.onmessage({data:{id:4,type:'inspect',bytes:[]}});
 assert(retryReplies.at(-1).meta);assert.equal(attempts,2);
 console.log('PASS: concurrent worker initialization and retry after a failed engine download');
}
(async()=>{await appChecks();await workerChecks()})().catch(e=>{console.error(e);process.exitCode=1});
