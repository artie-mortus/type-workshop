"""Export checks for composite outlines, CID CFF, cached metrics, input formats, and font names."""
import io
import struct
import json
from pathlib import Path
import sys
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.misc.psCharStrings import T2CharString
from fontTools.ttLib import TTFont, TTCollection, newTable
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.basePen import NullPen
from fontTools import subset

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from engine import generate, inspect, moveto_surplus, width_operand

def export(font, **changes):
    stream = io.BytesIO(); font.save(stream)
    options = dict(axes={}, scale=1, tracking=.05, family='Edge Test', style='Regular')
    options.update(changes)
    return TTFont(io.BytesIO(generate(stream.getvalue(), json.dumps(options))))

def fixture(cff=False):
    builder = FontBuilder(1000, isTTF=not cff)
    names = ['.notdef', 'A', 'acute', 'Aacute', 'space']
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap({65: 'A', 193: 'Aacute', 32: 'space'})
    builder.setupHorizontalMetrics({name: (600, 0) for name in names})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable(dict(familyName='Edge Source', styleName='Regular'))
    builder.setupOS2(); builder.setupPost()
    if cff:
        strings = {}
        for name in names:
            pen = T2CharStringPen(600, None)
            if name in ['A', 'acute']:
                pen.moveTo((0, 0)); pen.lineTo((100, 0)); pen.lineTo((100, 200)); pen.closePath()
            strings[name] = pen.getCharString()
        # Deprecated seac composites still appear in otherwise valid CFF fonts.
        strings['Aacute'] = T2CharString(program=[600, 20, 200, 65, 194, 'endchar'])
        builder.setupCFF('EdgeSource', {}, strings, {})
    else:
        glyphs = {}
        for name in names:
            pen = TTGlyphPen(glyphs)
            if name == 'Aacute':
                pen.addComponent('A', (1, .25, .5, 1, 20, 200))
            elif name in ['A', 'acute']:
                pen.moveTo((0, 0)); pen.lineTo((100, 0)); pen.lineTo((100, 200)); pen.closePath()
            glyphs[name] = pen.glyph()
        builder.setupGlyf(glyphs)
    return builder.font

def check_seac():
    output = export(fixture(cff=True), scale=1.2)
    assert output['hmtx']['Aacute'][0] == 770
    verify_cff_widths(output)
    print('PASS: CFF seac composite export')

def check_cid():
    path = Path('/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc')
    if not path.exists():
        print('SKIP: CID CFF system fixture unavailable'); return
    font = TTCollection(path).fonts[0]
    sub = subset.Subsetter(); sub.populate(text='Aé中'); sub.subset(font)
    output = export(font, scale=1.2)
    assert 'CFF ' in output
    assert output['CFF '].cff.topDictIndex[0].ROS
    verify_cff_widths(output)
    print('PASS: CID-keyed CFF export')

def check_metrics():
    font = fixture()
    font['hdmx'] = newTable('hdmx'); font['hdmx'].hdmx = {16: {n: 10 for n in font.getGlyphOrder()}}
    output = export(font)
    assert 'hdmx' not in output, 'Tracking must discard cached pixel widths'
    average = output['OS/2'].xAvgCharWidth
    output['OS/2'].recalcAvgCharWidth(output)
    assert average == output['OS/2'].xAvgCharWidth, 'Average width must reflect adjusted metrics'
    # Exports without stretch skip fontTools' bounds recalculation, so the engine sets hhea itself.
    for cff in [False, True]:
        for scale in [1, 1.2]:
            output = export(fixture(cff=cff), scale=scale, tracking=.08)
            fields = ['advanceWidthMax', 'minLeftSideBearing', 'minRightSideBearing', 'xMaxExtent']
            stored = [getattr(output['hhea'], field) for field in fields]
            output['hhea'].recalc(output)
            assert stored == [getattr(output['hhea'], field) for field in fields], (cff, scale, stored)
    print('PASS: tracking invalidates device metrics and refreshes average width and hhea metrics')

def verify_cff_widths(font):
    for name in font.getGlyphOrder():
        char = font['CFF '].cff.topDictIndex[0].CharStrings[name]
        char.draw(NullPen())
        assert char.width == font['hmtx'][name][0], name

