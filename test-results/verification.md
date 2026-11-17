# Export verification

Tested 2026-11-14 in isolated Chromium with the real Pyodide worker and FontFace API.

| Input | Browser download | Advance checks | FontForge validation | Tracking at 64 px |
| --- | --- | --- | --- | --- |
| Carlito TrueType subset | Passed | Every glyph +102 units | 0 | 3.13 px/character |
| FreeSans CFF subset | Passed | Every glyph +50 units | 0 | 3.13 px/character |
| Adwaita Sans Italic variable subset | Passed, static output | Every glyph +102 units | 36 | 3.07 px/character |

Tracking was +0.05 em. Pixel measurements include browser hinting and rounding. Variable before-preview uses the default static instance, preventing automatic optical sizing from changing the comparison.

Browser processing times on these small fixtures were 8, 13, and 42 ms, excluding 75 ms debounce. These are not a guarantee for full fonts.

Full-font local checks passed for all glyph advances at 100% and 120% synthetic stretch. Variable local checks instance all axes at their maxima. FontForge opened the full exports. Carlito's validation mask 36 also occurs on its unmodified source. Source outline/name warnings remain; opening successfully does not imply every source glyph is clean.

Fixed CFF nominal-width mismatch by clearing nominalWidthX/defaultWidthX before writing explicit charstring widths. Fixed original font caching across inputs and automatic optical sizing in the before preview.

Run `python scripts/verify-fonts.py` with fontTools installed and the fixture fonts at the listed system paths. Browser downloads and fixture subsets are retained locally in test-results and excluded from git.

## Negative tracking and themes

Verified 2026-11-14 after reproducing the reported invalid advance width with Carlito at -0.001 em. Tracking had made 165 zero-advance glyphs negative. Zero advances are now preserved, and other advances stop at zero.

- `python3 scripts/verify-tracking.py` passed 27 combinations across full TrueType, CFF, and variable fonts at -0.001, -0.1, and +0.05 em tracking and 50%, 100%, and 200% stretch. Every advance was checked, including decoded CFF charstring widths.
- `python3 scripts/verify-fonts.py` passed all six existing export checks, updated to preserve zero advances.
- Isolated headless Chromium passed real Pyodide generation and FontFace loading for full Carlito at -0.001 and -0.1 em. The downloaded file reopened with 2,783 glyphs and valid advances.
- Browser checks passed for dark defaults, keyboard switching, persisted light/dark choices after reload, custom specimen colors across theme changes, blocked-storage fallback, and a 390 px mobile layout without horizontal overflow. No JavaScript runtime errors occurred.
- Desktop dark/light and mobile dark screenshots, the browser harness, and the downloaded negative-tracking font are retained locally under `test-results/gui/`.

## Responsive specimens and size control

Verified 2026-11-14 in isolated headless Chromium. At an 889 px viewport, the previous layout squeezed each preview to 202.5 px, wrapping "hello, childe". The size input ended only 0.5 px above the sample box.

The updated layout stacks controls and specimens at tablet widths and gives each desktop specimen at least 22 rem before using two columns. At 889 px, each specimen now gets 741 px and the short sample stays on one line. The toolbar has a 16 px gap above the text box, with its controls aligned vertically.

Browser assertions passed at 390, 760, 761, 889, 1024, and 1440 px for toolbar separation and no horizontal page overflow. Two-column previews remain available at 1440 px. No runtime errors occurred. Before/after screenshots are retained locally as `test-results/gui/layout-before-889.png` and `test-results/gui/layout-after-889.png`.

## Special Elite cache and asynchronous loading

Verified 2026-11-14 with the reported Special Elite Regular font, 2,048 units per em and 370 glyphs. The pre-fix worker reproduced the screenshot's exact invalid advance width exception at -0.001 and -0.1 em. Current width handling passed both cases. Versioned entry and worker URLs now bypass previously cached scripts after reloading.

- A real Chromium test first cached the older application and worker, reproduced the exception, then loaded the versioned application. Special Elite adjusted and downloaded successfully at both negative tracking settings. The downloaded font reopened with 370 glyphs and valid advances.
- `python3 scripts/verify-tracking.py --font /home/artemis/Downloads/SpecialElite-Regular.ttf` passed 48 combinations across TrueType, CFF, variable, and Special Elite fixtures, including zero tracking and 50%, 100%, and 200% stretch.
- `python3 scripts/verify-fonts.py` passed all six export checks.
- `node --experimental-vm-modules scripts/verify-async.cjs` checks superseded file reads, stale inspection and generation errors, delayed FontFace results, fatal worker recovery, shared initialization, retry after engine download failure, and consistent script versions. The stale-read case failed before the fix. All cases now pass.

The browser cache harness and downloaded font are retained locally under `test-results/gui/verify-special-elite.cjs` and `test-results/gui/special-elite-negative.ttf`.

## Broader site audit

Verified 2026-11-14 after fixing additional reproducible failures.

- CID-keyed CFF adjustment failed because the worker assumed every CFF font had a single top-level Private dictionary. Each charstring now uses its own Private dictionary, including CID font dictionaries.
- Older CFF seac composites failed because the output pen had no glyph set for component expansion. Recording now decomposes those outlines before transformation.
- Tracking retained stale `hdmx` pixel advances and `LTSH` thresholds. These caches are now removed, and `OS/2.xAvgCharWidth` is refreshed from the adjusted advances.
- Export controls could copy stale or placeholder CSS while a new adjustment was pending or had failed. Both export actions now require a current result. New loads clear the previous metadata and previews, and file selection can retry the same file.
- Cross-tab theme changes reset custom specimen colors. They now preserve them, as the local switch already did.
- Font metadata now uses typographic family/style names when available and supplies usable defaults when legacy names are missing.

