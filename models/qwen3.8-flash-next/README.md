# Qwen3.8-Flash-Next on a single DGX Spark

Production serving config for a hybrid-quantized MoE on one Grace-Blackwell GB10, with the verification gates we run before calling any deployment "done."

- **Checkpoint:** [RadixArk/Qwen3.8-Flash-Next-NVFP4](https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4) (community NVFP4 build of [Qwen/Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next))
- **Recipe origin:** [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX) (hybrid fp8) and [tonyd2wild/Qwen3.8-Flash-Next-NVFP4-DGX-Spark](https://github.com/tonyd2wild/Qwen3.8-Flash-Next-NVFP4-DGX-Spark) (reduced-vocab MTP draft) — we credit and link; the stacking, measurements, and ops notes below are ours
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
6. **"Secret codeword" prompts poison multi-turn cache tests.** The model's safety tuning refuses to retain "secrets," so turn-3 recall "fails" even when the prefix cache is perfect. Both nodes failed identically → it was the prompt, not the serve. Use neutral phrasing ("note this identifier") for cache-correctness needles.
7. **The stock top-k kernel is non-deterministic on ties.** vLLM issues [#51782](https://github.com/vllm-project/vllm/issues/51782)/[#55122](https://github.com/vllm-project/vllm/pull/55122) (open upstream): the persistent top-k can return different candidate sets run-to-run at T=0 on tie-heavy rows — confirmed on our hardware with a per-call counter (483/498/450 across identical reps) while the text output stayed identical 8/8. A torch.topk exact-path overlay (`VLLM_QSA_EXACT_TOPK=1`) removes it at effectively zero cost (±0.5%, noise); we also validated jschmied's standalone deterministic kernel (210/210 adversarial cases incl. exact-reference parity on ties) and keep it parked — the overlay wins on cost.

## Production lane, promoted 2026-09-15 (both our Spark nodes)

Stacked and measured independently on a second Spark, then promoted after a 24h canary (0 restarts, 0 errors, 90% prefix-cache hit rate, T=0 outputs stable):

| Addition | Source | Measured vs prior lane |
|---|---|---|
| Reduced-vocab MTP draft (65,536-token draft vocab, ~1/4 of full) | tonyd2wild-class recipe | +17% mean decode (reverse A/B: 34.0/32.6/35.3 vs 29.0/29.2/28.8 tok/s @ 8k/32k/84k ctx) |
| Hybrid fp8 side-layers (blazux converter, blockwise e4m3) | blazux | +12.6% mean decode, KV capacity +21.6% (1.20M tokens) |
| Exact top-k overlay (T=0 determinism) | ours, from blazux's patch | ±0.5% (free) |

Cumulative from stock NVFP4: **+33% decode at agent context depths** (75k-token median), capacity +21.6%, determinism gained. Prefill:decode is 203:1 in our traffic, so decode gains dominate. Acceptance dips ~12% relative under hybrid (0.76/0.57/0.42 vs 0.81/0.66/0.51) — priced in, net-positive. Env knobs that define the lane: `QWEN4EXP_DRAFT_VOCAB=65536`, `VLLM_FP8_HYBRID=1`, `VLLM_QSA_EXACT_TOPK=1`.

## Provenance — where each piece of our recipe comes from

| Component | Origin | License | What we did |
|---|---|---|---|
| Base checkpoint | [RadixArk/Qwen3.8-Flash-Next-NVFP4](https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4) (community build of [Qwen/Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)) | Qwen base-model terms ("license: other") | Ran as-is (rollback baseline kept) |
| vLLM engine support (qwen4_exp arch) | [vllm-project/vllm#53896](https://github.com/vllm-project/vllm/pull/53896), unmerged | Apache-2.0 | Nightly image `vllm/vllm-openai:nightly-8a728663…` ships it |
| Reduced-vocab MTP draft (65,536-token corpus vocab) | [tonyd2wild/Qwen3.8-Flash-Next-NVFP4-DGX-Spark](https://github.com/tonyd2wild/Qwen3.8-Flash-Next-NVFP4-DGX-Spark) (overlay credits "Kai / 2Wild, 2026-09-05") | Apache-2.0 | Already in our overlay set; reverse A/B'd (+17%) and kept |
| Hybrid fp8 side-layer converter + shim | [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX) | Apache-2.0 | Used his converter on our ckpt; shim mounted env-gated; we credit/link, never re-post his files |
| Exact top-k overlay | ours, adapted from blazux's `patch_qsa_exact_topk.py` approach | MIT (ours) | Rewrote as env-gated overlay; measured zero cost |
| Deterministic top-k kernel | [jschmied/qwen38-flash-next-gb10](https://github.com/jschmied/qwen38-flash-next-gb10) | Apache-2.0 | Built + validated 210/210; parked, not shipped |
| PLE staging/mmap overlays | ours (fleet) | MIT (ours) | Env `QWEN4EXP_PLE_*` |

We keep a full off-node backup of the lane artifacts (overlays, launch/rollback scripts, kernel) on our NAS; nothing here re-posts third-party files.

## In this directory

- [`benchmarks/`](benchmarks/) — the measurement scripts and methodology (usage-based counting, T=0 determinism check, prefix-cache probe)
- [`verification/`](verification/) — the pre-deployment gate: coherence, determinism, tool-call, LiteLLM/router round-trip
