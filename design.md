# Reelbox interface design

Status: implemented as a dark sidebar/detail workspace, with populated desktop and 390 px mobile checks. Screenshots use synthetic fixture content.

## Direction

Use a dark workspace with quiet borders, readable typography, and a restrained accent. The owner's reference is https://webdevcody.github.io/jev-demos/#d2101186531289358711. This brief defines the requested adaptation; it does not claim a fresh visual inspection of that page.

## Desktop layout

The left sidebar contains search, analysis filters, topic boxes with counts, and a compact reel list. Keep search accessible while moving between reels. List rows show a small cover, title, and evidence badge; selection is visually distinct and keyboard accessible.

The main panel displays the selected cover, title, creator/source, a 2ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ3-line summary, tags, assigned boxes, and evidence basis. Put Open original and Analyze video in a separate action row with clear spacing. Additional detail can expand to show key ideas, transcription, sampled-frame evidence, and uncertainties. Selecting another reel updates the panel without opening a modal.

## Filters and evidence

- Quickly understood: successful caption/cover analysis. Show Based on caption and cover, or a more precise caption-only label when no cover was available.
- Video analyzed: completed deeper analysis. Show sampled-frame count and whether speech was transcribed.
- Needs review: unresolved evidence or category assignment, with a concrete explanation.
- Processing failures: a visible recoverable state with Retry and the failure reason. Preserve the last successful analysis when reanalysis fails.

Do not present model confidence as a guarantee. Empty, loading, offline, processing, no-results, and failure states need explicit copy. Display local D1 and MiniCPM model names in connection settings. Disclose remote inference only when explicitly configured.

Show missing-info retrieval progress as attempt N/10. Exhausted attempts create persistent notifications with the reel title, missing fields, View reel, and Dismiss notification. A sidebar notification button keeps these discoverable on mobile. The selected reel offers Retry missing info; it refreshes metadata and thumbnails without discarding or regenerating the existing analysis. Default list order follows Saved from the top; keyword/semantic search can still return its own match order.

## Interaction and accessibility

Display a Test batch panel with completed/limit progress and queued count. At the limit, show Paused for your verification and Continue next N. Connection settings contain a labeled limit selector and Apply limit. Keep processing paused until explicit continuation; a page refresh must never resume it. Distinguish queued work from actively processing work in status text.

Preserve the selected reel and active filters during refresh. Debounce search or use explicit submission; stale responses must not replace newer results. Disable duplicate Analyze video requests while work is running. Explain queued and completed states in an accessible status message.

At narrow widths, switch between the reel list and selected detail view with a clear Back to library action. Keep topic filters and search reachable. Avoid horizontal page overflow at 390 px. Provide visible focus, semantic controls, sufficient contrast, descriptive accessible names, and reduced-motion support. Full summaries must remain available when preview text is shortened.

## Review checklist

Check desktop and mobile with populated data, long titles, missing covers, many boxes, no search results, quick and deeper results, model errors, and keyboard-only navigation. Empty-library screenshots alone do not validate the detail workflow.

## Model waits and stopping

The Processing panel is visible even in unlimited mode. It shows Stop processing, persisted stopped state, Resume processing, and Waiting for model with the missing model and reason. Retry models now resets the backoff. Review continuation remains a separate button and must not be implied by Resume. Queued and waiting work are not described as actively processing.

Source-only previews are labeled Caption preview, Transcript preview or Source title preview. Do not present them as generated summaries; show the visual fallback as unused. The default model labels are `d1:latest` and `minicpm-v4.6:latest`. Missing thumbnails hold the reel after ten attempts, with no silent text-only vision request.

## Video approval

When more video context is needed, show Video approval needed, the reason, and an Approve video analysis button. Keep a persistent notification and preserve previous knowledge. One explicit button click authorizes that reel only. Automatic categories show one primary folder; manual assignment remains available.

## Current model override: MiniCPM only

The user-selected default is now local minicpm-v4.6:latest for both vision/writing and structured folder/routing judgments through /api/chat. D1 is unloaded and is not used by default. REELBOX_DECISION_MODEL defaults to the vision model; an explicit different override retains the native System One integration. Text embeddings remain nomic-embed-text for retrieval, not content decisions. Chat decision support scores are generated estimates, not native logits or calibrated probabilities; compatibility distributions split residual mass uniformly and are marked score_source=generated_estimate. Existing thresholds remain provisional and need evaluation for this model. This section supersedes earlier D1-first wording. Cached decisions have a new prompt version. Processing remains one reel at a time, with mandatory covers, model backoff, preserved previous results and explicit per-reel video approval. Switching models does not resume stopped work or reprocess completed records.


## Collection browsing redesign (implemented)

The dashboard now opens as a folder and reel-card library. A warm light theme is the default, with a persistent dark theme option. The sidebar provides status filters and every folder; the main collection shows six popular folders (four on phones), expandable to all, plus real thumbnail cards in Saved order. Grid/list choice persists locally. Search supports the existing literal/semantic modes and Ctrl/Cmd+K. Folder selection shows its description.

Opening a reel enters a focused detail page with Back, Previous and Next within the loaded results, explicit evidence labels, the original-link/video actions, and collapsed folder assignment and evidence sections. Returning preserves browse scroll position. Processing controls are collapsed at the bottom of the workspace; notifications remain available through their count button. A mobile navigation drawer replaces the sidebar. Missing covers, empty search results, errors and model waits retain their existing handling. Background refresh avoids rebuilding unchanged card/folder DOM. All data and processing contracts remain unchanged.

Verification used the populated local library read-only: folder expansion, folder filtering, detail and next/back navigation, grid/list views, both themes, literal empty search, settings open/close, 390px/mobile overflow checks and browser error inspection. No ingestion, video analysis, folder edits or sync was triggered during UI verification.


## Automatic matching for user-created folders

Creating or editing a folder saves it immediately and starts a durable background matching job. The name and description define membership. Existing analyzed Ready/Needs review reels are checked in Saved order. Text embeddings shortlist candidates at a provisional cosine floor of 0.35; local MiniCPM confirms clear membership from original title/caption, stored observations/summary and the existing thumbnail, with a provisional generated-support threshold of 0.75. These thresholds are heuristics, not calibrated probabilities. Missing-cover items are skipped; matching never retrieves media or grants video permission.

Memberships are additive: the existing folder assignments, analysis and status are untouched. Confirmed secondary links and explicitly selected manual links are protected during later reanalysis. Users may select multiple checkboxes in Organize in folders. Newly analyzed reels are appended to these user-folder jobs. Editing a description rescans additively; it does not remove previous matches.

Jobs store a generation, Saved-order item list, cursor, added count, error and retry time. They resume after restart and back off on model failures. Stop/Resume also controls matching; a reel verification-batch pause does not prevent the separate folder job. Editing a folder invalidates in-flight decisions for its previous definition. Folder progress is exposed through authenticated /api/boxes and displayed in the selected folder. Processing status separately reports pending folder jobs.

Implementation adds folder_matches and preserved_reel_boxes tables without changing the existing reel_boxes schema. test_folder_matching.py covers additive memberships, idempotence, missing-cover protection, outages/restarts, Stop, stale generations, future arrivals and preservation on reanalysis. UI verification uses the disposable synthetic library, never real ingestion or video downloads.
