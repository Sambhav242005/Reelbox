# Recorded organization benchmark

MiniCPM-V 4.6 organized this 50-reel technology sample on 17 October 2026. The model was already loaded. These are the timings from the run shown in the demo.

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

The run used saved titles, captions and covers with fresh local inference. Instagram retrieval, downloads, video analysis and model loading were outside the measurement. The sample excludes manga, manhwa, anime and gaming. No video frames were sampled.

Hardware: Intel Core i7-14700K and NVIDIA GeForce RTX 4070 Ti; the machine also reports Intel UHD Graphics 770. This does not independently establish which processor handled each inference operation.

The vision and decision model was MiniCPM-V 4.6, loaded as `minicpm-v4.6:latest` with Q4_K_M quantization. [OpenBMB's model card](https://huggingface.co/openbmb/MiniCPM-V-4.6) describes its Qwen3.5-0.8B language backbone and SigLIP2-400M vision encoder. Ollama's `qwen35` family and 752.16M parameter count describe the language component, not the full multimodal model. Retrieval used `nomic-embed-text`.

A reel counts as organized when it has a saved analysis and at least one folder assignment. The assignments have not been manually scored. Throughput is the number of organized reels divided by elapsed wall time. Median latency covers successful unique reels, including any retries or waits.

The inference cache started empty. The source library was opened read-only, and a fingerprint check confirmed that its records, folder assignments and settings stayed unchanged. Cache entries from the run remain private. Results will vary with hardware, model settings and the reels being processed.

Full aggregate metadata: [benchmark.json](media/benchmark.json). Reproduction and telemetry definitions: [DEMO.md](DEMO.md). Raw recordings, private sample IDs and source fingerprints are intentionally excluded from Git.
