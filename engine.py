"""Font adjustment engine shared by the browser worker and the command line.

The browser worker fetches this file and runs it in Pyodide, so it must stay
importable with only fontTools and brotli available.
"""
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

# Adjustment ranges for the page sliders, the page API and workshop.py.
TRACKING_RANGE=(-0.1,0.2) # em
# The page's tracking slider snaps to this step, so every caller rounds to it with
# n=round(1/step); floor(value*n+0.5)/n. JavaScript and Python compute that identically,
# and the integer division gives the same number as the slider's decimal value.
TRACKING_STEP=0.001 # em
STRETCH_RANGE=(50,200) # percent of the original width

def inspect(data):
 f=read(data)
 axes=[dict(tag=a.axisTag,min=a.minValue,max=a.maxValue,default=a.defaultValue) for a in f['fvar'].axes] if 'fvar' in f else []
 cff='CFF ' in f
 adjustments=dict(
  tracking=dict(min=TRACKING_RANGE[0],max=TRACKING_RANGE[1],default=0,step=TRACKING_STEP,unit='em'),
  # Fonts with a wdth axis change width through the axis, not synthetic stretch.
  stretch=None if any(a['tag']=='wdth' for a in axes) else dict(min=STRETCH_RANGE[0],max=STRETCH_RANGE[1],default=100,unit='percent'),
  axes={a['tag']:dict(min=a['min'],max=a['max'],default=a['default']) for a in axes},
 )
 return json.dumps(dict(family=f['name'].getBestFamilyName() or 'Untitled',style=f['name'].getBestSubFamilyName() or 'Regular',upem=f['head'].unitsPerEm,glyphs=len(f.getGlyphOrder()),axes=axes,outlines='cff' if cff else 'truetype',output_format='otf' if cff else 'ttf',adjustments=adjustments))

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
