importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js');
let engine;
const source = `
import io, json, re
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib.tables.ttProgram import Program

def read(data):
 f=TTFont(io.BytesIO(bytes(data)))
 if 'glyf' not in f and 'CFF ' not in f: raise ValueError('Unsupported outlines. Only TrueType glyf and CFF fonts are supported; CFF2 is not supported.')
 return f

def inspect(data):
 f=read(data)
 return json.dumps(dict(family=f['name'].getDebugName(1),style=f['name'].getDebugName(2),upem=f['head'].unitsPerEm,glyphs=len(f.getGlyphOrder()),axes=[dict(tag=a.axisTag,min=a.minValue,max=a.maxValue,default=a.defaultValue) for a in f['fvar'].axes] if 'fvar' in f else []))

def generate(data,options):
 o=json.loads(options); f=read(data)
 if 'fvar' in f:
  location={a.axisTag:o['axes'].get(a.axisTag,a.defaultValue) for a in f['fvar'].axes}
  f=instantiateVariableFont(f,location,inplace=True)
 scale=o['scale']; tracking=round(o['tracking']*f['head'].unitsPerEm)
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
 if 'CFF ' in f and (scale!=1 or tracking!=0):
   top=f['CFF '].cff.topDictIndex[0]; gs=f.getGlyphSet()
   recordings={}
   for name in f.getGlyphOrder():
    pen=RecordingPen(); gs[name].draw(TransformPen(pen,(scale,0,0,1,0,0))); recordings[name]=pen
   top.Private.nominalWidthX=0
   top.Private.defaultWidthX=0
   for name,recording in recordings.items():
    pen=T2CharStringPen(round(f['hmtx'][name][0]*scale)+tracking,None); recording.replay(pen)
    top.CharStrings[name]=pen.getCharString(private=top.Private,globalSubrs=top.GlobalSubrs)
 for name,(advance,lsb) in list(f['hmtx'].metrics.items()):
  width=round(advance*scale)+tracking
  if width<0 or width>65535: raise ValueError('Adjustment creates an invalid advance width. Reduce tracking or stretch.')
  f['hmtx'][name]=(width,round(lsb*scale))
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
onmessage=async({data:m})=>{try{if(!engine){postMessage({status:'Loading browser Python and fontTools…'});engine=await loadPyodide();await engine.loadPackage(['fonttools','brotli']);engine.runPython(source)}engine.globals.set('input_bytes',m.bytes);if(m.type==='inspect'){postMessage({id:m.id,meta:JSON.parse(engine.runPython('inspect(input_bytes)'))})}else{engine.globals.set('options',JSON.stringify(m.options));let result=engine.runPython('generate(input_bytes,options)');let bytes=result.toJs();result.destroy();postMessage({id:m.id,bytes},[bytes.buffer])}}catch(e){postMessage({id:m.id,error:String(e.message||e)})}};
