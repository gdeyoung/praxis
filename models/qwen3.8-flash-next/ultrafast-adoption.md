# UltraFast v16b on DGX Spark — adopting a community recipe over our own NVFP4 lane

> 2026-09-28 · Two DGX Sparks, production `local-agent` pool behind LiteLLM. This page is our field report: what we ran before, what we switched to, what it measured, and the deployment gotchas that cost us time.

We had a production Qwen3.8-Flash-Next lane of our own — the [NVFP4 recipe on this site](README.md) (NVIDIA's checkpoint byte-for-byte, our disk-backed n-gram table, staged gather, reduced-vocab MTP draft; ~44 tok/s median). Then [DimeRhyme's UltraFast recipe](https://github.com/dime-online/qwen3.8-Flash-DGX-UltraFast) landed on r/DGX_Spark claiming 74 tok/s single-stream on the same GB10 hardware. We blue-greened it against our lane on identical prompts. It won. This page is the honest before/after and the recipe we now run.

## TL;DR numbers (fair fight: same prompts, thinking off, 3 rounds each)

| | Our NVFP4 lane | UltraFast v16b | Δ |
|---|---|---|---|
| Median decode throughput | 187 cps | **229 cps** | **+22%** |
| Mean TTFT | 0.20 s | **0.17 s** | −15% |
| Categories won (of 8) | 1 (one tie) | **7** | — |
| Copy-heavy tasks | 200 cps | **289 cps** | +45% |
| Tool-call round-trip | works | works (exact args) | — |
| Image + video input | works | works | — |

Throughput here is chars/sec from our streaming harness (same treatment both sides; divide by ~4 for rough tok/s). Their headline 74 tok/s is a copy-heavy best-of-3 number — on the same class of workload we measured ~57 tok/s-equivalent vs our ~47. The honest like-for-like gain is **20–25%, not 70%**. Still the largest decode jump available to this model without new hardware.

## Provenance — every piece and its origin

We stack three upstreams; nothing here is re-posted from their repos. Their launchers, their configs, their LICENSE terms (all verified Apache-2.0 at citation time):

| Component | Origin | License (verified) | What we did |
|---|---|---|---|
| Base recipe, PLE-table-on-disk concept, draft-vocab idea | [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX) | Apache-2.0 | Credited ancestor of both forks; our NVFP4 lane derives from this lineage |
| W4A16 AutoRound checkpoint + fp8 PLE table | [Saren-Arterius/qwen3.8-Flash-DGX-AutoRound](https://github.com/Saren-Arterius/qwen3.8-Flash-DGX-AutoRound) (checkpoints on [HF: Saren](https://huggingface.co/Saren)) | Apache-2.0 | Downloaded pinned revisions; ran their prepare pipeline outputs |
| Dense-MTP drafter + low-latency GEMM + sort-free top-k | [dime-online/qwen3.8-Flash-DGX-UltraFast](https://github.com/dime-online/qwen3.8-Flash-DGX-UltraFast) | Apache-2.0 | Adopted as-is on our second Spark; added fleet wiring + verification |

The dense drafter is the interesting trick: the MoE MTP draft head (the expensive part of speculative decode on this model) is converted to a **dense g32 drafter** (9 modules), which gets ~3.7 accepted tokens per step flat across 1–8 streams. Same reduced 65K draft vocab idea as our lane, English/code-weighted — CJK-heavy traffic loses acceptance (and speed), quality unaffected since the target verifies every drafted token.

## What actually differs from our NVFP4 lane

| | Our old lane | UltraFast v16b |
|---|---|---|
| Checkpoint | NVIDIA NVFP4, byte-for-byte | W4A16 AutoRound experts, INT8 lm_head, fp8 sides |
| Drafter | MoE MTP, 65K vocab | **Dense g32 MTP**, 65K vocab, block rejection |
| PLE n-gram table (47.7 GiB) | our preadv disk gather | fp8 table, NVMe mmap, prewarm |
| KV | fp8_e4m3, pool ~1M tok | 16 GiB explicit pool |
| Vision | works (untested before this) | works (image + video) |
| Load time | ~10 min | **~5 min** (fastsafetensors) |

## Deployment gotchas (the part that cost time)

1. **The T80 builder self-test crashes on a read-only mount.** `test_rtn_int4_gptq.py::test_safetensors_roundtrip` writes a scratch `.safetensors.partial` to its cwd, and `build.sh` runs the tests with the repo mounted `:ro`. You get `OSError: [Errno 30] Read-only file system` and EXIT=1. Workaround without touching repo bytes: run the three self-tests with a writable scratch dir as cwd and `PYTHONPATH=/work`, then run the build + verify commands verbatim. Their `VERIFY OK` gate then passes. (Trivial upstream bug; worth an issue.)
2. **Thinking is ON by default in their launcher.** Our lane ships `enable_thinking: false`. If you benchmark their recipe without sending `chat_template_kwargs: {enable_thinking: false}`, draft acceptance craters and you'll under-measure it by ~30%.
3. **~130 GB of HF downloads, unauthenticated, are rate-limited.** Budget ~45 min for checkpoint + PLE table (81 + 35 files).
4. **Both recipes need ~87 GB of the 121 GB unified pool — no side-by-side on one Spark.** Blue-green means swap, not parallel. We ran the candidate on our second Spark and let the LiteLLM pool split traffic during soak.
5. **Old checkpoints still on disk eat ~195 GB.** Plan the retention story before you start; a two-Spark fleet holding both recipes needs ~1.3 TB.

## Our bench harness

8 prompt categories × 3 rounds (qa, code, json, math, longcode, summary, agent tool-use, copy), streamed, T=0.7, thinking off, chars/sec from stream deltas, TTFT from first delta. Same prompts hit both endpoints sequentially on an idle pool. We count chars, not SSE events (the [MTP/SSE trap](benchmarks/)): with speculative decoding, chunk counts lie by the acceptance rate.

## Ops notes

- Pool routing: two deployments behind one alias, usage-based routing; the faster node naturally absorbs more traffic (~2:1 after a day of soak, zero errors, zero restarts).
- Rollback: one docker command restores the previous container, one config edit restores the old endpoint. Keep the old checkpoint until soak is done.
- Soak checklist before calling it adopted: real traffic through a full day of cron cycles, decode latency drift, memory drift, restart count.

## Credits

- [DimeRhyme](https://github.com/dime-online) for the UltraFast recipe and for flipping it to Apache-2.0 on request in the original thread.
- [Saren-Arterius](https://github.com/Saren-Arterius) for the AutoRound checkpoint work.
- [blazux](https://github.com/blazux/qwen3.8-Flash-DGX) for the founding recipe of this whole lineage and the best quantization-bandwidth analysis we've read.
