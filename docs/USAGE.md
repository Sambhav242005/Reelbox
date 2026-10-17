# Usage and troubleshooting

## Configuration

Set environment variables in the terminal before launching the backend. A `.env` file is not automatically loaded.

| Variable | Default | Purpose |
| --- | --- | --- |
| `REELBOX_DATA` | `app/data` | Private library directory |
| `REELBOX_PORT` | `8765` | Backend port; extension expects 8765 |
| `REELBOX_OLLAMA_URL` | `http://127.0.0.1:11434` | Inference endpoint |
| `REELBOX_VISION_MODEL` | `minicpm-v4.6:latest` | Vision and writing |
| `REELBOX_DECISION_MODEL` | Same as vision model | Structured routing |
| `REELBOX_EMBED_MODEL` | `nomic-embed-text` | Semantic retrieval |

For example, from PowerShell in the repository root:

```powershell
$env:REELBOX_DATA = Join-Path $PWD 'private-library'
.\.venv\Scripts\python.exe app/app.py
```

If you choose a custom data directory, keep it outside your publication files or add it to `.gitignore`. Use the default port for extension pairing. Optional D1 routing uses a different provider contract and needs an Ollama version supporting its native System One endpoint; it is not needed for the standard setup.

## Everyday controls

The processing panel above the library shows queued, active and successfully organized reels. Use the small follow button to keep one reel visible as it moves into its folder. Timing and speed apply to the current measured run; existing records initially show **Not measured**. Review and errors are not successful organization. The panel's Resume/Stop button uses the same durable controls as Queue & controls.

- **Sync now** in the extension starts collection. Dashboard sync requests wait for the extension alarm.
- **Needs review** contains uncertain or incomplete evidence. A missing cover gets at most ten retrieval rounds before a persistent notice and hold.
- **Retry missing info** renews the metadata budget. It does not grant video approval.
- **Stop/Resume** persists across backend restarts. An already submitted model call can finish before Stop takes effect.
- **Continue next 50** releases a verification pause. Resume alone does not bypass it.
- Folder matching is additive. Editing a description rescans; it does not remove earlier matches.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Dashboard does not open | Run `.\.venv\Scripts\python.exe app/app.py` in a terminal to see errors. Inspect `app/data/app.log` when using the launcher. |
| Waiting for model | Start Ollama and finish pulling both configured models; work stays queued with backoff. |
| Cannot connect extension | Start backend on port 8765, use the browser profile signed into Instagram, and connect again. Resetting the database changes the pairing token. |
| Missing covers | Check account/session access and persistent notices; retry missing info after fixing the cause. |
| Video analysis fails | Check FFmpeg/FFprobe on PATH and account access. Video must be approved for the individual reel. |
| New code not reflected in extension | Reload it on the browser's extensions page. |
| Only part of Saved collected | A scan can reach its page/scroll cap or stop on Instagram changes/throttling; partial is not complete coverage. |

For backups, stop the backend and copy the entire private data directory. Keep backups private. Reload the extension after updating its files. Python dependency changes can be installed by repeating the requirements installation command.

## Local API

Connection & settings / Agent API exposes the local bearer token. Authenticated calls use `Authorization: Bearer <token>`. Common endpoints include `GET /api/reels`, `GET /api/boxes`, `GET /api/processing` and `GET /api/health`. Never include a real token in issue reports, screenshots or public snippets.
