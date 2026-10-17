# Recorded organization benchmark

This is the single tech-only run used in the public demo, recorded on 17 October 2026. It is a small warm-model sample, not a general speed or accuracy claim.

| Measurement | Recorded result |
| --- | --- |
| Sample | 50 unique reels; 20 featured |
| Topic selection | 10 each: AI, Technology, Code, UI, Useful Projects |
| Successfully organized | 50 |
| Needs review / errors | 0 / 0 |
| Wall time | 11.96 seconds |
| Successful throughput | 250.9 reels/minute |
| Median first-claim-to-success latency | 1.03 seconds |
| Workers | 5 |
| Warm-up | 2 separate examples, excluded |
| Original library fingerprint unchanged | Yes |

The run used cached source titles, captions and readable covers with fresh local inference. It excluded Instagram retrieval, media downloads, video analysis and cold model loading. Source text and existing folder memberships excluded manga, manhwa, anime and gaming. Frame samples were not needed or taken.

Hardware: Intel Core i7-14700K and NVIDIA GeForce RTX 4070 Ti; the machine also reports Intel UHD Graphics 770. This does not independently establish which processor handled each inference operation.

**Model identity matters:** the configured vision/decision alias was `minicpm-v4.6:latest`, but Ollama reported `qwen35`, **752.16M parameters, Q4_K_M**. These numbers must not be attributed to the standard MiniCPM model. The retrieval model was `nomic-embed-text`.

A successful result means a saved analysis with at least one folder assignment. Folder correctness was not manually scored. Throughput is successful results divided by elapsed wall time; median latency is calculated across successful unique reels and includes retries/waits. Inference caching started empty; cache entries created during this run remain private. The original library was opened read-only and its records, folder assignments and settings were checked against its preparation fingerprint.

Full aggregate metadata: [benchmark.json](media/benchmark.json). Reproduction and telemetry definitions: [DEMO.md](DEMO.md). Raw recordings, private sample IDs and source fingerprints are intentionally excluded from Git.
