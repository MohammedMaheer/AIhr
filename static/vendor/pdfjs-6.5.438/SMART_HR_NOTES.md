# PDF.js Distribution

Mozilla PDF.js v6.5.438, legacy generic distribution, Apache-2.0 license.

Source: https://github.com/mozilla/pdf.js/releases/tag/v6.5.438

Archive: `pdfjs-6.5.438-legacy-dist.zip`

SHA-256: `55138aa33b5f1f6f68809895338b947f395f344eb6381d424b2420d6daa6a844`

Source maps and the public example PDF are omitted. Runtime files are unmodified.
SmartHR lazy-loads the self-hosted viewer with an authorized in-memory document.
The `webviewerloaded` integration disables PDF scripting, preference overrides,
AI/alt-text model downloads and annotation editing before viewer initialization.
No CV is sent to Mozilla or an external document-viewing service.
