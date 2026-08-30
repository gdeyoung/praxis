# Benchmarks

Usage-based measurement scripts. The one rule that matters: **count `usage.completion_tokens` from a non-streamed response (or the final usage frame), never SSE chunk counts** — speculative decoding (MTP) packs multiple tokens per chunk and will silently halve your numbers. See the main [README](../README.md) for the trap in full.

| Script | What it measures |
|---|---|
| `bench_decode.py` | Median decode tok/s across N runs, T=0, usage-based |
| `bench_think.py` | Same with thinking mode forced on |
| `bench_toolargs.py` | Decode rate during tool-call argument generation |
| `bench_prefill.sh` | Cold + warm prefill tok/s on a fixed 8K prompt; reports prefix-cache HIT/MISS |
| `verify_gate.sh` | Full pre-deploy gate: coherence, determinism (same prompt twice → byte-equal), prefix-cache, tool-call round-trip |

Scripts are sanitized versions of the fleet's production instruments. Endpoint and model name are parameters; nothing is hardcoded.
