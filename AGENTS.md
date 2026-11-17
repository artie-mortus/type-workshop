# Type workshop

Static font adjustment page plus a command line. Read `README.md` for usage and `llms.txt` for the automation contract.

## One engine, two runtimes

`engine.py` is the only font-processing code. `worker.js` fetches it and runs it in Pyodide 0.27.7. `workshop.py` and every `scripts/verify-*.py` import it under CPython. Keep its imports to the standard library, fontTools, and brotli, because those are the packages the worker loads.

Reading `f['glyf']` makes fontTools re-encode every glyph on save. Only the stretch and variable-instancing paths may load it. Other paths must leave it unloaded so the original glyph bytes copy through, which `verify-edge-fonts.py` checks.

`generate()` lets fontTools recalculate bounds on save only when `outlines_changed` is true, because recalculating every glyph's bounds dominates export time on large fonts. Any new code that moves or reshapes outlines must set it. When advances change without outline changes, `update_hhea()` sets the width-dependent `hhea` fields itself.

Adjustment limits live in `engine.TRACKING_RANGE`, `engine.TRACKING_STEP`, and `engine.STRETCH_RANGE`. `inspect()` reports them as `adjustments`. The page sliders, the page API, and the CLI all read limits from there. The `min` and `max` on the sliders in `index.html` are placeholders until a font loads.

## Public contract

`llms.txt` documents what outside agents rely on: CLI flags and `--json` output, exit codes, `window.typeWorkshop`, the `data-state` values, and control selectors. Update it in the same change as any of those.

Checks that both sides make (ranges, axis names, empty names) use the same messages in `workshop.py` and the API in `app.js`, except where a message names a CLI flag. Both round tracking with the formula in `engine.py`. `scripts/verify-cli.py` asserts the CLI strings and `scripts/verify-async.cjs` asserts the API strings, so change both sides together.

## Releases

`index.html` loads `app.js?v=<release>`. The page passes that query to `worker.js`, and the worker passes it to `engine.py`. Bump it in any change to those three files so browsers fetch them together.

## Verification

Run all of these after engine, worker, or app changes:

```sh
python3 scripts/verify-fonts.py
python3 scripts/verify-tracking.py
python3 scripts/verify-edge-fonts.py
python3 scripts/verify-cli.py
node --experimental-vm-modules scripts/verify-async.cjs
```

The Python checks use system fonts under `/usr/share/fonts`. Playwright is not a project dependency. For real-browser checks, install it in a scratch directory, launch `/usr/bin/chromium` headless and muted, and serve the project on a random free port. Record results in `test-results/verification.md`. Keep screenshots and harnesses under `test-results/gui/`, which git ignores.
