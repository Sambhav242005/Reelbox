# Recording and measuring Reelbox

The public demo uses GitHub, AI, coding and technology reels only. Manga, manhwa, anime and gaming are excluded using both source text and existing folder memberships. The 20 featured reels are drawn from a 50-reel sample across AI, Technology, Code, UI and Useful Projects.

## What is measured

The isolated run uses cached source titles, captions and covers with fresh local inference. It does not measure Instagram collection, media retrieval, video analysis, model loading or cold starts. Two separate warm-up reels are excluded. There are five application workers; the inference service controls actual scheduling.

The recording uses MiniCPM-V 4.6 (`minicpm-v4.6:latest`), quantized as Q4_K_M. Its Qwen language backbone explains the `qwen35` family reported by Ollama. See [the recorded benchmark metadata](media/benchmark.json) for hardware and timings. Folder assignments have not been manually scored.

The MP4 plays at normal speed, with captions and a visible cursor. The raw WebM and private timeline are in `work/demo/recording/`; public exports are in `docs/media/`.

## Repeat the workflow

Use the normal Python environment and install the optional Node dependencies from the repository root:

```powershell
npm ci --prefix app
node app/node_modules/playwright-core/cli.js install ffmpeg
```

The recorder uses the installed Microsoft Edge browser in a fresh headless context, not your signed-in browser profile. FFmpeg and FFprobe must also be on PATH for sample validation and final exports. The exporter currently uses the Windows Segoe UI font.

Archive any existing `work/demo/` after stopping its disposable server. Preparation refuses to overwrite an existing sample; serving refuses to repeat a started benchmark.

```powershell
.\.venv\Scripts\python.exe scripts/demo-library.py prepare
.\.venv\Scripts\python.exe scripts/demo-library.py serve
```

The source library is opened read-only. Preparation selects ten complete, readable-cover reels from each of five permitted topics in Saved order, deduplicates them and chooses four per topic for the showcase. It copies source evidence and folder descriptions only. Credentials, original analyses, assignments and inference caches are not copied. Server guards block Instagram retrieval and video downloads. The isolated server starts paused on port 8770.

In another terminal, run each phase in order:

```powershell
node scripts/record-demo.mjs --discover
node scripts/record-demo.mjs --rehearse
node scripts/record-demo.mjs --record
.\.venv\Scripts\python.exe scripts/demo-library.py report
.\.venv\Scripts\python.exe scripts/finish-demo.py
```

Discovery saves a map of the page's controls. Rehearsal checks the panel, reel navigation and folders without starting inference. Recording requires a passed rehearsal and resumes only the isolated service. The report checks the source library's fingerprint and reads the model metadata. Export accepts recordings between 30 and 45 seconds and leaves playback speed unchanged.

## Permanent processing panel

The panel sits above the collection. Unorganized represents queued work, Organizing shows active backend stages, and Organized requires a successful analysis and at least one folder assignment. Review, model waits and errors are separate. Use the follow button on a queued/active reel to keep the same card visible through its transition, then open its folder with the arrow. The existing processing controls remain available.

The authenticated `GET /api/processing` response preserves existing fields and adds:

- `observed_at`: snapshot time; the UI rejects older responses.
- `metrics`: current batch ID, tracked unique reels, successful organization/review/error totals, first-claim and completion times, wall-clock duration, successful reels per minute, and median successful-reel duration. Unmeasured durations/rates are `null`.
- `board`: library-wide counts and bounded card lists, independent of collection filters and pagination.

`processing_runs` and `processing_timings` are additive SQLite tables. The first claim starts a timing; retries reuse its batch/reel key and first timestamp. Pauses, waits and restarts remain part of wall time. A completed run's clock freezes until more work is admitted. Old records and metadata-only backfills do not create historical inference timings. Existing batch `completed` still includes review/error outcomes and must not be substituted for `metrics.organized`.

The board polls every 500ms while work is active and every two seconds when idle. Motion follows confirmed states using transform/opacity and is disabled for reduced motion. A polite live region announces successful transitions; it does not announce every ticking number.

## Checks

```powershell
$env:PYTHONPATH = Join-Path $PWD 'app'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node tests/test-extension.mjs
node tests/test-collector.mjs
# Uses the disposable service, never port 8765:
node tests/test-processing-ui.mjs
```

The browser check uses simulated processing responses to exercise transitions, distinct outcomes, both themes, mobile widths and reduced motion. The public recording uses real inference, not those simulated responses.

Recording follows the ui-demo Discover → Rehearse → Record workflow. Implementation references: [Playwright recording lifecycle](https://playwright.dev/docs/videos), [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html), and the modern-web-guidance motion guide (transform/opacity and reduced-motion handling).