def check_geometry_and_formats():
    for cff in [False, True]:
        source = fixture(cff=cff)
        glyphs = source.getGlyphSet()
        for flavor in [None, 'woff', 'woff2']:
            source.flavor = flavor
            for scale in [.5, 1, 2]:
                output = export(source, scale=scale, tracking=-.1)
                assert output.flavor is None
                assert output['name'].getBestFamilyName() == 'Edge Test'
                for name in source.getGlyphOrder():
                    a = BoundsPen(glyphs); glyphs[name].draw(a)
                    transformed = output.getGlyphSet()
                    b = BoundsPen(transformed); transformed[name].draw(b)
                    if a.bounds is None:
                        assert b.bounds is None
                    else:
                        expected = tuple(v * scale if i % 2 == 0 else v for i, v in enumerate(a.bounds))
                        assert all(abs(x-y) <= 1 for x, y in zip(expected, b.bounds)), (cff, flavor, scale, name, expected, b.bounds)
                if cff: verify_cff_widths(output)
    print('PASS: TrueType and CFF outlines, transformed composites, TTF/OTF/WOFF/WOFF2 inputs')

def check_stray_moveto_operands():
    """FreeSans's Bsmallcap omits vstemhm, leaving stem operands before its first rmoveto.

    Browsers reject the font, and fontTools draws from the stray operands. Rasterizers use the last operands.
    """
    names = ['.notdef', 'stems', 'nostems', 'hmove', 'valid']
    square = [100, 0, 'rlineto', 0, 100, 'rlineto', -100, 0, 'rlineto', 'endchar']
    programs = {
        '.notdef': [600, 'endchar'],
        'stems': [600, 0, 50, 'hstemhm', 10, 20, 30, 40, 100, 200, 'rmoveto', *square],
        'nostems': [600, 10, 20, 100, 200, 'rmoveto', *square],
        'hmove': [600, 0, 50, 'hstemhm', 7, 8, 100, 'hmoveto', *square],
        'valid': [600, 0, 50, 'hstemhm', 100, 200, 'rmoveto', *square],
    }
    builder = FontBuilder(1000, isTTF=False)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap({65: 'stems', 66: 'nostems', 67: 'hmove', 68: 'valid'})
    builder.setupHorizontalMetrics({name: (600, 0) for name in names})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable(dict(familyName='Stray Source', styleName='Regular'))
    builder.setupOS2(); builder.setupPost()
    builder.setupCFF('StraySource', {}, {name: T2CharString(program=program) for name, program in programs.items()}, {})
    stream = io.BytesIO(); builder.font.save(stream)
    source = TTFont(io.BytesIO(stream.getvalue()))
    assert json.loads(inspect(stream.getvalue()))['repaired_glyphs'] == ['stems', 'nostems', 'hmove']
    starts = {'stems': (100, 200), 'nostems': (100, 200), 'hmove': (100, 0), 'valid': (100, 200)}
    for scale, tracking in [(1, 0), (1.5, 0.05)]:
        output = export(source, scale=scale, tracking=tracking)
        charstrings = output['CFF '].cff.topDictIndex[0].CharStrings
        glyphs = output.getGlyphSet()
        for name, (x, y) in starts.items():
            assert moveto_surplus(charstrings[name].bytecode)[1] == 0, (name, scale)
            bounds = BoundsPen(glyphs); glyphs[name].draw(bounds)
            assert bounds.bounds == (round(x * scale), y, round((x + 100) * scale), y + 100), (name, scale, bounds.bounds)
        verify_cff_widths(output)
    # Valid charstrings keep their exact bytes when nothing is adjusted.
    untouched = export(source, scale=1, tracking=0)['CFF '].cff.topDictIndex[0].CharStrings['valid'].bytecode
    assert untouched == TTFont(io.BytesIO(stream.getvalue()))['CFF '].cff.topDictIndex[0].CharStrings['valid'].bytecode
    path = Path('/usr/share/fonts/gnu-free/FreeSans.otf')
    if path.exists():
        output = export(TTFont(path), scale=1, tracking=0)
        bounds = BoundsPen(output.getGlyphSet()); output.getGlyphSet()['Bsmallcap'].draw(bounds)
        assert bounds.bounds == (60, 0, 458, 524), bounds.bounds
    print('PASS: stray operands before the first moveto are dropped, outlines land where rasterizers draw them')

def stored_flags(data):
    """Return the flag bytes a simple glyph stores, before repeats are expanded."""
    contours = struct.unpack('>h', data[:2])[0]
    end = struct.unpack(f'>{contours}H', data[10:10 + 2 * contours])
    offset = 10 + 2 * contours
    offset += 2 + struct.unpack('>H', data[offset:offset + 2])[0]
    points, flags = end[-1] + 1, []
    while points > 0:
        flag = data[offset]; offset += 1; flags.append(flag); points -= 1
        if flag & 8:
            points -= data[offset]; offset += 1
    return flags

