"""Font adjustment engine shared by the browser worker and the command line.

The browser worker fetches this file and runs it in Pyodide, so it must stay
importable with only fontTools and brotli available.
"""
import hashlib, io, json, math, re
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib.tables.ttProgram import Program
from fontTools.misc.psCharStrings import encodeIntT2, encodeFixed

def read(data):
 f=TTFont(io.BytesIO(bytes(data)))
 if 'glyf' not in f and 'CFF ' not in f: raise ValueError('Unsupported outlines. Only TrueType glyf and CFF fonts are supported; CFF2 is not supported.')
 f.repaired_glyphs=repair_charstrings(f) if 'CFF ' in f else []
 return f

STEM_OPERATORS={1,3,18,23} # hstem, vstem, hstemhm, vstemhm
MOVETO_ARGUMENTS={21:2,22:1,4:1} # rmoveto, hmoveto, vmoveto

def moveto_surplus(bytecode):
 """Count stray operands before a charstring's first moveto, reading only the bytes up to it."""
 operands=0; stems=False; i=0
 while i<len(bytecode):
  b=bytecode[i]
  if b>=32: operands+=1; i+=1 if b<=246 else 5 if b==255 else 2; continue
  if b==28: operands+=1; i+=3; continue
  if b in STEM_OPERATORS: stems=True; operands=0; i+=1; continue
  # Hint masks, subroutine calls and drawing operators end the scan. A first move inside a
  # subroutine is not examined.
  if b not in MOVETO_ARGUMENTS: return 0,0
  need=MOVETO_ARGUMENTS[b]
  # Without earlier stem hints, an odd extra operand is the glyph width.
  width=0 if stems else (operands-need)%2
  return width,max(0,operands-need-width)
 return 0,0

def repair_charstrings(f):
 """Drop stray operands before the first moveto, as FreeType does.

 Some FontForge builds omit the vstemhm operator before the first moveto, leaving its stem
 operands on the stack. Browsers' sanitizer rejects the whole font, and fontTools draws the
 glyph from the stray operands instead of the move, displacing the contour.
 """
 charstrings=f['CFF '].cff.topDictIndex[0].CharStrings; repaired=[]
 for name in f.getGlyphOrder():
  cs=charstrings[name]
  if cs.bytecode is None: continue
  width,surplus=moveto_surplus(cs.bytecode)
  if not surplus: continue
  cs.decompile(); program=list(cs.program)
  move=next(i for i,token in enumerate(program) if token in ('rmoveto','hmoveto','vmoveto'))
  start=max((i+1 for i,token in enumerate(program[:move]) if isinstance(token,str)),default=0)+width
  del program[start:start+surplus]
  cs.setProgram(program); repaired.append(name)
 return repaired

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
 return json.dumps(dict(family=f['name'].getBestFamilyName() or 'Untitled',style=f['name'].getBestSubFamilyName() or 'Regular',upem=f['head'].unitsPerEm,glyphs=len(f.getGlyphOrder()),axes=axes,outlines='cff' if cff else 'truetype',output_format='otf' if cff else 'ttf',repaired_glyphs=f.repaired_glyphs,adjustments=adjustments))

WIDTH_IF_ODD={1,3,18,23,19,20,21,14} # stems, hint masks, rmoveto, endchar
WIDTH_IF_EVEN={22,4} # hmoveto, vmoveto

def t2_number(bytecode,i):
 """Decode the Type 2 number at i. Returns (value, next index)."""
 b=bytecode[i]
 if b==28: return int.from_bytes(bytecode[i+1:i+3],'big',signed=True),i+3
 if b<=246: return b-139,i+1
 if b<=250: return (b-247)*256+bytecode[i+1]+108,i+2
 if b<=254: return -(b-251)*256-bytecode[i+1]-108,i+2
 return int.from_bytes(bytecode[i+1:i+5],'big',signed=True)/65536,i+5

def subr_bias(subrs):
 return 107 if len(subrs)<1240 else 1131 if len(subrs)<33900 else 32768

