#!/usr/bin/env python3
"""Inspect and adjust fonts from the command line.

Uses the same engine as the browser page, so a CLI export matches a browser
export made with the same settings. Requires fontTools and brotli.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FONT_SUFFIXES = {'.ttf', '.otf', '.woff', '.woff2'}

EXAMPLES = """examples:
  %(prog)s inspect Font.ttf --json
  %(prog)s adjust Font.ttf --tracking 0.05 --stretch 120 -o Font-Wide.ttf
  %(prog)s adjust Variable.ttf --axis wght=700 --axis wdth=87.5 --family "My Sans"

exit status: 0 success, 1 font or adjustment error, 2 invalid arguments.
With --json, results and font or adjustment errors print as one JSON object
on stdout. Invalid arguments print usage to stderr instead."""


class WorkshopError(Exception):
    pass


def load_engine():
    try:
        import engine
    except ImportError as error:
        raise WorkshopError(f'{error}. Install the engine dependencies with: python3 -m pip install fonttools brotli')
    return engine


def font_bytes(path):
    if path.suffix.lower() not in FONT_SUFFIXES:
        raise WorkshopError(f'Unsupported file extension "{path.suffix}". Use TTF, OTF, WOFF or WOFF2.')
    try:
        return path.read_bytes()
    except OSError as error:
        raise WorkshopError(f'Cannot read {path}: {error.strerror}')


def describe(engine, path):
    data = font_bytes(path)
    try:
        meta = json.loads(engine.inspect(data))
    except Exception as error:
        raise WorkshopError(f'Cannot load this font: {error}')
    meta['path'] = str(path)
    return data, meta


def parse_axes(pairs, meta):
    axes = {}
    available = {a['tag']: a for a in meta['axes']}
    for pair in pairs:
        tag, separator, value = pair.partition('=')
        if not separator:
            raise WorkshopError(f'Axis "{pair}" must use TAG=VALUE, for example wght=700.')
        if tag not in available:
            names = ', '.join(available) or 'none'
            raise WorkshopError(f'This font has no "{tag}" axis. Available axes: {names}.')
        try:
            number = float(value)
        except ValueError:
            raise WorkshopError(f'Axis {tag} value "{value}" is not a number.')
        axis = available[tag]
        if not axis['min'] <= number <= axis['max']:
            raise WorkshopError(f'Axis {tag} must be between {axis["min"]:g} and {axis["max"]:g}.')
        axes[tag] = number
    return axes


def round_to_step(value, step):
    """Round half up to the page slider's grid, exactly as app.js does."""
    n = round(1 / step)
    return math.floor(value * n + 0.5) / n


def css_for(family, filename):
    return (
        '@font-face {\n'
        f'  font-family: {json.dumps(family)};\n'
        f'  src: url({json.dumps(filename)});\n'
        '  font-style: normal;\n'
        '  font-weight: 400;\n'
        '}'
    )


def run_inspect(args):
    _, meta = describe(load_engine(), args.font)
    if args.json:
        return meta
    axes = ', '.join(f'{a["tag"]} {a["min"]:g} to {a["max"]:g} (default {a["default"]:g})' for a in meta['axes'])
    tracking, stretch = meta['adjustments']['tracking'], meta['adjustments']['stretch']
    lines = [
        f'{meta["family"]} / {meta["style"]}',
        f'{meta["upem"]} units per em, {meta["glyphs"]} glyphs, {"CFF" if meta["outlines"] == "cff" else "TrueType"} outlines',
        f'Axes: {axes or "none"}',
        f'Tracking: {tracking["min"]:g} to {tracking["max"]:g} em',
        f'Stretch: {stretch["min"]:g} to {stretch["max"]:g} percent' if stretch else 'Stretch: use --axis wdth=VALUE',
        f'Exports as: .{meta["output_format"]}',
    ]
    if meta['repaired_glyphs']:
        lines.append(f'Repaired outlines: {", ".join(meta["repaired_glyphs"])} (stray operands before the first move)')
    return '\n'.join(lines)


