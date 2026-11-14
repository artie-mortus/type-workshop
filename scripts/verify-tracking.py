"""Regression checks for negative tracking and zero-advance marks."""
from pathlib import Path
import io
import json
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import NullPen

root = Path(__file__).resolve().parents[1]
exec((root / 'worker.js').read_text().split('const source = `')[1].split('`;')[0])
fixtures = {'ttf': '/usr/share/fonts/carlito/Carlito-Regular.ttf', 'cff': '/usr/share/fonts/gnu-free/FreeSans.otf', 'variable': '/usr/share/fonts/Adwaita/AdwaitaSans-Italic.ttf'}
for kind, fixture in fixtures.items():
    path = Path(fixture)
    data = path.read_bytes()
    original = read(data)
    if 'fvar' in original:
        original = instantiateVariableFont(original, {a.axisTag: a.defaultValue for a in original['fvar'].axes})
    assert any(a == 0 for a, _ in original['hmtx'].metrics.values()), 'Fixture needs zero-width glyphs'
    for tracking in [-.001, -.1, .05]:
        for scale in [.5, 1, 2]:
            output = generate(data, json.dumps(dict(axes={}, scale=scale, tracking=tracking, family='Tracking Test', style='Regular')))
            font = TTFont(io.BytesIO(output), checkChecksums=2)
            for name, (advance, _) in original['hmtx'].metrics.items():
                expected = max(0, round(advance * scale) + round(tracking * original['head'].unitsPerEm)) if advance else 0
                assert font['hmtx'][name][0] == expected, (kind, tracking, scale, name)
                if 'CFF ' in font:
                    char = font['CFF '].cff.topDictIndex[0].CharStrings[name]
                    char.draw(NullPen())
                    assert char.width == expected, (name, char.width, expected)
    print(f'{kind}: PASS, negative/positive tracking, zero-width glyphs, 50–200% stretch')
