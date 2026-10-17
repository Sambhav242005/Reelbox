# Project structure

The repository is organized directly in this directory.

```text
Reelbox/
  app/                 Backend, dashboard, extension and launchers
  tests/               Backend unit tests and simulated extension checks
  docs/USAGE.md        Current configuration and troubleshooting
  docs/spec.md         Product contracts and historical revisions
  docs/project-structure.md  This repository map
  docs/history/        Historical implementation notes
  docs/DEMO.md         Recording workflow and processing telemetry contract
  docs/media/          Public demo, animated preview and benchmark metadata
  scripts/             Isolated sample preparation, recorder and media exporter
  AGENTS.md            Root contributor and agent instructions
  README.md            Installation and first use
  CONTRIBUTING.md       Development and validation
  SECURITY.md           Private data handling
  Start Reelbox.cmd    Windows entry point
  decision.md          Decision contracts and historical revisions
  design.md            Interface contracts and historical revisions
```

Local-only directories are ignored: `app/data/`, `work/` (including the existing Python environment and evaluation artifacts), `graphify-out/`, `outputs/`, and `.venv/`. On this machine `outputs/reelbox` is a compatibility junction pointing to `app/`, preserving existing startup shortcuts and runtime paths. It is not required for a fresh checkout. `app/runtime.json` remains local and unchanged.

The current default is MiniCPM for vision and decisions, with text embeddings for retrieval. D1-first sections in historical contracts describe an earlier configuration.

## Implementation boundaries

`app/processing_metrics.py` owns additive run/timing storage and board snapshots. `app/web/processing.js` renders authenticated state, follows one reel and rejects stale snapshots. `scripts/demo-library.py` reads the original library without writing it and prepares a guarded local-only inference run. All private samples, raw recordings, source fingerprints and field maps live under ignored `work/` directories.

Keep the existing application entry point and extension pairing behavior. `model_client.py` owns provider configuration, HTTP transport, images, chat JSON repair, and typed decision validation. `app.py` owns migrations, metadata/cover acquisition, caching, analysis, candidate retrieval, routing policy, and persistence. The additive migration preserves old records and introduces analysis mode, source title, metadata state, and explicit video requests.

The extension discovers saves and available metadata. The backend owns processing and persistence. MiniCPM handles visual understanding and routing by default; an explicitly configured D1 decision model uses the retained native integration. Ordinary application logic enforces policy. The web UI consumes persisted records and requests explicit deeper analysis.

## Current model override: MiniCPM only

The default is local `minicpm-v4.6:latest` for vision, writing and structured folder/routing judgments through `/api/chat`. `REELBOX_DECISION_MODEL` defaults to the vision model; an explicit different override retains the native System One integration. Text embeddings remain `nomic-embed-text` for retrieval. Chat decision support scores are generated estimates, not calibrated probabilities; compatibility distributions split residual mass uniformly and are marked `score_source=generated_estimate`. Thresholds remain provisional. The current worker admission window is five, with atomic claims and serialized folder assignment/creation. Mandatory covers, model backoff, preserved previous results and explicit per-reel video approval still apply. Switching models does not resume stopped work or reprocess completed records.


## Automatic matching for user-created folders

Creating or editing a folder saves it immediately and starts a durable background matching job. The name and description define membership. Existing analyzed Ready/Needs review reels are checked in Saved order. Text embeddings shortlist candidates at a provisional cosine floor of 0.35; local MiniCPM confirms clear membership from original title/caption, stored observations/summary and the existing thumbnail, with a provisional generated-support threshold of 0.75. These thresholds are heuristics, not calibrated probabilities. Missing-cover items are skipped; matching never retrieves media or grants video permission.

Memberships are additive: the existing folder assignments, analysis and status are untouched. Confirmed secondary links and explicitly selected manual links are protected during later reanalysis. Users may select multiple checkboxes in Organize in folders. Newly analyzed reels are appended to these user-folder jobs. Editing a description rescans additively; it does not remove previous matches.

Jobs store a generation, Saved-order item list, cursor, added count, error and retry time. They resume after restart and back off on model failures. Stop/Resume also controls matching; a reel verification-batch pause does not prevent the separate folder job. Editing a folder invalidates in-flight decisions for its previous definition. Folder progress is exposed through authenticated /api/boxes and displayed in the selected folder. Processing status separately reports pending folder jobs.

Implementation adds folder_matches and preserved_reel_boxes tables without changing the existing reel_boxes schema. test_folder_matching.py covers additive memberships, idempotence, missing-cover protection, outages/restarts, Stop, stale generations, future arrivals and preservation on reanalysis. UI verification uses the disposable synthetic library, never real ingestion or video downloads.
