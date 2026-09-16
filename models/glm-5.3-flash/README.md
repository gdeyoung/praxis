# GLM-5.3-Flash on a 2× DGX Spark cluster

Our production deployment record for GLM-5.3-Flash (NVFP4, 320B-class MoE) served with vLLM TP2 across two DGX Spark boxes. The recipe and container image are **[@tonyd2wild](https://github.com/tonyd2wild)'s** — [GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark](https://github.com/tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark), a world-first deploy recipe with seven day-0 bugs fixed and a patched SM121 image. What this page adds: an independent deployment on someone else's fabric, five localization fixes any second deployer will hit, and our own measured numbers.

## What's running

| Component | Value |
|---|---|
| Container image | `ghcr.io/tonyd2wild/vllm-glm53-flash:sm121-v11-dflash2` (31.2 GB) |
| Checkpoint | [RedHatAI/GLM-5.3-Flash-NVFP4](https://huggingface.co/RedHatAI/GLM-5.3-Flash-NVFP4) (185 GB per node) |
| Drafter (spec decode) | `incoai/GLM-5.3-Flash-DFlash2` (2.2 GB) — DFlash2, 7 speculative tokens (re-tuned 2026-09-16, see pass 2) |
| Topology | 2 nodes, TP2, `mp` executor; head serves :8000, worker joins over a private RoCE v2 link |
| Interconnect | The two Sparks' on-board 200 Gb RoCE ports on a dedicated subnet |

Serve flags (as-running — matching the upstream recipe):

```
vllm serve /models/glm-5.3-flash-nvfp4
  --served-model-name glm-5.3-flash
  --tensor-parallel-size 2 --distributed-executor-backend mp --nnodes 2
  --gpu-memory-utilization 0.85 --max-model-len 262144
  --max-num-seqs 6 --block-size 2304 --max-num-batched-tokens 8192
  --moe-backend marlin --kv-cache-dtype fp8_e4m3 --kv-cache-memory 6442450944
  --enforce-eager
  --speculative-config {"method":"dflash","model":"/models/dflash2-draft","num_speculative_tokens":7}
  --tool-call-parser glm47 --enable-auto-tool-choice --reasoning-parser glm45
  --default-chat-template-kwargs {"enable_thinking":false}
  --chat-template /models/glm-5.3-flash-nvfp4/chat_template_mm.jinja
```

## Verified numbers (usage-based, 2026-08-30)

Per our [benchmark methodology](../qwen3.8-flash-next/benchmarks/): count `usage.completion_tokens`, never SSE chunks — DFlash2 packs multiple tokens per stream event and event-counting reads roughly a third of true speed.

| Check | Result |
|---|---|
| Decode, single-stream, idle cluster | **56.3 tok/s cold → 60.1 tok/s canary** (recipe author's reference: 46.9 on identical hardware) |
| Decode with a concurrent interactive session sharing the box | 19.9 tok/s single-stream — the cluster shares; plan for contention |
| TTFT (greedy, 256-token generation) | 0.66 s |
| Determinism (T=0, repeated) | Byte-identical |
| Coherence | Clean prose, no degeneration at 256 tokens |
| Tool call (OpenAI format) | Correct JSON args (`{"city": "Chicago"}`) via `glm47` parser |
| Health → usable | 760 s cold boot (JIT + weight load) — see [deploy-watch](../deploy-watch.md) for why the poll budget must exceed this |

Context: this replaced a DeepSeek-V4-Flash deployment that hit 78 tok/s after tuning passes. GLM-5.3-Flash trades some single-stream speed for better tool-use, reasoning, and hallucination behavior on our workloads.

## Tuning pass 1 (2026-08-31) — KV 6 GiB + k=5

Adopted from the upstream repo's community tuning study (issue #11) with the maintainer's follow-up analysis (#12), applied as two sequenced gated changes — one variable per relaunch, full verification between.

| Change | Before | After | Why |
|---|---|---|---|
| `--kv-cache-memory` | 3 GiB | 6 GiB | KV pool 310K→643K tokens; the load-bearing fix for concurrency on TP2 |
| `num_speculative_tokens` | 7 | 5 | Acceptance decays hard past draft position 3; k=5 keeps ~86% of accepted tokens while cutting 28% of draft+verify compute |

Measured on our harness (usage-based, salted mixed prompts, 400-token generations):

| Workload | Baseline | After both |
|---|---|---|
| C1 (single-stream) | 44.1 tok/s | 42.1 tok/s |
| C4 (4 concurrent) | 44.5 tok/s | **53.2 tok/s** |
| C6 (6 concurrent) | 62.3 tok/s | **67.6 tok/s** |
| 6 × 61.5K-token prompts (369K tokens KV demand) | exceeds old pool — preemption regime | **zero errors, zero preemptions** |

Single-stream within noise (upstream documents ±30% single-pass swing on this hardware); the durable wins are concurrency and the elimination of preemption under long-context load. The 369K-token test is the one that matters: it's 119% of the old pool's capacity — the workload shape that used to force evict-and-recompute.

Quality gates after each change: determinism byte-identical at T=0, tool-call JSON clean, coherence clean, zero preemptions in logs.

## Tuning pass 2 (2026-09-16) — k back to 7, prefix cache repaired

Two changes, same day, each gated:

### k 5 → 7 (acceptance-regime retune)

Sixteen days after pass 1, the engine's per-position acceptance counters told a different story: ~100/97/96/91/90% at draft positions 0-4 (mean 4.75 of 5 tokens accepted per step). The decay-past-position-3 regime that justified k=5 was gone — spec-decode acceptance is a *measured* quantity, not a set-and-forget, so the depth gets re-tuned whenever the acceptance curve shifts.

| Workload | k=5 | k=7 |
|---|---|---|
| Structured decode (single-stream) | 54.5 tok/s | **64.9 tok/s (+19%)** |
| Prose decode (single-stream) | 30.3 tok/s | 30.1 tok/s (flat — the accept-collapsed lane, as expected) |
| C4 (4 concurrent) | 53.2 tok/s | 55.3 tok/s (holds) |
| C6 (6 concurrent) | 67.6 tok/s | 61.4 tok/s (−9%, watch item) |
| 6 × 61.5K-token prompts (370K tokens KV demand) | zero preemptions | **zero preemptions, 6/6 OK** |

Quality gates at k=7: determinism byte-identical, tool-call JSON clean, native vision verified (inline PNG → correct color). KV pool at k=7: 593K tokens (642K at k=5 — spec length trades pool size; both comfortably exceed max context × 2).

Operational note: our C4 baseline pass *crashed the engine* — first concurrency burst after a fresh boot triggers a TileLang kernel JIT mid-batch that stalled the worker RPC cross-rank into an EngineDeadError. Warm up new batch shapes with small concurrent requests (4 × 32-token gens) before any real concurrency bench on a cold boot. Our watchdog recovered the pair; the relaunch carried the k=7 flag.

### Prefix cache: 0 hits → working (upstream fix, our same-day deployment)

For our lane's entire life, `prefix_cache_hits_total` sat at **zero** across 35,000+ queries — `enable_prefix_caching=True` in config, no reuse in practice. Every agent turn re-prefilled the whole conversation.

Root cause (found by the community, fixed in upstream [PR #18](https://github.com/tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark/pull/18), which repairs [issue #13](https://github.com/tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark/issues/13)): the DFlash2 drafter runs its own KV cache group with a short sliding window. No group was flagged as the EAGLE group, so the coordinator's fallback flagged *every* group — and in `find_longest_cache_hit`, the draft window's short hit replaced the running hit length, collapsing the chain to zero. Identical prompts, block-aligned or not, never hit.

Deployed as a bind-mount overlay (no image rebuild): pull the live `kv_cache_coordinator.py` from the running image, verify the patch's anchors match exactly once, apply the patch to a local copy, run the predicate self-check, add one `-v` mount line to the launcher. One relaunch.

Verification with a block-size-aware probe (5,178-token prompt, sent 3×):

| send | wall | Δ hits |
|---|---|---|
| 1 (cold) | 4.30 s | 0 |
| 2 | 7.31 s | **+4,608** (= `floor(5178/2304)` × 2304 — exactly the complete blocks) |
| 3 (warm) | **0.71 s** | +4,608 |

Warm re-prefill is now 6.1× faster. Decode throughput unchanged (structured 64.4, prose 28.6 — noise band). Two probe lessons worth publishing: a prompt shorter than the block size (2,304 tokens here) has *zero* cacheable blocks — it will read as broken no matter what; and the commit lands on send 2 on this hybrid-mamba arch, not send 3 as on some lanes.

One caveat on the fix's scope: `--kv-cache-memory` at 6 GiB remains right for us, but the KV pool reading at k=7 is 593K tokens — if you push context hard with concurrency, size against that number, not pass 1's 643K.

## The five localization fixes (our contribution to the recipe's story)

The recipe works, but it ships *the author's* fabric and workflow. Five things we had to fix — any second deployer hits all five:

1. **Exec bits**: `git clone` drops the executable bit on the recipe's shell scripts — `chmod +x` before anything else, or scripts fail with confusing permission errors.
2. **Fabric values**: the recipe hardcodes the author's subnet, RoCE version, and GID index. Ours differ (ours: RoCE v1, different GID index, different address range). Derive yours from `ibdev2netdev` on both nodes and **use the same ACTIVE port on both** — name instability across reboots is a known trap (see [our field notes](../../sparks/field-notes.md)).
3. **Remote worker launch**: the recipe assumes two terminals, a human at each. If you script the cutover, the wrapper must SSH to the worker for rank 1 — launching it locally just runs a second head, which fails late and confusingly.
4. **Chat template location**: `chat_template_mm.jinja` lives in the recipe repo, not the HF checkpoint download — copy it into the model dir (or point `--chat-template` at the recipe path).
5. **hf_hub API churn**: `huggingface_hub` 1.16.1 removed the legacy `huggingface_cli` entry point — download weights with `snapshot_download()`, not the CLI the older scripts assume.

One more, environmental: a vLLM patch file (`sparse_attn_indexer_kpool.py`, Apache-2.0, from the recipe's overlay) is bind-mounted over the image's copy — the SM121 top-k crash fix. If you build your own image instead of pulling theirs, don't lose the overlay.

## Deployment pattern

We ran this as a gated blue-green cutover ([the pattern](../qwen3.8-flash-next/verification/)): backup-with-integrity-markers of the outgoing model → stop old containers → download new weights → worker-first TP2 launch → bounded health poll (budget > cold-boot time) → verification suite → router alias flip with config backup → watchdog repoint. The original pipeline had five real bugs (unexecuted localization, missing exec bits, download failures masked as success, an unverified backup gate, the local-launch bug above) — **every one was caught by a verification gate, not by the pipeline's own checks.** The gates are the deployment.

## Rollback

Old model's weights archived with sha256 + entry-count markers on the storage box; old containers stopped, not removed; router alias revert is a config-file swap. Full rollback costs a ~2-hour restore — which is why the backup verification ran *before* the old weights were cleared, not after.
