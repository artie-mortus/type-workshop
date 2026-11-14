# Type workshop

Static, browser-side font adjustment tool. Font bytes stay on your device.

Dark mode is the default. Use the light switch on the right to select the original light palette. Your choice is saved in this browser when local storage is available.

## Run locally

From this directory:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open http://localhost:8000. Use HTTP rather than opening index.html directly because the app uses a Web Worker.

Deploy the four application files to any static web host. No build step or backend is required. The first font load downloads Pyodide, fontTools, and Brotli from jsDelivr, so an internet connection is required.

## Verification status

TrueType, CFF, and variable browser exports were downloaded and reopened in FontForge. Every exported advance was checked against the expected font-unit adjustment. Full-font transformation checks cover tracking and 120% stretch. See [verification evidence](test-results/verification.md) for measurements, source warnings, and limitations.

CFF2 outlines remain unsupported. Processing latency depends on font size and device speed.

Tracking keeps combining marks and other zero-advance glyphs at zero. Negative tracking stops other advances at zero so tight spacing can still export a valid font. Run `python3 scripts/verify-tracking.py` to check negative and positive tracking across TrueType, CFF, and variable fonts using the same system fixtures as the export checks.
