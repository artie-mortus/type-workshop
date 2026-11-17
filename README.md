# Type workshop

Static, browser-side font adjustment tool. Font bytes stay on your device.

Dark mode is the default. Use the light switch on the right to select the original light palette. Your choice is saved in this browser when local storage is available.

## Run locally

From this directory:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open http://localhost:8000. Use HTTP rather than opening index.html directly because the app uses a Web Worker.

Deploy the four application files and the three icon files (`icon.svg`, `favicon.ico`, `apple-touch-icon.png`) to any static web host. No build step or backend is required. The first font load downloads Pyodide, fontTools, and Brotli from jsDelivr, so an internet connection is required.

## Verification status

TrueType, CFF, and variable browser exports were downloaded and reopened in FontForge. Every exported advance was checked against the expected font-unit adjustment. Full-font transformation checks cover tracking and 120% stretch. See [verification evidence](test-results/verification.md) for measurements, source warnings, and limitations.

CFF2 outlines remain unsupported. Processing latency depends on font size and device speed.

Tracking keeps combining marks and other zero-advance glyphs at zero. Negative tracking stops other advances at zero so tight spacing can still export a valid font. Run `python3 scripts/verify-tracking.py` to check negative and positive tracking across TrueType, CFF, and variable fonts using the same system fixtures as the export checks.

For a reported font, add `--font /path/to/font.ttf` to the tracking checks. The matrix includes unchanged tracking as well as negative and positive adjustments.

Run `node --experimental-vm-modules scripts/verify-async.cjs` for deterministic file-selection races, worker initialization, and failure recovery checks. This uses Node's built-in modules and mocks the DOM and Python engine.

The entry script URL in `index.html` carries a release version, which is forwarded to the worker URL. Bump that version whenever shipping application or worker changes so browsers fetch both scripts together.

Run `python3 scripts/verify-edge-fonts.py` for synthetic composite geometry, compressed input formats, cached-width invalidation, font-name fallbacks, and CID-keyed CFF checks. The CID case uses the system Noto Sans CJK collection when available. CFF exports support both CID private dictionaries and older seac composite outlines. Tracking discards cached device widths and refreshes the average-width metadata.

Changing a font or adjustment clears the previous export until a new font is ready. Copy CSS and Download remain disabled during generation or after an error.

## Icon

The icon is a serif "Ab" over a tracking arrow, drawn from DejaVu Serif Bold outlines in the dark palette. Run `python3 scripts/make-icon.py` to rebuild all three icon files. It needs fontTools, `rsvg-convert`, DejaVu Serif Bold at `/usr/share/fonts/TTF/DejaVuSerif-Bold.ttf`, and ImageMagick.
