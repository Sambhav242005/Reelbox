# Reelbox product specification

Status: D1-first local-model implementation, 2026-10-16. Automated checks use temporary libraries and simulated model responses. D1 and MiniCPM passed live synthetic-image checks; real-account behavior remains a separate verification.

## Goal

Turn saved Instagram reels into a searchable local library with thumbnails, short descriptions and broad topic boxes. Begin at the top of Saved and avoid video downloads or generative inference when source evidence and a decision suffice.

## Models

| Role | Model |
| --- | --- |
| First decision with vision | `d1:latest`, local, native System One |
| Visual fallback, writing and topic-name proposals | `minicpm-v4.6:latest`, local chat |
| Semantic retrieval | `nomic-embed-text`, local |
| Speech transcription | Faster-Whisper base, local CPU |

D1 makes choices and scores evidence; it does not generate descriptions or category names. MiniCPM generates grounded summaries or names when requested. Default inference stays local. User-configured remote endpoints or cloud model overrides must be disclosed; session credentials are never model input.

## Processing flow

Instagram retrieval uses Instaloader 4.15.4. Metadata acquisition never resolves or downloads video media. Video retrieval requires explicit user approval for that reel. A context-insufficient model decision requests approval and never downloads by itself. Low classification confidence or a new category alone is insufficient to trigger video; use visual help or review instead. The 40-record retrieval trial is documented in `work/instaloader-sample/REPORT.md`; it does not validate inference quality.

1. Collect available source title, caption, creator and cover URL from Saved. Fetch missing metadata without downloading video when possible. Deduplicate by shortcode and store original source title separately from generated title.
2. Retrieve missing source information with one persisted budget of ten rounds. Keep successful fields, refresh expired image URLs and make at most one cover request per round. Stop early when complete; otherwise notify the user with the still-missing fields. A manual metadata retry starts another budget without discarding previous analysis.
3. A thumbnail is mandatory for automatic vision routing. After the retrieval budget is exhausted without one, hold the reel in Needs review and send no text-only vision request. Explicit Analyze video may acquire a cover from decoded video frames.
4. Local embeddings retrieve candidate box descriptions and representative reels. D1 receives actual source text and the cover first, before any MiniCPM call. It chooses one primary topic independently of content completeness; unresolved subjects receive a separate evidence-route choice.
5. A confident existing-topic match can save the category with a clearly labeled caption/source preview. Do not describe a source preview as a generated summary or claim MiniCPM was used.
6. When explanation, a generated summary or a new topic name is needed, invoke MiniCPM. D1 validates the result; new boxes receive normalized-name and semantic duplicate checks plus a novelty decision. Ambiguous evidence stays in Needs review.
7. After the user explicitly approves video analysis for that reel, download temporarily, transcribe available speech locally and extract 4-16 samples spread across the duration. D1 judges up to four distributed samples and transcript evidence first. If it requests help, MiniCPM describes the extracted samples in image batches of at most four, writes a concise summary and receives a final D1 categorization check. Never loop back into another automatic video download from the deeper stage.
8. Persist source provenance, summary kind, actual model IDs, decision scores and evaluated frame count. Distinguish extracted frames from frames actually judged or described. Delete temporary video, audio and frames after success, failure or stop; keep the thumbnail and knowledge record.

## Queue, models and stop controls

The persistent queue processes one reel at a time in Saved order. A scan begins at the top, scrolls incrementally and supplies a timestamp plus ascending positions. Repeated appearances retain their first position within a scan.

The default batch contains 50 unique reels. Stop after completion for user verification; only Continue next N releases a fresh batch. Offer 10, 25, 50, 100 and Unlimited. Reservations survive restarts and interrupted jobs reuse their slot. True record failures and thumbnail holds finish a slot; model waits and manual stops do not finish it.

Before claiming model work, check Ollama and required local models. Offline service or an incomplete download leaves jobs queued without a new reservation. Mid-job model unavailability, timeouts and temporary service failures set Waiting for model and retain the same slot. Retry with backoff from 5 seconds to 5 minutes; allow Retry models now. Never drain the queue into failed records because a shared model is unavailable. Metadata-only backfill need not depend on model readiness.

Stop processing is persisted. It prevents new jobs/model calls, checks between stages and terminates an active FFmpeg child. An in-flight model or bounded network request may finish first. Cache validated results but preserve previous analysis until replacement succeeds. Resume restores processing; it does not bypass a completed-batch review pause. The dashboard remains available while stopped.

## Records and caching

A per-reel refresh_analysis flag requests fresh inference independently of force_video. It bypasses prior inference cache for that job, survives model waits/stops, and clears after completion. This supports targeted reruns without downloading video unnecessarily or clearing unrelated caches.

An explicitly requested full rerun creates a private SQLite backup, asks local D1 to choose short subject labels for existing folders from a starter set matching the user's naming style, merges duplicate names while preserving assignments, starts a new unlimited batch and resets all reels to metadata-first queued work in Saved order. MiniCPM can propose other short names for newly encountered subjects. Retain old analyses, assignments and thumbnails until successful replacements. Reset the metadata retry budget and clear forced-video flags; a rerun never means downloading every video. The prompt version changes with naming policy so prior inference does not bypass the new policy. Normal runs retain the default 50-reel review pause.

Retain source URL, shortcode, metadata, thumbnail, preview/summary, kind, tags, boxes, uncertainty, evidence mode, model IDs and timestamps. Processing status is separate from evidence mode. Cache inference and embeddings by actual inputs, model IDs and prompt/schema version. Explicit video reanalysis can bypass inference cache. Previously successful analysis and assignments survive failed or interrupted reanalysis.

