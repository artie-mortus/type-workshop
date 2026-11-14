from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
import io, json
root=Path(__file__).resolve().parents[1]
exec((root/'worker.js').read_text().split('const source = `')[1].split('`;')[0])
fixtures={'ttf':'/usr/share/fonts/carlito/Carlito-Regular.ttf','cff':'/usr/share/fonts/gnu-free/FreeSans.otf','variable':'/usr/share/fonts/Adwaita/AdwaitaSans-Italic.ttf'}
for kind,path in fixtures.items():
 data=Path(path).read_bytes()
 for scale in [1,1.2]:
  base=read(data)
  axes={a.axisTag:a.maxValue for a in base['fvar'].axes} if 'fvar' in base else {}
  if axes: base=instantiateVariableFont(base,axes)
  output=generate(data,json.dumps(dict(axes=axes,scale=scale,tracking=.05,family='Verified Workshop',style='Regular')))
  font=TTFont(io.BytesIO(output),checkChecksums=2)
  assert 'fvar' not in font
  assert font['name'].getDebugName(1)=='Verified Workshop'
  for name,(advance,lsb) in base['hmtx'].metrics.items():
   assert font['hmtx'][name][0]==round(advance*scale)+round(base['head'].unitsPerEm*.05)
  ext='otf' if kind=='cff' else 'ttf'
  target=root/f'test-results/{kind}-{scale}.{ext}';target.write_bytes(output)
  print(kind,scale,'PASS',len(output),'bytes; all advances verified')
