# GLM-5.3-Flash on a 2× DGX Spark cluster

Our production deployment record for GLM-5.3-Flash (NVFP4, 320B-class MoE) served with vLLM TP2 across two DGX Spark boxes. The recipe and container image are **[@tonyd2wild](https://github.com/tonyd2wild)'s** — [GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark](https://github.com/tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark), a world-first deploy recipe with seven day-0 bugs fixed and a patched SM121 image. What this page adds: an independent deployment on someone else's fabric, five localization fixes any second deployer will hit, and our own measured numbers.

## What's running

| Component | Value |
|---|---|
| Container image | `ghcr.io/tonyd2wild/vllm-glm53-flash:sm121-v11-dflash2` (31.2 GB) |
| Checkpoint | [RedHatAI/GLM-5.3-Flash-NVFP4](https://huggingface.co/RedHatAI/GLM-5.3-Flash-NVFP4) (185 GB per node) |
| Drafter (spec decode) | `incoai/GLM-5.3-Flash-DFlash2` (2.2 GB) — DFlash2, 7 speculative tokens |
| Topology | 2 nodes, TP2, `mp` executor; head serves :8000, worker joins over a private RoCE v2 link |
| Interconnect | The two Sparks' on-board 200 Gb RoCE ports on a dedicated subnet |

Serve flags (as-running — matching the upstream recipe):

```
vllm serve /models/glm-5.3-flash-nvfp4
  --served-model-name glm-5.3-flash
  --tensor-parallel-size 2 --distributed-executor-backend mp --nnodes 2
  --gpu-memory-utilization 0.85 --max-model-len 262144
  --max-num-seqs 6 --block-size 2304 --max-num-batched-tokens 8192
  --moe-backend marlin --kv-cache-dtype fp8_e4m3 --kv-cache-memory 3221225472
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

Context: this replaced a DeepSeek-V4-Flash deployment that hit 78 tok/s after tuning passes. GLM-5.3-Flash trades some single-stream speed for better tool-use, reasoning, and hallucination behavior on our workloads. First-night numbers; no tuning passes yet.

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
