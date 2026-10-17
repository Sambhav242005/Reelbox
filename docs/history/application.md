# Historical implementation and operation notes

These notes include superseded D1-first defaults and workspace paths. For current installation and usage, use [README](../../README.md) and [USAGE](../USAGE.md). Later sections record subsequent changes.

# Reelbox

A local library for Instagram saved reels, using D1 first for decisions and MiniCPM for visual understanding and writing when needed.

## Start the server

Double-click `Start Reelbox.cmd` in the workspace root, or `start.cmd` in this directory. Open **http://127.0.0.1:8765/**. Do not open `web/index.html` directly; its assets and library API require the server.

From PowerShell in the workspace root:

```powershell
& .\work\reel-venv\Scripts\python.exe .\outputs\reelbox\launch.py --open
```

Code is in `<workspace>/app`. `runtime.json` records the Python executable in `work/reel-venv`. Keep these paths in place. The per-user startup shortcut starts the backend at sign-in; `install-startup.ps1` installs it. Remove Reelbox.lnk from `shell:startup` to disable startup.

## Local models

| Role | Default |
| --- | --- |
| First decision, including vision | `d1:latest` |
| Visual understanding, summaries and new topic names when requested | `minicpm-v4.6:latest` |
| Semantic retrieval | `nomic-embed-text` |
| Speech transcription | Faster-Whisper base, on CPU |

Start Ollama and finish downloading the models. D1 uses the native `/v1/systemone` endpoint with text, images and typed questions; it is not a text-generating chat model. MiniCPM uses `/api/chat` with images and locally validated structured output. Use a current Ollama release that supports D1 and its native decision endpoint. Test models in Connection & settings checks D1 first, then MiniCPM with synthetic text.

With these defaults, model inference, the database and dashboard stay local. Instagram metadata and media acquisition still require network access and a valid account session. No cloud decision model, Gemma, or cloud credits are required by the default configuration. Changing model IDs or the Ollama endpoint can change where inference occurs; the displayed model names show the configured values. Session cookies and API tokens are never included in model evidence.

## Connect Instagram

1. Load `app/extension/` as an unpacked extension in your normal Edge, Chrome, or Brave profile. See [extension instructions](../../app/extension/README.md).
2. Open Instagram, your profile, then Saved.
3. Click the extension and choose Connect this Saved page.
4. Use Sync now in the extension for an immediate scan. Sync saves in the dashboard queues a request checked by the extension's next alarm.

The extension checks once per minute while the browser is open and attempts one completed scan per Asia/Calcutta calendar day. Both the local backend and browser must be running. Resetting the database changes its token and requires pairing again.

Scanning begins at the top, reads visual row order, and scrolls downward incrementally. Scan timestamps and ascending Saved positions drive queue and default display order. A duplicate appearing in another collection retains its first position. The next scan refreshes positions of existing records. Semantic search ranks by relevance.

## D1-first data flow

Targeted fresh reruns use the persisted `refresh_analysis` flag independently of `force_video`; previous model cache entries are bypassed for those reels, while video still requires insufficient source context or an explicit request. Old successful results remain until replacements succeed.

Instaloader 4.15.4 replaces yt-dlp for Instagram retrieval. Metadata lookup reads the caption, first caption line as source title, creator and cover URL without resolving or downloading video media. Only an explicit Analyze video or Approve video analysis action resolves and downloads video; model requests wait for approval. Low classification confidence alone goes to review. Existing Instagram cookies stay local to metadata requests; video media requests do not carry session cookies. Video downloads are bounded to 250 MB and 120 seconds, with the existing 10-minute duration limit and temporary-file cleanup.

The initial retrieval trial tested ten failed, ten review, ten ready and ten queued records: all 40 returned metadata and thumbnails, 37 returned MP4 videos and three were non-video posts. Every video was deliberately downloaded for that retrieval trial only; normal processing retains the context gate. The trial did not run inference or change live records. Details: `work/instaloader-sample/REPORT.md` in the workspace.

