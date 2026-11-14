# Type workshop

Static, browser-side font adjustment tool. Font bytes stay on your device.

## Run locally

From this directory:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open http://localhost:8000. Use HTTP rather than opening index.html directly because the app uses a Web Worker.

Deploy the four application files to any static web host. No build step or backend is required. The first font load downloads Pyodide, fontTools, and Brotli from jsDelivr, so an internet connection is required.

## Verification status

JavaScript syntax checks passed. A local Python check reopened a transformed TrueType export and verified its advance width. Browser processing, CFF exports, variable font exports, FontForge compatibility, and the 150 ms response target still need acceptance testing. CFF2 outlines are explicitly rejected.
