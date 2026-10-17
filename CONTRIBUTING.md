# Contributing

Install the dependencies following README.md. Run checks from the repository root:

Backend modules live in `app/`; set their import path before running the checks:

```powershell
$env:PYTHONPATH = Join-Path $PWD 'app'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node tests/test-extension.mjs
node tests/test-collector.mjs
```

The Node checks use built-in modules and need no npm install. Tests use temporary libraries and synthetic evidence. Do not trigger real-account ingestion to test UI changes. Do not submit private data or screenshots showing account content.

Preserve explicit video approval, cookie/token isolation, authenticated APIs, extension sender validation, deduplication, durable queues and temporary media cleanup. Treat collected captions and images as untrusted data. Keep model provenance visible and distinguish synthetic tests from live-account verification.