1. Save and deduplicate links by shortcode. Retain source title separately from generated titles.
2. Acquire title, caption, creator and an app-owned thumbnail. Missing information gets at most ten persisted retrieval rounds with backoff, at most one cover request per round, and refreshed expired URLs. Successful fields are retained.
3. If the thumbnail is still missing, notify the user and hold the reel in Needs review. No text-only vision analysis is silently substituted. Retry missing info starts a new retrieval budget. Analyze video is an explicit way to request deeper evidence and can produce a cover from the video.
4. Retrieve existing topic candidates with local embeddings. D1 receives actual source text, the thumbnail, and candidate boxes before any MiniCPM call.
5. A confident existing-topic match can save a clearly labeled caption/source preview without invoking MiniCPM. This is not a generated summary.
6. When D1 requests explanation, a generated summary, or a name for a new topic, MiniCPM reads the evidence. D1 validates the resulting topic assignment. Existing broad boxes are preferred; a new proposal receives another duplicate/novelty check before insertion. Unresolved evidence goes to Needs review.
7. If video evidence is needed, request user approval first. After approval, temporarily download it, transcribe available speech locally, and extract 4-16 temporal samples. D1 judges up to four uniformly distributed samples and the transcript first. If it requests visual help, MiniCPM describes the extracted samples in batches of at most four images and summarizes the evidence. D1 validates the final category. Counts distinguish frames extracted from frames actually judged or described.
8. Save model IDs, preview/summary kind, source provenance and scores. Clean temporary video, audio and frames on success, stop, hold or failure. Retain the thumbnail, transcript and knowledge record.

Model scores are heuristics, not guarantees. Defaults are acceptance 0.80 and novelty 0.85; evaluate them against representative reels. Captions are source claims, not independently checked facts. Temporal samples can miss brief actions.

## Offline waiting and Stop/Resume

If Ollama is offline or D1 is still downloading, the worker waits without claiming a new batch slot. A model disappearing, loading, timing out or returning a service error during a reel returns that reel to Waiting for model. The rest of the queue stays intact. Retry checks back off from 5 seconds to at most 5 minutes; Retry models now checks sooner. Missing-model, rate-limit and configurable-provider account errors are also wait states, not failures across the entire queue.

Waiting does not increment completed-batch progress. A reel interrupted mid-processing keeps its reserved slot and previous result; the same reel resumes when models return. Successful inference is cached by evidence, model IDs and prompt/schema version to avoid repeating completed calls. Temporary downloads or frame extraction may need to run again after cleanup.

Stop processing stops new jobs and model calls at the next checkpoint, terminates an active FFmpeg child, and preserves queued records. An already-sent model request or a bounded metadata request may finish before the stop takes effect. Its validated inference result can be cached, but the reel's previous analysis remains until a full replacement completes. Stop persists across backend restarts. Resume processing releases that stop; it does not bypass a completed batch's review pause. The dashboard/server remain available while processing is stopped.

## Test batches

The worker starts the next eligible reel immediately after completion. There is no artificial three-second delay between jobs; source retrieval limits, model-outage backoff, approval holds and the selected batch boundary still apply.

For an explicitly authorized full-library rerun, stop processing first and run `work/reel-venv/Scripts/python.exe outputs/reelbox/reprocess.py` from the workspace root. It writes a private database backup and model folder plan under `data/backups/`. Local D1 chooses short subject labels for existing folders from a starter set (Code, UI, AI, Graphics, Simulation, Manhwa, Cool Projects and Useful Projects), using the original descriptions. It merges duplicate folders, requeues every reel with a renewed metadata budget, and starts a fresh unlimited batch. It leaves processing stopped until Resume is selected. Old results remain until replacement succeeds. The full rerun still uses title/caption/thumbnail before any conditional video download. MiniCPM can propose other short names for newly encountered subjects; D1 validates them. MiniCPM structured-output requests disable thinking to leave the response budget available for final JSON.