def width_operand(cs):
 """Find a charstring's leading width without decoding its outline.

 Follows subroutine calls up to the first operator that fixes the width. Returns (present, end),
 where the width occupies bytecode[:end] when present, or None if the width lies inside a
 subroutine or the charstring does something unexpected first.
 """
 local=getattr(cs.private,'Subrs',None) or []; glob=cs.globalSubrs or []
 stack=[] # one entry per operand: (start, end) in the main charstring, or None
 def run(bytecode,main,depth):
  i=0
  while i<len(bytecode):
   b=bytecode[i]
   if b>=32 or b==28:
    value,after=t2_number(bytecode,i); stack.append((i,after,value) if main else (None,None,value)); i=after; continue
   if b in (10,29): # callsubr, callgsubr
    if not stack or depth>=10: return None
    subrs=local if b==10 else glob
    index=stack.pop()[2]+subr_bias(subrs)
    if not isinstance(index,int) or not 0<=index<len(subrs): return None
    subr=subrs[index]
    if subr.bytecode is None: subr.compile() # decoded earlier, for example by repair_charstrings
    found=run(subr.bytecode,False,depth+1)
    if found!='return': return found
    i+=1; continue
   if b==11 and not main: return 'return'
   if b in WIDTH_IF_ODD: present=len(stack)%2==1
   elif b in WIDTH_IF_EVEN: present=len(stack)%2==0
   else: return None
   if not present: return False,0
   start,stop,_=stack[0]
   return (True,stop) if start==0 else None
  return None
 if cs.bytecode is None: cs.compile() # decoded earlier, for example by repair_charstrings
 found=run(cs.bytecode,True,0)
 return found if isinstance(found,tuple) else None

CFF_WIDTH_ERROR='This stretch or tracking makes a glyph wider than CFF outlines can store. Reduce the adjustment.'

def cff_width_operand(width,nominal):
 """A charstring stores width-nominalWidthX as a 16-bit number. fontTools writes larger
 values in a form readers decode as a small fraction, so refuse them."""
 value=width-nominal
 if not -32768<=value<=32767: raise ValueError(CFF_WIDTH_ERROR)
 return value

def set_charstring_width(cs,width):
 """Rewrite only the width operand, keeping hints and subroutine calls. False if it cannot be located."""
 found=width_operand(cs)
 if found is None: return False
 present,end=found
 value=cff_width_operand(width,cs.private.nominalWidthX)
 encoded=encodeIntT2(int(value)) if value==int(value) else encodeFixed(value)
 cs.bytecode=encoded+cs.bytecode[end:]
 return True

extents_cache={}
def glyph_extents(data):
 """Outline width per glyph, measured as fontTools' hhea.recalc measures it. Cached for repeated adjustments."""
 key=hashlib.sha256(bytes(data)).digest()
 if key not in extents_cache:
  f=read(data); extents={}
  if 'glyf' in f:
   glyf=f['glyf']
   for name in f.getGlyphOrder():
    g=glyf[name]
    if g.numberOfContours==0: continue
    if g.numberOfContours<0 and not hasattr(g,'xMax'): g.recalcBounds(glyf)
    extents[name]=g.xMax-g.xMin
  else:
   charstrings=f['CFF '].cff.topDictIndex[0].CharStrings
   for name in f.getGlyphOrder():
    bounds=charstrings[name].calcBounds(charstrings)
    if bounds is not None: extents[name]=int(math.ceil(bounds[2])-math.floor(bounds[0]))
  extents_cache.clear(); extents_cache[key]=extents
 return extents_cache[key]

def update_hhea(f,extents):
 """Recompute the advance-dependent hhea fields the same way fontTools' hhea.recalc does."""
 hhea=f['hhea']; hmtx=f['hmtx']
 hhea.advanceWidthMax=max(advance for advance,_ in hmtx.metrics.values())
 if extents:
  hhea.minLeftSideBearing=min(hmtx[name][1] for name in extents)
  hhea.minRightSideBearing=min(hmtx[name][0]-hmtx[name][1]-width for name,width in extents.items())
  hhea.xMaxExtent=max(hmtx[name][1]+width for name,width in extents.items())
 else: # no glyph has outlines
  hhea.minLeftSideBearing=hhea.minRightSideBearing=hhea.xMaxExtent=0

