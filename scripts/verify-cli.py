"""Command-line checks: JSON contract, exit codes, validation, and engine parity."""
import io
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from fontTools.ttLib import TTFont

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from engine import generate

FIXTURES = {
    'ttf': Path('/usr/share/fonts/carlito/Carlito-Regular.ttf'),
    'cff': Path('/usr/share/fonts/gnu-free/FreeSans.otf'),
    'variable': Path('/usr/share/fonts/Adwaita/AdwaitaSans-Italic.ttf'),
}


def cli(*args, cwd=None):
    run = subprocess.run([sys.executable, str(root / 'workshop.py'), *map(str, args)], capture_output=True, text=True, cwd=cwd)
    return run.returncode, run.stdout, run.stderr


def same_font(a, b):
    """Compare raw bytes, ignoring the head save timestamp and the whole-file checksum."""
    def normalized(data):
        data = bytearray(data)
        tables = struct.unpack('>H', data[4:6])[0]
        for record in range(12, 12 + tables * 16, 16):
            if data[record:record + 4] == b'head':
                offset = struct.unpack('>I', data[record + 8:record + 12])[0]
                data[offset + 8:offset + 12] = bytes(4)  # checkSumAdjustment
                data[offset + 28:offset + 36] = bytes(8)  # modified
                data[record + 4:record + 8] = bytes(4)  # head table checksum
        return bytes(data)
    assert normalized(a) == normalized(b), 'CLI output differs from the engine output'


def check_inspect():
    code, out, _ = cli('inspect', FIXTURES['variable'], '--json')
    meta = json.loads(out)
    assert code == 0
    assert meta['outlines'] == 'truetype' and meta['output_format'] == 'ttf'
    assert {'opsz', 'wght'} <= set(meta['adjustments']['axes'])
    assert meta['adjustments']['tracking'] == dict(min=-0.1, max=0.2, default=0, step=0.001, unit='em')
    code, out, _ = cli('inspect', FIXTURES['cff'], '--json')
    assert json.loads(out)['output_format'] == 'otf'
    assert json.loads(out)['repaired_glyphs'] == ['Bsmallcap'] and meta['repaired_glyphs'] == []
    code, out, _ = cli('inspect', FIXTURES['ttf'])
    assert code == 0 and 'Tracking: -0.1 to 0.2 em' in out
    print('PASS: inspect reports outlines, output format, axes and allowed ranges')


def check_parity(work):
    # Tracking rounds half up to the slider's 0.001 em step, matching app.js.
    cases = [
        ('ttf', ['--tracking', '-0.05', '--stretch', '120'], dict(axes={}, tracking=-0.05, scale=1.2), dict(tracking=-0.05, stretch=120, axes={})),
        ('cff', ['--tracking', '0.0505', '--stretch', '80'], dict(axes={}, tracking=0.051, scale=0.8), dict(tracking=0.051, stretch=80, axes={})),
        ('variable', ['--tracking', '0.1', '--axis', 'wght=700'], dict(axes=dict(wght=700), tracking=0.1, scale=1), dict(tracking=0.1, stretch=100, axes=dict(opsz=14, wght=700))),
    ]
    for kind, flags, options, applied in cases:
        output = work / f'{kind}-parity'
        code, out, err = cli('adjust', FIXTURES[kind], *flags, '--family', 'Parity Sans', '--style', 'Bold', '-o', output, '--json')
        assert code == 0, err
        report = json.loads(out)
        assert report['output'] == str(output) and report['family'] == 'Parity Sans'
        assert {key: report[key] for key in applied} == applied, 'The report must show the applied settings'
        assert report['warnings'], 'An output path without the font extension must warn'
        expected = generate(FIXTURES[kind].read_bytes(), json.dumps(dict(options, family='Parity Sans', style='Bold')))
        same_font(output.read_bytes(), expected)
        print(f'PASS: {kind} CLI export matches the engine for {" ".join(flags)}')