The default is 50 unique reels per batch, starting at the top. When the batch finishes, processing pauses for verification. Select Continue next 50 to release the next batch. Settings offer 10, 25, 50, 100 or Unlimited; changes apply to the current batch count. Reservations and review pauses survive restarts. True processing failures and thumbnail holds count as finished attempts; model outages and manual stops do not finish a slot. Manual retries reuse a reel's slot in the current batch.

Link discovery can continue while model processing waits or pauses. Undelivered work stays queued and does not require a rescan. Existing incomplete records can receive metadata-only backfill without repeating analysis; those records also reserve batch slots.

## Interface and API

The sidebar contains search, topic boxes, compact reel navigation and analysis filters. The detail panel shows the cover, a labeled source preview or generated summary, tags, assignments and expandable evidence. Open original links to Instagram. Analyze video explicitly requests deeper analysis. Previous results survive unsuccessful reanalysis. Missing-info notices persist until resolved or dismissed.

Copy the local API token from Connection & settings / Agent API. Supply `Authorization: Bearer <token>`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/reels` | Records with evidence, preview kind, processing status and boxes |
| GET | `/api/reels?q=herbs&semantic=1` | Semantic ranking |
| GET | `/api/reels?mode=caption_cover` | Quick records, excluding review items |
| GET | `/api/reels?mode=video_sampled` | Video-analyzed records, excluding review items |
| GET | `/api/reels?status=review` | Needs review and thumbnail holds |
| GET | `/api/reels?status=waiting_model` | Reels interrupted by a model outage |
| GET | `/api/reels?box=1` | Topic filter |
| GET | `/api/reels/<shortcode>` | Full record |
| GET | `/api/boxes` | Topic boxes and counts |
| GET | `/api/health` | Model configuration, Ollama/embedding readiness and counts |
| GET | `/api/processing` | Batch progress, manual stop, model wait and retry time |
| GET | `/api/notifications` | Undismissed missing-info notices |
| GET | `/api/sync-status` | Collector state |
| POST | `/api/ingest` | `{"items":[{"url":"https://www.instagram.com/reel/SHORTCODE/"}]}`; optional title, caption, creator, cover_url, scan_started, saved_position |
| POST | `/api/analyze-video` | `{"id":"SHORTCODE"}` |
| POST | `/api/retry` | `{"id":"SHORTCODE"}` retries a terminal record |
| POST | `/api/retry-info` | `{"id":"SHORTCODE"}` starts another metadata/thumbnail budget |
| POST | `/api/reel-boxes` | `{"id":"SHORTCODE","box_ids":[1,2]}` |
| POST | `/api/boxes` | `{"name":"Gardening","description":"Growing plants"}`; include id to edit |
| POST | `/api/processing` | `{"action":"stop"}`, `{"action":"resume"}`, `{"action":"continue"}`, or `{"action":"configure","batch_size":50}` |
| POST | `/api/notifications/dismiss` | `{"id":1}` |
| POST | `/api/sync` | `{"mode":"force"}` |
| POST | `/api/model-check` | `{}` checks the configured models using synthetic text |

List results default to 500 and are capped at 1000. The UI loads 100 at a time up to 1000; refine a search or topic for larger libraries. Semantic ranking can include weak matches. The API binds only to 127.0.0.1:8765.

## Configuration and verification

Environment variables: `REELBOX_DATA`, `REELBOX_PORT`, `REELBOX_OLLAMA_URL`, `REELBOX_VISION_MODEL`, `REELBOX_DECISION_MODEL`, `REELBOX_EMBED_MODEL`, `REELBOX_ACCEPT_THRESHOLD`, `REELBOX_NOVELTY_THRESHOLD`. The extension targets port 8765; other ports are mainly for isolated testing. Runtime requirements are Windows, Python 3.11, FFmpeg/FFprobe and Ollama; Faster-Whisper downloads its local model once.

From this directory:

```powershell
..\..\work\reel-venv\Scripts\python.exe -m unittest -v test_app test_pipeline test_batches test_controls test_instagram_source
```

From the workspace root:

```powershell
node work/test-extension.mjs
node work/test-collector.mjs
# Disposable synthetic library, with no worker or account:
work/reel-venv/Scripts/python.exe work/serve-qa.py
# In another terminal:
node work/qa-reelbox.mjs http://127.0.0.1:8766
node work/test-batch-ui.mjs
```

Tests use temporary data and synthetic evidence. D1 and MiniCPM passed actual local synthetic-image checks; results are in `work/current-model-check.json` at the workspace root. These checks confirm model input/response integration, not complete real-account categorization. Real Saved coverage still requires an account comparison. Instagram layout changes, sessions and throttling can interrupt scans. A scan reaching its 150-round or 100-page cap is partial, not complete.

Never share `data/`, which contains private session files and cached evidence. API Anything remains packaged for optional legacy `sync.mjs` capture; it is not the current collector or a validated saved-feed API. Captures may contain credentials.

Provider references: [D1](https://ollama.com/library/d1), [MiniCPM](https://ollama.com/library/minicpm-v4.6), [System One](https://docs.ollama.com/api/systemone). See [spec](../spec.md), [decision contract](../../decision.md), [design](../../design.md), and [structure](../project-structure.md).

## Video approval and primary folders

D1 chooses one primary folder from original evidence before judging whether more content is needed. Existing-folder matches use majority support and a margin over alternatives; summary self-confidence is not a classification gate. A model request for video now creates a Video approval needed hold and notification. Click Approve video analysis to allow that individual download, transcription and frame sampling. No model-requested video is downloaded automatically. Stop/Resume, retries, Continue and reruns are not approval. These rules supersede earlier automatic video wording above.

Validation: work/validate-routing-nine.py runs the nine labelled real examples in a disposable library with downloads blocked; results are work/routing-nine-evaluation.json. work/test-video-approval-ui.mjs checks the approval button against the disposable UI fixture.

## Grounded new folders

The generic new-option score no longer blocks folder creation. D1 chooses human-readable names, may discover named starter subjects (including Manhwa, Fitness and Languages), and can compare close alternatives. MiniCPM can still propose other names. Every proposed new folder receives a grounded-subject check, normalized-name lookup and duplicate validation before insertion. Empty starter folders are not created.

The grounded-subject/reuse default is 0.70 (REELBOX_FOLDER_SUPPORT_THRESHOLD); distinct-topic novelty is 0.75 (REELBOX_NOVELTY_THRESHOLD), with a 0.20 lead. These are provisional heuristics, not calibrated accuracy percentages. The visual fallback now supplies extracted cover text, objects and subject with original metadata to D1. Numeric confidence is constrained by an enum; errors distinguish invalid JSON from schema violations. Local model IDs, video permission and batch pauses are preserved.

Run work/reel-venv/Scripts/python.exe work/validate-routing-nine.py --review-ten from the workspace root to evaluate the ten reviewed examples in an isolated library with video downloads blocked. Results are work/review-ten-evaluation.json; this small sample does not establish general accuracy.

## Rolling processing queue

Processing admits one unfinished reel at a time in saved order. Each completed reel frees one place for the next. Ollama inference remains serial to avoid adding concurrent vision requests during cache failures. This window is separate from the verification batch limit (currently 100 for the selected rerun); it never admits reels outside a fully reserved batch. The window rebuilds from database state after restart. Model waits retain their place, and Stop/Resume and per-reel video approval still apply. The processing API reports queue_capacity, queue_window IDs and in_flight separately from unfinished batch reservations (active).

## Current model override: MiniCPM only

The user-selected default is now local minicpm-v4.6:latest for both vision/writing and structured folder/routing judgments through /api/chat. D1 is unloaded and is not used by default. REELBOX_DECISION_MODEL defaults to the vision model; an explicit different override retains the native System One integration. Text embeddings remain nomic-embed-text for retrieval, not content decisions. Chat decision support scores are generated estimates, not native logits or calibrated probabilities; compatibility distributions split residual mass uniformly and are marked score_source=generated_estimate. Existing thresholds remain provisional and need evaluation for this model. This section supersedes earlier D1-first wording. Cached decisions have a new prompt version. Processing remains one reel at a time, with mandatory covers, model backoff, preserved previous results and explicit per-reel video approval. Switching models does not resume stopped work or reprocess completed records.

## Five concurrent reel workers

The current user-selected worker concurrency and rolling admission window are five. Claims are atomic and a completed reel frees a place for the next saved reel. Folder assignment/creation is serialized to protect novelty and duplicate checks. Ollama independently controls inference scheduling; five application workers do not override OLLAMA_NUM_PARALLEL. The remaining queue is run with an unlimited batch budget at the user's request. Existing video approvals remain per reel; newly encountered review items do not gain video permission. This supersedes earlier single-worker queue descriptions.


## Collection browsing redesign (implemented)

The dashboard now opens as a folder and reel-card library. A warm light theme is the default, with a persistent dark theme option. The sidebar provides status filters and every folder; the main collection shows six popular folders (four on phones), expandable to all, plus real thumbnail cards in Saved order. Grid/list choice persists locally. Search supports the existing literal/semantic modes and Ctrl/Cmd+K. Folder selection shows its description.

Opening a reel enters a focused detail page with Back, Previous and Next within the loaded results, explicit evidence labels, the original-link/video actions, and collapsed folder assignment and evidence sections. Returning preserves browse scroll position. Processing controls are collapsed at the bottom of the workspace; notifications remain available through their count button. A mobile navigation drawer replaces the sidebar. Missing covers, empty search results, errors and model waits retain their existing handling. Background refresh avoids rebuilding unchanged card/folder DOM. All data and processing contracts remain unchanged.

Verification used the populated local library read-only: folder expansion, folder filtering, detail and next/back navigation, grid/list views, both themes, literal empty search, settings open/close, 390px/mobile overflow checks and browser error inspection. No ingestion, video analysis, folder edits or sync was triggered during UI verification.


## Automatic matching for user-created folders

Creating or editing a folder saves it immediately and starts a durable background matching job. The name and description define membership. Existing analyzed Ready/Needs review reels are checked in Saved order. Text embeddings shortlist candidates at a provisional cosine floor of 0.35; local MiniCPM confirms clear membership from original title/caption, stored observations/summary and the existing thumbnail, with a provisional generated-support threshold of 0.75. These thresholds are heuristics, not calibrated probabilities. Missing-cover items are skipped; matching never retrieves media or grants video permission.

Memberships are additive: the existing folder assignments, analysis and status are untouched. Confirmed secondary links and explicitly selected manual links are protected during later reanalysis. Users may select multiple checkboxes in Organize in folders. Newly analyzed reels are appended to these user-folder jobs. Editing a description rescans additively; it does not remove previous matches.

Jobs store a generation, Saved-order item list, cursor, added count, error and retry time. They resume after restart and back off on model failures. Stop/Resume also controls matching; a reel verification-batch pause does not prevent the separate folder job. Editing a folder invalidates in-flight decisions for its previous definition. Folder progress is exposed through authenticated /api/boxes and displayed in the selected folder. Processing status separately reports pending folder jobs.

Implementation adds folder_matches and preserved_reel_boxes tables without changing the existing reel_boxes schema. test_folder_matching.py covers additive memberships, idempotence, missing-cover protection, outages/restarts, Stop, stale generations, future arrivals and preservation on reanalysis. UI verification uses the disposable synthetic library, never real ingestion or video downloads.
