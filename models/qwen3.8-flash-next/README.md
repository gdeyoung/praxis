# Qwen3.8-Flash-Next on a single DGX Spark

Production serving config for a hybrid-quantized MoE on one Grace-Blackwell GB10, with the verification gates we run before calling any deployment "done."

- **Checkpoint:** [RadixArk/Qwen3.8-Flash-Next-NVFP4](https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4) (community NVFP4 build of [Qwen/Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next))
- **Recipe origin:** [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX) — we credit and link; the additions below are ours
- **vLLM support PR:** [vllm-project/vllm#53896](https://github.com/vllm-project/vllm/pull/53896) (unmerged at time of writing)

## Why hybrid quantization (the one-paragraph version)

Flash-Next is a hybrid MoE: routed experts (~63 GiB) ship NVFP4-quantized in the community checkpoint, but the dense "side" layers — GDN projections, attention QKVO, shared experts (~15 GiB) — remain bf16. Every decoded token reads all of that side-layer weight regardless of which experts fire, so **bf16 side layers set the decode bandwidth floor**. Converting those ~300 tensors to blockwise fp8-e4m3 (128×128 blocks, fp32 scales — the DeepSeek-V3 layout vLLM loads natively) halves the floor.

## Measured results (our hardware, single DGX Spark)

| Metric | NVFP4 (stock) | Hybrid fp8 sides | Δ |
|---|---|---|---|
| Decode, no-think | 28.0 tok/s | **33.3 tok/s** | +19% |
| Decode, thinking-on | 24.9 | **31.9** | +28% |
| Decode, tool-call args | 27.2 | 30.9 | +14% |
| Greedy smoke (incl. TTFT) | 22.5 | 26.8 | +19% |
| KV cache capacity | 582k tok | 608k tok | +4% |

Quality gates passed on both layouts: identical greedy continuation on a fixed prompt, deterministic at T=0, prefix-cache HIT, OpenAI-compatible tool-calling round-trip. Max per-tensor relative error from the fp8 conversion: 3.5%.

## Gotchas we hit (the actual content)

1. **The MTP/SSE benchmark trap.** Speculative decoding (MTP k=2) packs 2–3 tokens into each SSE stream chunk. Any benchmark that counts *events* instead of `usage.completion_tokens` reports ~half the real throughput. We watched a stock bench report "11 tok/s" on a 28 tok/s endpoint. **Always trust `usage` from the non-streamed response, never chunk counts.**
2. **Cold boot is ~14 min, not 8–13.** torch.compile cache is cold for the new fp8 graph shapes. Poll `/health`; don't panic at minute 10.
3. **First big prefill post-boot is unrepresentative** (~900 vs ~1,900 tok/s steady-state). Warm the caches before recording prefill numbers.
4. **Verify the container env, not the docs.** `VLLM_FP8_HYBRID=1` in `docker inspect` is the ground truth that hybrid mode actually loaded.
5. **Streaming tar over SSH for backups: timeouts truncate silently.** A killed `timeout` mid-stream leaves a short file that *looks* complete. Full `tar tzf` decompression pass (gzip CRC on every byte) is the only acceptance test. We caught two truncated copies (137 MB and 4.9 GB) before the verified one landed.

## In this directory

- [`benchmarks/`](benchmarks/) — the measurement scripts and methodology (usage-based counting, T=0 determinism check, prefix-cache probe)
- [`verification/`](verification/) — the pre-deployment gate: coherence, determinism, tool-call, LiteLLM/router round-trip