Existing records migrate without forced model reanalysis. Old sampled-video analyses retain their evidence mode. Legacy provider-outage failures can return to Waiting for model without deleting their previous result. Old incomplete records can receive metadata-only backfill.

## Interface and acceptance

Use the dark sidebar/detail layout in design.md. Expose search, topic boxes, compact reel list, quick/video/review/error views, persistent missing-information notifications, batch progress, Stop, Resume and model-wait state. Detail shows the cover, concise preview or summary, tags, source link, explicit Analyze video and expandable evidence. On mobile provide Back to library without horizontal overflow.

Validate quick D1-only acceptance, MiniCPM fallback after D1, video escalation, missing-thumbnail holds, model download/offline waits, backoff, interrupted work, Stop/Resume persistence, fifty-reel boundaries, category novelty, migrations, caching and temporary cleanup. Real Instagram coverage still requires an account comparison; synthetic tests cannot prove complete collection. Confidence thresholds are conservative initial heuristics, not calibrated accuracy guarantees.

## Primary-topic routing and video consent

The main topic is chosen separately from content completeness, using source title/caption/cover and broad folder descriptions. Automatic routing assigns one primary folder with majority support (at least 0.50) and a 0.15 lead over alternatives. Summary self-confidence cannot reject a clear known topic. Ambiguous competitors remain in review. New-topic creation retains conservative evidence and novelty checks.

A model request for video is held in Needs review with a reason, a video_approval_required marker and a persistent notification. Never download automatically, even after a full rerun or Continue. The user must explicitly select Analyze video or Approve video analysis for that reel. Existing results and assignments remain available during the approval wait.

## Grounded new-folder creation and visual fallback

A missing folder is not an unclear subject. Remove the generic new-score gate; offer named broad starter subjects without inserting empty folders, allow other MiniCPM proposals, and validate every new subject against original source and images. Grounding/reuse defaults to 0.70 and distinct-topic novelty to 0.75 with a 0.20 lead, plus name and duplicate checks. These provisional defaults supersede earlier 0.80/0.85 new-folder gates. Labels in model choices are human readable and mapped back to IDs. Close alternatives receive a focused comparison with an abstention option.

The cover fallback extracts text, objects, subject and caption relation before writing a summary. D1 validates observations alongside original source and actual images. Model-written summary confidence does not block grounded folder creation. Numeric confidence uses an enum; malformed JSON and schema errors have separate diagnostic messages. Video consent and the selected batch pause remain unchanged.

## Rolling processing queue

Processing admits one unfinished reel at a time in saved order. Each completed reel frees one place for the next. Ollama inference remains serial to avoid adding concurrent vision requests during cache failures. This window is separate from the verification batch limit (currently 100 for the selected rerun); it never admits reels outside a fully reserved batch. The window rebuilds from database state after restart. Model waits retain their place, and Stop/Resume and per-reel video approval still apply. The processing API reports queue_capacity, queue_window IDs and in_flight separately from unfinished batch reservations (active).

## Current model override: MiniCPM only

The user-selected default is now local minicpm-v4.6:latest for both vision/writing and structured folder/routing judgments through /api/chat. D1 is unloaded and is not used by default. REELBOX_DECISION_MODEL defaults to the vision model; an explicit different override retains the native System One integration. Text embeddings remain nomic-embed-text for retrieval, not content decisions. Chat decision support scores are generated estimates, not native logits or calibrated probabilities; compatibility distributions split residual mass uniformly and are marked score_source=generated_estimate. Existing thresholds remain provisional and need evaluation for this model. This section supersedes earlier D1-first wording. Cached decisions have a new prompt version. Processing remains one reel at a time, with mandatory covers, model backoff, preserved previous results and explicit per-reel video approval. Switching models does not resume stopped work or reprocess completed records.

## Five concurrent reel workers

The current user-selected worker concurrency and rolling admission window are five. Claims are atomic and a completed reel frees a place for the next saved reel. Folder assignment/creation is serialized to protect novelty and duplicate checks. Ollama independently controls inference scheduling; five application workers do not override OLLAMA_NUM_PARALLEL. The remaining queue is run with an unlimited batch budget at the user's request. Existing video approvals remain per reel; newly encountered review items do not gain video permission. This supersedes earlier single-worker queue descriptions.


## Automatic matching for user-created folders

Creating or editing a folder saves it immediately and starts a durable background matching job. The name and description define membership. Existing analyzed Ready/Needs review reels are checked in Saved order. Text embeddings shortlist candidates at a provisional cosine floor of 0.35; local MiniCPM confirms clear membership from original title/caption, stored observations/summary and the existing thumbnail, with a provisional generated-support threshold of 0.75. These thresholds are heuristics, not calibrated probabilities. Missing-cover items are skipped; matching never retrieves media or grants video permission.

Memberships are additive: the existing folder assignments, analysis and status are untouched. Confirmed secondary links and explicitly selected manual links are protected during later reanalysis. Users may select multiple checkboxes in Organize in folders. Newly analyzed reels are appended to these user-folder jobs. Editing a description rescans additively; it does not remove previous matches.

Jobs store a generation, Saved-order item list, cursor, added count, error and retry time. They resume after restart and back off on model failures. Stop/Resume also controls matching; a reel verification-batch pause does not prevent the separate folder job. Editing a folder invalidates in-flight decisions for its previous definition. Folder progress is exposed through authenticated /api/boxes and displayed in the selected folder. Processing status separately reports pending folder jobs.

Implementation adds folder_matches and preserved_reel_boxes tables without changing the existing reel_boxes schema. test_folder_matching.py covers additive memberships, idempotence, missing-cover protection, outages/restarts, Stop, stale generations, future arrivals and preservation on reanalysis. UI verification uses the disposable synthetic library, never real ingestion or video downloads.
