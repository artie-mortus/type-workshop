importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js');
let engine,initializing;
async function getEngine(){
 if(!initializing)initializing=(async()=>{
  postMessage({status:'Loading browser Python and fontTools…'});
  const loaded=await loadPyodide();
  await loaded.loadPackage(['fonttools','brotli']);
  loaded.runPython(source);
  return loaded;
 })().catch(error=>{initializing=null;throw error});
 return initializing;
}
const source = `
import io, json, re
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib.tables.ttProgram import Program

def read(data):
 f=TTFont(io.BytesIO(bytes(data)))
 if 'glyf' not in f and 'CFF ' not in f: raise ValueError('Unsupported outlines. Only TrueType glyf and CFF fonts are supported; CFF2 is not supported.')
 return f

def inspect(data):
 f=read(data)
 return json.dumps(dict(family=f['name'].getBestFamilyName() or 'Untitled',style=f['name'].getBestSubFamilyName() or 'Regular',upem=f['head'].unitsPerEm,glyphs=len(f.getGlyphOrder()),axes=[dict(tag=a.axisTag,min=a.minValue,max=a.maxValue,default=a.defaultValue) for a in f['fvar'].axes] if 'fvar' in f else []))

def generate(data,options):
 o=json.loads(options); f=read(data)
 if 'fvar' in f:
  location={a.axisTag:o['axes'].get(a.axisTag,a.defaultValue) for a in f['fvar'].axes}
  f=instantiateVariableFont(f,location,inplace=True)
 scale=o['scale']; tracking=round(o['tracking']*f['head'].unitsPerEm)
 # Combining marks and control glyphs must retain their zero advance.
 # Tight tracking can close a narrow glyph's advance, but cannot make it negative.
 widths={name:max(0,round(advance*scale)+tracking) if advance else 0 for name,(advance,_) in f['hmtx'].metrics.items()}
 if any(width>65535 for width in widths.values()): raise ValueError('This stretch or tracking exceeds the font width limit. Reduce the adjustment.')
 if scale!=1:
  if 'glyf' in f:
   for g in f['glyf'].glyphs.values():
    g.expand(f['glyf'])
    if g.isComposite():
     for c in g.components:
      if not hasattr(c,'x'): raise ValueError('Point-attached composite cannot be stretched safely.')
      c.x=round(c.x*scale)
      if hasattr(c,'transform'):
       c.transform=[[c.transform[0][0],c.transform[0][1]/scale],[c.transform[1][0]*scale,c.transform[1][1]]]
    elif g.numberOfContours>0:
     for i,(x,y) in enumerate(g.coordinates): g.coordinates[i]=(round(x*scale),y)
    g.program=Program()
   for tag in ['fpgm','prep','cvt ','hdmx','LTSH','VDMX']: 
    if tag in f: del f[tag]
 if tracking!=0:
  for tag in ['hdmx','LTSH']:
   if tag in f: del f[tag]
 if 'CFF ' in f and (scale!=1 or tracking!=0):
   top=f['CFF '].cff.topDictIndex[0]; gs=f.getGlyphSet()
   recordings={}
   for name in f.getGlyphOrder():
    pen=DecomposingRecordingPen(gs); gs[name].draw(TransformPen(pen,(scale,0,0,1,0,0))); recordings[name]=pen
   # CID-keyed CFF fonts store a separate Private dictionary per font dict.
   privates={name:top.CharStrings[name].private for name in f.getGlyphOrder()}
   for private in privates.values():
    private.nominalWidthX=0
    private.defaultWidthX=0
   for name,recording in recordings.items():
    pen=T2CharStringPen(widths[name],None); recording.replay(pen)
    top.CharStrings[name]=pen.getCharString(private=privates[name],globalSubrs=top.GlobalSubrs)
 for name,(advance,lsb) in list(f['hmtx'].metrics.items()):
  f['hmtx'][name]=(widths[name],round(lsb*scale))
 if 'OS/2' in f: f['OS/2'].recalcAvgCharWidth(f)
 family=o['family'].strip(); style=o['style'].strip()
 if not family or not style: raise ValueError('Family and style names cannot be empty.')
 ps=re.sub('[^A-Za-z0-9-]','',family+'-'+style)[:63] or 'Workshop-Regular'
 names={1:family,2:style,3:ps+';Workshop',4:family+' '+style,6:ps,16:family,17:style}
 f['name'].names=[n for n in f['name'].names if n.nameID not in names]
 for id,value in names.items():
  f['name'].setName(value,id,3,1,0x409)
 if 'CFF ' in f:
  cff=f['CFF '].cff; cff.fontNames=[ps]; top=cff.topDictIndex[0]; top.FamilyName=family; top.FullName=family+' '+style
 if 'DSIG' in f: del f['DSIG']
 f.flavor=None
 out=io.BytesIO(); f.save(out)
 return out.getvalue()
`;
// Pyodide errors include a Python traceback; show its final exception to the user.
function processingError(error) {
 const lines=String(error.message||error).trim().split('\n');
 return lines.at(-1).replace(/^(?:[\w.]*Error|Exception):\s*/, '');
}
onmessage=async({data:m})=>{try{engine=await getEngine();engine.globals.set('input_bytes',m.bytes);if(m.type==='inspect'){postMessage({id:m.id,meta:JSON.parse(engine.runPython('inspect(input_bytes)'))})}else{engine.globals.set('options',JSON.stringify(m.options));let result=engine.runPython('generate(input_bytes,options)');let bytes=result.toJs();result.destroy();postMessage({id:m.id,bytes},[bytes.buffer])}}catch(e){postMessage({id:m.id,error:processingError(e)})}};