Validation:

- `python3 scripts/verify-edge-fonts.py` passes synthetic TrueType and CFF outline bounds, transformed composites, decoded CFF widths, all four advertised input formats, cached metric invalidation, typographic-only and missing names, and a real Noto Sans CJK CID subset.
- `node --experimental-vm-modules scripts/verify-async.cjs` passes existing races/recovery checks plus stale CSS, metadata clearing, and custom-color preservation.
- The existing 48 tracking combinations and six full-font export checks pass.
- Real Chromium/Pyodide passes load, adjustment, reset, and recovery for TTF, OTF, WOFF, WOFF2, CID-keyed CFF, and variable fonts. Empty family names and corrupt fonts disable export; loading a valid font recovers. Layout checks pass at 320, 390, 760, 761, 889, 1024, and 1440 pixels. No JavaScript runtime errors were observed.
- A deterministic sample of 39 supported system-font subsets passes three stretch/tracking combinations each, checking every glyph advance and decoded CFF charstring width. One bitmap-only font was excluded because its outlines are outside the declared supported formats. Subsetting dropped source FFTM metadata with expected fontTools warnings.

The last audit pass found no further bugs in these checks. Browser and corpus harnesses remain locally in `test-results/gui/audit-site.cjs` and `test-results/audit-corpus.py`. CFF2 support, point-attached TrueType composite stretching, and rescaling GPOS kerning remain declared limitations rather than newly supported features.

## Agent and command-line access

Verified 2026-11-17. The Python engine moved from a string in `worker.js` to `engine.py`, which the worker fetches on the release version and the new `workshop.py` command line imports. The page gained a `data-state` attribute and a `window.typeWorkshop` API, both documented in `llms.txt`.

- `python3 scripts/verify-cli.py` passes. It covers `inspect` and `adjust` JSON output, default names, overwrite protection, eleven error cases with exact messages and exit status 1, usage errors with exit status 2, and `wdth` fonts that reject `--stretch`. CLI exports for TrueType, CFF, and variable fixtures are byte-identical to direct engine output apart from the save timestamp. A 0.001 em tracking change fails the comparison, so the comparison is not vacuous.
- `node --experimental-vm-modules scripts/verify-async.cjs` passes the earlier race and recovery cases plus `data-state` transitions, API validation, API load, adjust and export, a versioned `engine.py` fetch, and retry after `engine.py` returns 404.
- `verify-fonts.py`, `verify-tracking.py`, and `verify-edge-fonts.py` pass unchanged against `engine.py`.
- Real headless Chromium with Pyodide passes `test-results/gui/verify-agents.cjs`. The file input and slider move `data-state` through `loading`, `generating`, and `ready`. The API loads fonts by URL, adjusts, and returns export bytes. Out-of-range settings reject without discarding the current export. Engine and load errors set `data-state=error`, and `reset()` recovers. The footer and `<link rel=help>` both reach `llms.txt`. No page errors and no overflow at 390 px.
- Browser exports match CLI exports for the same settings in every advance and outline. The CFF subset matched byte for byte. Carlito at 80% stretch had 18 composite glyphs and Adwaita Sans at wght 700 had 337 with recalculated bounds one unit apart. Pyodide 0.27.7 bundles fontTools 4.51.0 and this machine has 4.67.0, and the two releases round composite bounds differently.

Found during this check, not fixed: Chromium's font sanitizer rejects the full system `FreeSans.otf` ("Failed validating CharStrings INDEX"). The page passes CFF charstrings through unchanged for the Original preview, so it cannot load that font, while the CLI processes it. The subset in `test-results/cff-input.otf` loads normally.

Screenshots and exported fonts are under `test-results/gui/agents/`.

### Review pass

A second review of the same change found and fixed these holes:

- The page's tracking slider snaps to 0.001 em, so `adjust({tracking: 0.0505})` generated 0.051 while the CLI used 0.0505. Both now round half up to the step `engine.py` reports, and the CLI reports the applied value. Real Chromium applied 0.051 em, the same as the CLI.
- `adjust({width: 120})` succeeded and changed nothing. Unknown setting names, non-number values, non-string names, and a non-object `axes` now reject before the page changes.
- An empty family name reached the engine and produced a different message than the CLI. Both now reject it up front with the same message, and the current export survives.
- `load(url)` rejected URLs without a font extension, such as `download?id=3`, although the engine reads the format from the bytes. A plain array or number failed deep inside the loader. Both now behave predictably.
- `reset()` clicked a DOM button, which does nothing while that button is disabled, and the handler hard-coded `0` and `100`. It now calls the handler directly with the engine's defaults.
- The page's CSS used the untrimmed family name while the font stored the trimmed one.
- CLI JSON reported `stretch: null` for an applied 100 percent and listed only the axes passed on the command line. It now reports applied stretch and every axis location.

`verify-async.cjs` covers each API case and overlapping `adjust` calls. `verify-cli.py` covers rounding and applied-value reports. `verify-agents.cjs` repeats the rounding, unknown-setting, and empty-name checks in Chromium.