def run_adjust(args):
    engine = load_engine()
    data, meta = describe(engine, args.font)
    tracking, stretch = meta['adjustments']['tracking'], meta['adjustments']['stretch']
    if not tracking['min'] <= args.tracking <= tracking['max']:
        raise WorkshopError(f'Tracking must be between {tracking["min"]:g} and {tracking["max"]:g} em.')
    if args.stretch is not None:
        if stretch is None:
            width = meta['adjustments']['axes']['wdth']
            raise WorkshopError(f'This font has a wdth axis. Use --axis wdth=VALUE ({width["min"]:g} to {width["max"]:g}) instead of --stretch.')
        if not stretch['min'] <= args.stretch <= stretch['max']:
            raise WorkshopError(f'Stretch must be between {stretch["min"]:g} and {stretch["max"]:g} percent.')
    axes = parse_axes(args.axis, meta)
    family = (args.family if args.family is not None else meta['family'] + ' Workshop').strip()
    style = (args.style if args.style is not None else meta['style']).strip()
    if not family or not style:
        raise WorkshopError('Family and style names cannot be empty.')

    extension = '.' + meta['output_format']
    output = args.output or Path(re.sub(r'[^a-zA-Z0-9_-]', '-', args.font.stem) + '-workshop' + extension)
    warnings = []
    if output.suffix.lower() != extension:
        warnings.append(f'{output.name} has {meta["outlines"]} outlines, which normally use the {extension} extension.')
    if output.resolve() == args.font.resolve():
        raise WorkshopError('The output path is the input font. Choose a different --output.')
    if output.exists() and not args.force:
        raise WorkshopError(f'{output} already exists. Pass --force to overwrite it.')

    applied_tracking = round_to_step(args.tracking, tracking['step'])
    applied_stretch = None if stretch is None else (args.stretch if args.stretch is not None else stretch['default'])
    location = {tag: axes.get(tag, axis['default']) for tag, axis in meta['adjustments']['axes'].items()}
    scale = 1 if applied_stretch is None else applied_stretch / 100
    options = dict(axes=location, tracking=applied_tracking, scale=scale, family=family, style=style)
    try:
        result = engine.generate(data, json.dumps(options))
    except Exception as error:
        raise WorkshopError(f'Cannot process this font: {error}')
    try:
        output.write_bytes(result)
    except OSError as error:
        raise WorkshopError(f'Cannot write {output}: {error.strerror}')

    css = css_for(family, output.name)
    if args.json:
        return dict(
            output=str(output), bytes=len(result), format=meta['output_format'],
            family=family, style=style, tracking=applied_tracking,
            stretch=applied_stretch, axes=location, repaired_glyphs=meta['repaired_glyphs'], css=css, warnings=warnings,
        )
    for warning in warnings:
        print(f'warning: {warning}', file=sys.stderr)
    message = f'Wrote {output} ({len(result):,} bytes) as "{family}" {style}.'
    if meta['repaired_glyphs']:
        message += f'\nRepaired outlines: {", ".join(meta["repaired_glyphs"])}'
    return message + ('\n\n' + css if args.css else '')


def build_parser():
    parser = argparse.ArgumentParser(
        prog='workshop.py', description=__doc__.split('\n\n')[0],
        epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest='command', required=True)

    inspect = commands.add_parser('inspect', help='show names, metrics, axes and allowed adjustments')
    inspect.add_argument('font', type=Path, help='TTF, OTF, WOFF or WOFF2 file')
    inspect.add_argument('--json', action='store_true', help='print one JSON object')
    inspect.set_defaults(run=run_inspect)

    adjust = commands.add_parser('adjust', help='write an adjusted copy of a font')
    adjust.add_argument('font', type=Path, help='TTF, OTF, WOFF or WOFF2 file')
    adjust.add_argument('-o', '--output', type=Path, help='output path (default: <font>-workshop.ttf or .otf in the current directory)')
    adjust.add_argument('--tracking', type=float, default=0, metavar='EM', help='letter spacing in em (default 0), rounded to 0.001; inspect shows the allowed range')
    adjust.add_argument('--stretch', type=float, metavar='PERCENT', help='synthetic horizontal stretch (default 100); inspect shows the allowed range. Fonts with a wdth axis use --axis wdth=VALUE')
    adjust.add_argument('--axis', action='append', default=[], metavar='TAG=VALUE', help='variable axis location, repeatable; unset axes use their defaults')
    adjust.add_argument('--family', help='family name (default: source family + " Workshop")')
    adjust.add_argument('--style', help='style name (default: source style)')
    adjust.add_argument('--css', action='store_true', help='also print @font-face CSS')
    adjust.add_argument('--force', action='store_true', help='overwrite an existing output file')
    adjust.add_argument('--json', action='store_true', help='print one JSON object, including the CSS')
    adjust.set_defaults(run=run_adjust)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = args.run(args)
    except WorkshopError as error:
        if args.json:
            print(json.dumps(dict(error=str(error))))
        else:
            print(f'error: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2) if args.json else result)
    return 0


if __name__ == '__main__':
    sys.exit(main())