def check_defaults(work):
    code, out, err = cli('adjust', FIXTURES['cff'], '--json', cwd=work)
    assert code == 0, err
    report = json.loads(out)
    assert report['output'] == 'FreeSans-workshop.otf' and report['family'] == 'FreeSans Workshop'
    assert report['warnings'] == [] and 'src: url("FreeSans-workshop.otf")' in report['css']
    assert report['repaired_glyphs'] == ['Bsmallcap'], 'adjust must report outlines the engine repaired'
    assert TTFont(work / report['output'])['name'].getDebugName(1) == 'FreeSans Workshop'
    code, out, _ = cli('adjust', FIXTURES['cff'], '--json', cwd=work)
    assert code == 1 and 'already exists' in json.loads(out)['error']
    code, _, _ = cli('adjust', FIXTURES['cff'], '--json', '--force', cwd=work)
    assert code == 0
    print('PASS: default output name and family, overwrite protection, --force')


def check_errors(work):
    target = work / 'unused.ttf'
    corrupt = work / 'corrupt.ttf'
    corrupt.write_bytes(b'not a font')
    cases = [
        (['adjust', FIXTURES['ttf'], '--tracking', '0.3'], 'Tracking must be between -0.1 and 0.2 em.'),
        (['adjust', FIXTURES['ttf'], '--stretch', '20'], 'Stretch must be between 50 and 200 percent.'),
        (['adjust', FIXTURES['ttf'], '--axis', 'wght=700'], 'This font has no "wght" axis. Available axes: none.'),
        (['adjust', FIXTURES['variable'], '--axis', 'wght'], 'Axis "wght" must use TAG=VALUE, for example wght=700.'),
        (['adjust', FIXTURES['variable'], '--axis', 'wght=2000'], 'Axis wght must be between 100 and 900.'),
        (['adjust', FIXTURES['ttf'], '--family', ' '], 'Family and style names cannot be empty.'),
        (['adjust', FIXTURES['ttf'], '-o', FIXTURES['ttf']], 'The output path is the input font. Choose a different --output.'),
        (['inspect', work / 'notes.txt'], 'Unsupported file extension ".txt". Use TTF, OTF, WOFF or WOFF2.'),
        (['inspect', work / 'missing.ttf'], f'Cannot read {work / "missing.ttf"}: No such file or directory'),
    ]
    for args, message in cases:
        if args[0] == 'adjust' and '-o' not in args:
            args = [*args, '-o', target]
        code, out, err = cli(*args, '--json')
        assert (code, json.loads(out), err) == (1, dict(error=message), ''), (args, code, out, err)
        code, out, err = cli(*args)
        assert (code, out, err.strip()) == (1, '', f'error: {message}'), (args, code, out, err)
    code, out, _ = cli('inspect', corrupt, '--json')
    assert code == 1 and json.loads(out)['error'].startswith('Cannot load this font:')
    assert not target.exists(), 'Failed adjustments must not write output'
    code, _, err = cli('adjust', FIXTURES['ttf'], '--tracking', 'wide')
    assert code == 2 and 'invalid float value' in err
    print(f'PASS: {len(cases) + 2} error cases report exit 1 with stable messages, usage errors exit 2')


def check_wdth(work):
    font = TTFont(FIXTURES['variable'])
    axis = font['fvar'].axes[0]
    axis.axisTag = 'wdth'
    axis.minValue, axis.defaultValue, axis.maxValue = 75, 100, 125
    for record in font['fvar'].instances:
        record.coordinates['wdth'] = record.coordinates.pop('opsz')
    path = work / 'wdth.ttf'
    font.save(path)
    code, out, _ = cli('inspect', path, '--json')
    assert json.loads(out)['adjustments']['stretch'] is None
    code, out, _ = cli('adjust', path, '--stretch', '120', '--json')
    assert code == 1 and json.loads(out)['error'] == 'This font has a wdth axis. Use --axis wdth=VALUE (75 to 125) instead of --stretch.'
    code, out, err = cli('adjust', path, '--axis', 'wdth=110', '-o', work / 'wdth-out.ttf', '--json')
    assert code == 0, err
    print('PASS: fonts with a wdth axis route width through --axis')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        failures = []
        for check in [check_inspect, lambda: check_parity(work), lambda: check_defaults(work), lambda: check_errors(work), lambda: check_wdth(work)]:
            try:
                check()
            except Exception as error:
                failures.append(error)
                print(f'FAIL: {type(error).__name__}: {error}')
        assert not failures, f'{len(failures)} CLI checks failed'