def check_overlap_flags():
    """Adwaita Mono repeats its first flag, so fontTools decodes OVERLAP_SIMPLE onto later points.

    Stretching re-encodes those glyphs. Browsers reject bit 6 on any stored flag but the first.
    """
    font = fixture()
    for name in ['A', 'acute']:
        glyph = font['glyf'][name]
        glyph.flags[0] |= 0x40; glyph.flags[1] |= 0x40
    fonts = [('synthetic', font)]
    path = Path('/usr/share/fonts/Adwaita/AdwaitaMono-Regular.ttf')
    if path.exists():
        fonts.append(('Adwaita Mono', TTFont(path)))
    for label, source in fonts:
        output = export(source, scale=1.2)
        glyf, checked = output['glyf'], 0
        for name in output.getGlyphOrder():
            data = getattr(glyf.glyphs[name], "data", b"")
            if len(data) and struct.unpack('>h', data[:2])[0] > 0:
                flags = stored_flags(data)
                assert not any(flag & 0x40 for flag in flags[1:]), (label, name, flags[:4])
                checked += 1
        for name in ['A', 'acute'] if label == 'synthetic' else []:
            assert stored_flags(glyf.glyphs[name].data)[0] & 0x40, 'The first flag keeps OVERLAP_SIMPLE'
        assert checked
    # Without stretch or instancing, the glyf table must stay unloaded and copy through byte for byte.
    # Loading it re-encodes every glyph on save, which broke default Adwaita Mono exports.
    for label, source in fonts[1:]:
        stream = io.BytesIO(); source.save(stream)
        original = TTFont(io.BytesIO(stream.getvalue())).reader['glyf']
        for tracking in [0, 0.05]:
            assert export(source, scale=1, tracking=tracking).reader['glyf'] == original, (label, tracking)
    print('PASS: OVERLAP_SIMPLE stays on the first stored flag when stretching; unstretched glyf copies through unchanged')

def check_tracking_width_edits():
    """Tracking at 100% stretch rewrites only CFF width operands, keeping hints and subroutines."""
    from fontTools.cffLib import SubrsIndex
    from fontTools.pens.recordingPen import RecordingPen
    square = [100, 0, 'rlineto', 0, 100, 'rlineto', -100, 0, 'rlineto', 'endchar']
    programs = {
        '.notdef': ['endchar'],
        'implicit': [0, 50, 'hstem', 10, 20, 'rmoveto', *square],
        'explicit': [20, 0, 50, 'hstem', 10, 20, 'rmoveto', *square],
        'short': [1500, 0, 50, 'hstem', 10, 20, 'rmoveto', *square],  # beyond 1131, so stored as 28 xx xx
        'subrhints': [20, -107, 'callsubr', 10, 20, 'rmoveto', *square],  # subr 0 holds "0 50 hstem"
        'subrwidth': [-106, 'callsubr', 10, 20, 'rmoveto', *square],  # subr 1 holds the width too
    }
    names = list(programs)
    builder = FontBuilder(1000, isTTF=False)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap({65 + i: name for i, name in enumerate(names[1:])})
    advances = {'.notdef': 600, 'implicit': 600, 'explicit': 520, 'short': 2000, 'subrhints': 520, 'subrwidth': 530}
    builder.setupHorizontalMetrics({name: (advances[name], 10) for name in names})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable(dict(familyName='Width Source', styleName='Regular'))
    builder.setupOS2(); builder.setupPost()
    builder.setupCFF('WidthSource', {}, {name: T2CharString(program=program) for name, program in programs.items()},
                     dict(nominalWidthX=500, defaultWidthX=600))
    top = builder.font['CFF '].cff.topDictIndex[0]
    top.Private.Subrs = SubrsIndex()
    for program in [[0, 50, 'hstem', 'return'], [30, 0, 50, 'hstem', 'return']]:
        top.Private.Subrs.append(T2CharString(program=program, private=top.Private))
    for name in names:
        top.CharStrings[name].private = top.Private
    stream = io.BytesIO(); builder.font.save(stream)
    source = TTFont(io.BytesIO(stream.getvalue()))
    located = {name: width_operand(source['CFF '].cff.topDictIndex[0].CharStrings[name]) for name in names[1:]}
    assert located == {'implicit': (False, 0), 'explicit': (True, 1), 'short': (True, 3), 'subrhints': (True, 1), 'subrwidth': None}, located
    output = export(source, tracking=0.05)
    charstrings = output['CFF '].cff.topDictIndex[0].CharStrings
    original = source.getGlyphSet(); adjusted = output.getGlyphSet()
    for name in names:
        a, b = RecordingPen(), RecordingPen()
        original[name].draw(a); adjusted[name].draw(b)
        assert a.value == b.value, name
        assert output['hmtx'][name][0] == advances[name] + 50, name
    verify_cff_widths(output)
    for name in ['implicit', 'explicit', 'short', 'subrhints']:
        program = charstrings[name].program
        assert 'hstem' in program or 'callsubr' in program, f'{name} must keep its hints and subroutine calls'
    assert output['CFF '].cff.topDictIndex[0].Private.nominalWidthX == 500
    assert output['hhea'].advanceWidthMax == 2050
    print('PASS: tracking rewrites CFF widths in place across implicit, explicit, 3-byte and subroutine layouts')

