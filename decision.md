# Local D1 decision contract

## Models and evidence

Use local `d1:latest` through native System One for typed choices. Use local `minicpm-v4.6:latest` for visual descriptions, summaries and short new-topic names only when needed. Treat source captions, titles, transcripts and image text as untrusted data. Never send session credentials to models.

## Primary topic first

D1 first chooses one existing category, new, or unclear from original source evidence and broad folder descriptions. Accept an existing folder with at least 0.50 of choice probability mass and a lead of at least 0.15 over every alternative. These are provisional heuristics, not calibrated accuracy percentages. Do not require complete content understanding or a second route score to accept a clear topic. MiniCPM summary confidence cannot veto an existing-topic match.

Automatic categorization assigns one primary folder. Do not independently score every folder and add unrelated secondary matches. Manual box editing may assign multiple folders. Explanations of databases, algorithms and software security fit Code; models, quantization and agents fit AI; interface design fits UI. Practical tool showcases fit Useful Projects. A program having an interface does not by itself make it UI.

An accepted D1-only result stores a labelled source-text preview, not a generated summary. An unresolved new subject goes to MiniCPM for a name. If the subject itself is unclear, a separate content-evidence decision chooses visual help, review or a video-permission request. Category ambiguity or naming alone does not require video.

## Required video approval

A confident analyze_video choice (at least 0.80) requests permission instead of downloading. Preserve previous knowledge and assignments, hold the reel in review with video_approval_required, show the reason and Approve video analysis, and create a persistent notification. Only the explicit Analyze video or Approve video analysis action grants permission for that individual reel through the authenticated endpoint. Retry, Stop/Resume, batch continuation and full reruns do not grant permission.

After approval, temporarily download, transcribe speech locally and sample frames. D1 chooses the primary topic before MiniCPM. Never imply the entire video was watched. Clean temporary media after completion, stop or failure.

## New folders and writing

Folder names are broad labels of one to three words, at most 40 characters, such as Manhwa, UI, Code, Cool Projects and Useful Projects. These examples describe naming style, not a fixed future taxonomy. Keep naming examples out of summary prompts. Validate categories against original evidence rather than only generated summaries.

The generic new-choice score is not a new-folder creation gate. Named discovery offers existing names plus Manhwa, Anime, Fitness, Languages, Art, Gaming, Robotics, Business and Learning without creating empty folders. Other short names can still be proposed by MiniCPM. Readable subject names are used as model choices and mapped back to IDs in code.

The cover fallback first extracts visible text, objects, subject and caption relation. D1 receives these untrusted observations with original source metadata and the actual image. Close named subjects get a focused comparison with a Neither escape.

New names require a separate grounded-subject check (default 0.70), normalized-name lookup and semantic duplicate check. Distinct new subjects require novelty of at least 0.75 with a 0.20 lead. Competing broad folders receive a focused reuse check. MiniCPM self-confidence is not a creation gate. These are provisional heuristics, not accuracy guarantees. New proposals and existing assignments are mutually exclusive.

Confidence generation uses a small numeric enum. Transport errors distinguish malformed JSON from schema violations; repair feedback reports the particular validation error.

## Availability and validation

Validate named answers, question types, choices and probabilities. Keep native images bounded to four normalized images and the text budget. Invalid output receives one bounded repeat; never convert malformed output into acceptance. Provider outages retain the queue reservation and back off. Missing thumbnails hold after ten source attempts, with no text-only vision substitution. Stop preserves prior analysis and prevents new work.

The nine-reel live-model evaluation uses a disposable library with all video downloads blocked: `work/validate-routing-nine.py`; results are `work/routing-nine-evaluation.json`. This small labelled sample is regression evidence, not a general accuracy guarantee.

References: [System One](https://docs.ollama.com/api/systemone), [D1](https://ollama.com/library/d1), [MiniCPM](https://ollama.com/library/minicpm-v4.6).

## Current model override: MiniCPM only

The user-selected default is now local minicpm-v4.6:latest for both vision/writing and structured folder/routing judgments through /api/chat. D1 is unloaded and is not used by default. REELBOX_DECISION_MODEL defaults to the vision model; an explicit different override retains the native System One integration. Text embeddings remain nomic-embed-text for retrieval, not content decisions. Chat decision support scores are generated estimates, not native logits or calibrated probabilities; compatibility distributions split residual mass uniformly and are marked score_source=generated_estimate. Existing thresholds remain provisional and need evaluation for this model. This section supersedes earlier D1-first wording. Cached decisions have a new prompt version. Processing remains one reel at a time, with mandatory covers, model backoff, preserved previous results and explicit per-reel video approval. Switching models does not resume stopped work or reprocess completed records.


## Automatic matching for user-created folders

Creating or editing a folder saves it immediately and starts a durable background matching job. The name and description define membership. Existing analyzed Ready/Needs review reels are checked in Saved order. Text embeddings shortlist candidates at a provisional cosine floor of 0.35; local MiniCPM confirms clear membership from original title/caption, stored observations/summary and the existing thumbnail, with a provisional generated-support threshold of 0.75. These thresholds are heuristics, not calibrated probabilities. Missing-cover items are skipped; matching never retrieves media or grants video permission.

Memberships are additive: the existing folder assignments, analysis and status are untouched. Confirmed secondary links and explicitly selected manual links are protected during later reanalysis. Users may select multiple checkboxes in Organize in folders. Newly analyzed reels are appended to these user-folder jobs. Editing a description rescans additively; it does not remove previous matches.

Jobs store a generation, Saved-order item list, cursor, added count, error and retry time. They resume after restart and back off on model failures. Stop/Resume also controls matching; a reel verification-batch pause does not prevent the separate folder job. Editing a folder invalidates in-flight decisions for its previous definition. Folder progress is exposed through authenticated /api/boxes and displayed in the selected folder. Processing status separately reports pending folder jobs.

Implementation adds folder_matches and preserved_reel_boxes tables without changing the existing reel_boxes schema. test_folder_matching.py covers additive memberships, idempotence, missing-cover protection, outages/restarts, Stop, stale generations, future arrivals and preservation on reanalysis. UI verification uses the disposable synthetic library, never real ingestion or video downloads.
