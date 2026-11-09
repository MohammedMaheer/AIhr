# Private Document Previews

PDFs (including scans) are displayed from the original upload with self-hosted
[Mozilla PDF.js](https://github.com/mozilla/pdf.js/releases/tag/v6.5.438). DOCX and
legacy DOC files are converted to PDF locally with LibreOffice. TXT files are
decoded from their original bytes, including Unicode BOMs and common legacy
Windows encoding. Cached extraction remains an explicitly separate Text view.

The converter has no network, credentials, application storage or published port.
Only its Unix socket is shared with SmartHR. It runs as UID 999 with a read-only
filesystem, dropped capabilities, bounded CPU/memory/processes and temporary
files. Each conversion has a fresh profile, disabled macros, a 30-second process
deadline and bounded input/output. Source CVs are never changed. Conversion
results are cached in application memory for five minutes, capped at 64 MiB;
ownership is checked before every cache lookup. No paid AI is used.

Copy this directory to `/opt/smarthr/preview`. Create the explicitly named socket
directory owned by the app UID/GID with mode 0750. Rehearse the worker and the
application together before merging `compose.override.yml` with the existing
VPS compose configuration. Do not expose the socket or add a published port.
This override is VPS-specific and does not replace the site's existing compose,
environment, database, storage or connected-account configuration.

Password-protected PDFs use the viewer's password prompt. Encrypted, damaged,
unsupported or over-limit Word files show an honest error with the original
download and text fallback still available. Word font substitutions can cause
minor layout differences from Microsoft Word; no pixel-perfect guarantee is made.
Scanned PDFs display visually without OCR or vector reprocessing.

Relevant upstream references:

- [LibreOffice command-line conversion](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)
- [Macro-security configuration](https://github.com/LibreOffice/core/blob/master/officecfg/registry/schema/org/openoffice/Office/Common.xcs)
