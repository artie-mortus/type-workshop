# Type workshop

Adjusts a font's tracking, width, and variable axes, then exports a static TTF or OTF under a new name. You can use it as a web page or from the command line. Both run the same engine, and font bytes stay on your device either way.

Dark mode is the default. Use the light switch on the right to select the original light palette. Your choice is saved in this browser when local storage is available.

## Run locally

From this directory:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open http://localhost:8000. Use HTTP rather than opening index.html directly because the app uses a Web Worker.

To deploy, copy these files to any static web host:

- the page: `index.html`, `style.css`, `app.js`, `worker.js`, `engine.py`
- the automation guide and CLI it links to: `llms.txt`, `workshop.py`
- the icons: `icon.svg`, `favicon.ico`, `apple-touch-icon.png`

No build step or backend is required. The first font load downloads Pyodide, fontTools, and Brotli from jsDelivr, so the page needs an internet connection.

## Command line

`workshop.py` needs Python 3 with `fonttools` and `brotli` installed (`python3 -m pip install fonttools brotli`).

```sh
python3 workshop.py inspect Font.ttf
python3 workshop.py adjust Font.ttf --tracking 0.05 --stretch 120 -o Font-Wide.ttf --css
python3 workshop.py adjust Variable.ttf --axis wght=700 --family "My Sans"
```

`inspect` lists the font's axes and the adjustment ranges that apply to it. The ranges match the page's sliders. Add `--json` to either command for one JSON object on stdout, including font and adjustment errors. `python3 workshop.py adjust --help` lists every flag.

## Automation

[`llms.txt`](llms.txt) is the guide for AI agents and scripts. It covers the CLI's JSON contract, the page's `window.typeWorkshop` API, and the `data-state` attribute that tells browser automation when an export is ready. The page footer links to it.

## Verification status

TrueType, CFF, and variable browser exports were downloaded and reopened in FontForge. Every exported advance was checked against the expected font-unit adjustment. Full-font transformation checks cover tracking and 120% stretch. See [verification evidence](test-results/verification.md) for measurements, source warnings, and limitations.

CFF2 outlines remain unsupported. Processing latency depends on font size and device speed.

Tracking keeps combining marks and other zero-advance glyphs at zero. Negative tracking stops other advances at zero so tight spacing can still export a valid font. Run `python3 scripts/verify-tracking.py` to check negative and positive tracking across TrueType, CFF, and variable fonts using the same system fixtures as the export checks.

For a reported font, add `--font /path/to/font.ttf` to the tracking checks. The matrix includes unchanged tracking as well as negative and positive adjustments.

Run `node --experimental-vm-modules scripts/verify-async.cjs` for deterministic file-selection races, worker initialization, and failure recovery checks. This uses Node's built-in modules and mocks the DOM and Python engine. It also covers the automation API's state transitions and validation.

Run `python3 scripts/verify-cli.py` for the command line's JSON output, exit codes, and validation messages. It also checks that CLI exports are byte-identical to the engine's, ignoring the save timestamp.

The entry script URL in `index.html` carries a release version. The page forwards it to `worker.js`, which forwards it to `engine.py`. Bump that version whenever you ship application, worker, or engine changes so browsers fetch all three together.

Run `python3 scripts/verify-edge-fonts.py` for synthetic composite geometry, compressed input formats, cached-width invalidation, font-name fallbacks, and CID-keyed CFF checks. The CID case uses the system Noto Sans CJK collection when available. CFF exports support both CID private dictionaries and older seac composite outlines. Some FontForge builds, including the one behind FreeSans, leave stem operands before a glyph's first move. Browsers reject such fonts, and fontTools draws the glyph in the wrong place. The engine drops those operands as FreeType does, and `inspect` lists the glyphs it repaired. Tracking discards cached device widths and refreshes the average-width metadata.

Changing a font or adjustment clears the previous export until a new font is ready. Copy CSS and Download remain disabled during generation or after an error.

## Icon

The icon is a serif "Ab" over a tracking arrow, drawn from DejaVu Serif Bold outlines in the dark palette. Run `python3 scripts/make-icon.py` to rebuild all three icon files. It needs fontTools, `rsvg-convert`, DejaVu Serif Bold at `/usr/share/fonts/TTF/DejaVuSerif-Bold.ttf`, and ImageMagick.