def generate(data,options):
 o=json.loads(options); f=read(data)
 # Instancing and stretch change outlines, so fontTools must recalculate bounds when saving.
 # Otherwise the outlines are untouched, and recalculating every glyph's bounds dominates the time.
 outlines_changed='fvar' in f or o['scale']!=1
 if 'fvar' in f:
  location={a.axisTag:o['axes'].get(a.axisTag,a.defaultValue) for a in f['fvar'].axes}
  f=instantiateVariableFont(f,location,inplace=True)
 scale=o['scale']; tracking=round(o['tracking']*f['head'].unitsPerEm)
 # Combining marks and control glyphs must retain their zero advance.
 # Tight tracking can close a narrow glyph's advance, but cannot make it negative.
 widths={name:max(0,round(advance*scale)+tracking) if advance else 0 for name,(advance,_) in f['hmtx'].metrics.items()}
 if any(width>65535 for width in widths.values()): raise ValueError('This stretch or tracking exceeds the font width limit. Reduce the adjustment.')
 # Outline coordinates and bounding boxes are signed 16-bit numbers.
 head=f['head']
 if scale!=1 and max(abs(head.xMin),abs(head.xMax))*scale>32767: raise ValueError('This stretch makes the outlines wider than the font format can store. Reduce the stretch.')
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
 redraw=f.getGlyphOrder() if scale!=1 else []
 if 'CFF ' in f and scale==1 and tracking!=0:
  # Tracking alone changes only widths. Rewrite the width operand and keep hints and subroutines.
  charstrings=f['CFF '].cff.topDictIndex[0].CharStrings
  redraw=[name for name in f.getGlyphOrder() if not set_charstring_width(charstrings[name],widths[name])]
 if 'CFF ' in f and redraw:
   top=f['CFF '].cff.topDictIndex[0]; gs=f.getGlyphSet()
   recordings={}
   for name in redraw:
    pen=DecomposingRecordingPen(gs); gs[name].draw(TransformPen(pen,(scale,0,0,1,0,0))); recordings[name]=pen
   # CID-keyed CFF fonts store a separate Private dictionary per font dict.
   privates={name:top.CharStrings[name].private for name in redraw}
   if scale!=1:
    # Every glyph is redrawn, so explicit widths can replace the nominal and default widths.
    for private in privates.values():
     private.nominalWidthX=0
     private.defaultWidthX=0
   for name,recording in recordings.items():
    # T2CharStringPen writes the width as is, so subtract the glyph's nominal width.
    pen=T2CharStringPen(cff_width_operand(widths[name],privates[name].nominalWidthX),None); recording.replay(pen)
    top.CharStrings[name]=pen.getCharString(private=privates[name],globalSubrs=top.GlobalSubrs)
 for name,(advance,lsb) in list(f['hmtx'].metrics.items()):
  f['hmtx'][name]=(widths[name],round(lsb*scale))
 if 'OS/2' in f: f['OS/2'].recalcAvgCharWidth(f)
 f.recalcBBoxes=outlines_changed
 if not outlines_changed and tracking!=0: update_hhea(f,glyph_extents(data))
 family=o['family'].strip(); style=o['style'].strip()
 if not family or not style: raise ValueError('Family and style names cannot be empty.')
 ps=re.sub('[^A-Za-z0-9-]','',family+'-'+style)[:63] or 'Workshop-Regular'
 names={1:family,2:style,3:ps+';Workshop',4:family+' '+style,6:ps,16:family,17:style}
 f['name'].names=[n for n in f['name'].names if n.nameID not in names]
 for id,value in names.items():
  f['name'].setName(value,id,3,1,0x409)
 if 'CFF ' in f:
  cff=f['CFF '].cff; cff.fontNames=[ps]; top=cff.topDictIndex[0]; top.FamilyName=family; top.FullName=family+' '+style
 if f.isLoaded('glyf'):
  # A repeated first flag copies OVERLAP_SIMPLE (bit 6) onto later points when fontTools decodes
  # a glyph, and saving re-encodes every glyph once glyf is loaded. The spec allows the bit only
  # on the first flag, and browsers reject fonts that store it later. An unloaded glyf table is
  # copied byte for byte, so leave it unloaded.
  glyf=f['glyf']
  for g in glyf.glyphs.values():
   g.expand(glyf)
   if g.numberOfContours>0:
    for i in range(1,len(g.flags)): g.flags[i]&=0xBF
 if 'DSIG' in f: del f['DSIG']
 f.flavor=None
 out=io.BytesIO(); f.save(out)
 return out.getvalue()
