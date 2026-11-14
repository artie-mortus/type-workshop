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
