# Knapsack stack adoption: +106% median decode on our TP2 pair

**2026-10-07 — the production lane swap from vLLM v11 dflash2 to knapcio's speed stack, measured on our own hardware.**

Upstream sources, both credited:

- **Recipe (TP2 port):** [tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark](https://github.com/tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark) — `runs/2026-09-29-knapcio-tp2` (field report on their repo: issue #24)
- **Stack origin:** [knapcio/GLM-5.3-Flash-4x-DGX-Spark-TP4](https://github.com/knapcio/GLM-5.3-Flash-4x-DGX-Spark-TP4) @ commit [`770d115`](https://github.com/knapcio/GLM-5.3-Flash-4x-DGX-Spark-TP4/commit/770d115) — Dockerfile.roce, TP4 runbook, and the checkpoint-conversion scripts (TP4 native; tonyd2wild ported them to TP2)

We ran the old lane for five weeks (see the [main README](README.md) for its full tuning history — KV 6 GiB, k=7, prefix-cache fix). This page covers the swap only: what changed, what we measured, what it cost.

## What changed

| | Before (v11 dflash2) | After (knapcio @770d115) |
|---|---|---|
| Serving stack | vLLM `sm121-v11-dflash2` image | `glm53-roce:v11-b58f34ea` (built from the recipe's Dockerfile.roce on the old image as base) |
| Checkpoint | RedHatAI NVFP4 (185 GB/node) | nvidia-base NVFP4 → locally converted **lossless8** mix (204.5 GB/node, hardlink-backed) |
| Drafter | incoai DFlash2, k=7 | DFlash2 **fp8blk re-encode**, k=7 (mean re-encode error 2.64%, 148,070 tensors) |
| Weight load | ~11 min | **53 s** (mmap off the converted checkpoint) |
| Cold boot | 760 s | ~12 min first-ever (JIT), 140–190 s subsequent |

The nvidia base checkpoint (pinned rev [`09b04e5e`](https://huggingface.co/nvidia/GLM-5.3-Flash-NVFP4/tree/09b04e5e74bca08ca8549fc736d4cdd8624bfde3), config sha256 `e23c5d98f53e861d…`) stays on disk **forever** — the converted lossless8 tree hardlinks against it, so deleting it would rewrite ~200 GB of shared blocks. Same for the drafter (`bf582e4`, config `c4aeac01…` → converted hash `15bc8429…`). Converted-tree hash `f14dc13ce3bef88a5539c9e61b3e4f3dbef6958ebc3acda4b7f05f418642c3b0`, byte-identical across both nodes.

## Measured (usage-based, same bench, before vs after)

Five prompt shapes, single-stream, `usage.completion_tokens` counted per [our methodology](../qwen3.8-flash-next/benchmarks/). Same harness run before and after the swap on the same pair:

| Workload | Before | After | Δ |
|---|---|---|---|
| Prose | 8.9 tok/s | 34.6 tok/s | **+289%** |
| Narrative | 15.5 | 40.1 | **+159%** |
| Technical | 19.9 | 42.9 | **+116%** |
| Summary | 21.8 | 41.0 | **+88%** |
| Code | 42.6 | 65.4 | **+54%** |
| **Median** | **19.9** | **41.0** | **+106%** |

The pattern: the stack's win is largest exactly where the old lane was slowest — thinking-mode prose decode. Code, already the fastest shape, gains least. Upstream's own numbers (issue #24: tool calls 47.7→101, prose 18.1→35.3, peak 61→96) are consistent in direction and rough magnitude with ours; we measured the TP2 port, they measured TP4 + TP2-port averages.

Quality gates after cutover:

- **3-needle retrieval over 82,011 tokens: 3/3 exact** (62.3 s) — same gate we used adopting the lane originally
- **Vision input verified** (inline 64×64 PNG → "Red", 0.3 s); video stays disabled
- Zero reasoning tokens emitted at default effort in smoke tests
- LiteLLM router round-trip unchanged — same model id, same port, 11 dependents never noticed

## What it cost (the trade-offs, stated plainly)

1. **KV pool 789K → 560K tokens.** Still two full 262K sessions, but long-context concurrency headroom shrank. Documented fallback: 4 GiB if memory walls appear.
2. **Prefill ~13–17% slower.** Decode is what our lane does all day; accepted consciously.
3. **Thinking can't be fully disabled.** The new template has no `enable_thinking=false` equivalent; we default effort to `low`, which in practice emits zero reasoning tokens but is not the same guarantee.
4. **First-ever boot pays ~12 min of JIT.** Subsequent boots 140–190 s. Health-poll budgets and watchdogs must know this (see [deploy-watch](../deploy-watch.md)).

## Ops rewiring that shipped with it

- Watchdog repointed to the new containers (`glm53-r0`/`glm53-r1`) with a new relaunch path; the 15-minute canary cron renamed and reverified
- Old containers kept stopped on both nodes as an armed rollback (~5 min to restore the old lane)
- The RedHat 185 GB base on each node is deletion-pending after a clean-days burn-in window — the nvidia base is **not** deletable (hardlink backing)

One process failure worth recording honestly: our scripted cutover's post-conversion hash check read empty once ("false fatal") and we killed a perfectly good conversion — root-caused to most-likely fork failure under ~1 GB MemAvailable with 204 GB of fresh page cache seconds after conversion. Completed manually; the empirical retest of the pattern returned the correct hash. Lesson: don't run post-conversion verification in the same memory-pressure window as the conversion itself.