def check_format_limits():
    """Widths and coordinates past 16 bits must fail with a readable error, never a corrupt font."""
    def wide_font(cff):
        builder = FontBuilder(1000, isTTF=not cff)
        builder.setupGlyphOrder(['.notdef', 'wide'])
        builder.setupCharacterMap({65: 'wide'})
        builder.setupHorizontalMetrics({'.notdef': (500, 0), 'wide': (30000, 0)})
        builder.setupHorizontalHeader(ascent=800, descent=-200)
        builder.setupNameTable(dict(familyName='Wide', styleName='Regular'))
        builder.setupOS2(); builder.setupPost()
        if cff:
            builder.setupCFF('Wide', {}, {'.notdef': T2CharString(program=['endchar']),
                                          'wide': T2CharString(program=[0, 0, 'rmoveto', 29000, 0, 'rlineto', 0, 500, 'rlineto', 'endchar'])}, {})
        else:
            glyphs = {}
            for name in ['.notdef', 'wide']:
                pen = TTGlyphPen(glyphs)
                if name == 'wide':
                    pen.moveTo((0, 0)); pen.lineTo((29000, 0)); pen.lineTo((29000, 500)); pen.closePath()
                glyphs[name] = pen.glyph()
            builder.setupGlyf(glyphs)
        return builder.font
    for cff in [False, True]:
        output = export(wide_font(cff), scale=1, tracking=0.2)
        assert output['hmtx']['wide'][0] == 30200
        if cff: verify_cff_widths(output)
        # TrueType advances are unsigned 16-bit, so 33200 fits; CFF widths stop at 32767.
        refused = [(1.2, 0), (1.1, 0.2)] if cff else [(1.2, 0)]
        if not cff:
            assert export(wide_font(cff), scale=1.1, tracking=0.2)['hmtx']['wide'][0] == 33200
        for scale, tracking in refused:
            try:
                export(wide_font(cff), scale=scale, tracking=tracking)
            except ValueError as error:
                assert 'Reduce the' in str(error), error
            else:
                raise AssertionError(f'{"CFF" if cff else "TrueType"} at {scale}x must refuse coordinates past 16 bits')
    try:
        export(wide_font(True), scale=1, tracking=2.8)
    except ValueError as error:
        assert str(error) == 'This stretch or tracking makes a glyph wider than CFF outlines can store. Reduce the adjustment.'
    else:
        raise AssertionError('A CFF width past 32767 must be refused')
    # A font without outlines gets the same hhea values fontTools would compute.
    empty = fixture()
    for name in empty.getGlyphOrder():
        empty['glyf'][name] = TTGlyphPen(None).glyph()
    output = export(empty, tracking=0.1)
    fields = ['advanceWidthMax', 'minLeftSideBearing', 'minRightSideBearing', 'xMaxExtent']
    stored = [getattr(output['hhea'], field) for field in fields]
    output['hhea'].recalc(output)
    assert stored == [getattr(output['hhea'], field) for field in fields], stored
    print('PASS: 16-bit width and coordinate limits fail with readable errors; outline-free hhea matches fontTools')

def check_names():
    font = fixture()
    font['name'].names = []
    stream = io.BytesIO(); font.save(stream)
    metadata = json.loads(inspect(stream.getvalue()))
    assert metadata['family'] == 'Untitled' and metadata['style'] == 'Regular'
    for name_id, value in [(16, 'Typographic Family'), (17, 'Book')]:
        font['name'].setName(value, name_id, 3, 1, 0x409)
    stream = io.BytesIO(); font.save(stream)
    metadata = json.loads(inspect(stream.getvalue()))
    assert metadata['family'] == 'Typographic Family' and metadata['style'] == 'Book'
    print('PASS: missing legacy names and typographic-only family/style names')

if __name__ == '__main__':
    failures = []
    for check in [check_seac, check_cid, check_metrics, check_geometry_and_formats, check_stray_moveto_operands, check_overlap_flags, check_tracking_width_edits, check_format_limits, check_names]:
        try: check()
        except Exception as error:
            failures.append(error); print(f'FAIL: {check.__name__}: {type(error).__name__}: {error}')
    assert not failures, f'{len(failures)} export checks failed'
