# Blackfrost DERISKED swap: uncensored GLM-5.3-Flash at knapcio-stack parity

**2026-10-10 — replacing the censored checkpoint under a live knapcio stack, without losing the +106%.** Companion to [knapcio-adoption.md](knapcio-adoption.md) (the stack swap); this page covers the checkpoint swap only.

Sources:

- **Checkpoint:** [Blackfrost-AI/GLM-5.3-Flash-DERISKED-NVFP4](https://huggingface.co/Blackfrost-AI/GLM-5.3-Flash-DERISKED-NVFP4) @ rev [`1ab31e8b`](https://huggingface.co/Blackfrost-AI/GLM-5.3-Flash-DERISKED-NVFP4/tree/1ab31e8bce94502c014b77593f206a66d49e01bd) — abliterated from `zai-org/GLM-5.3-Flash-BF16`, MIT
- **Stack:** unchanged — knapcio @ [`770d115`](https://github.com/knapcio/GLM-5.3-Flash-4x-DGX-Spark-TP4/commit/770d115) via tonyd2wild's TP2 port, image `glm53-roce:v11-b58f34ea`, DFlash2 drafter k=7
- **Config precedent:** tonyd2wild's `runs/2026-09-21-blackfrost-derisked` (W4A16 rewrite for the v11 dflash2 stack — different fix than ours, see below)

## What changed

| | Before | After |
|---|---|---|
| Base checkpoint | nvidia NVFP4 (33 shards, 111,755+36,297 tensor names) | Blackfrost DERISKED (120 shards, **111,755 names — zero `input_scale` anywhere**) |
| Dense-MLP layers 0–2 | NVFP4 + scales | **BF16 from upstream** → re-encoded block-128 FP8 locally (0.15–0.18% err; one tensor 2.36%) |
| Everything else | lossless8 quant mix, identical | identical (config byte-parity except the 12 dense-MLP entries) |

Converted tree: 205 GB/node logical, **14 GB of new blocks** (hardlink-backed against the base), byte-identical across both nodes. Config sha256 `ca6fc8c30a38dd67…`, dense-MLP overlay shard `model-qmix-lossless8-densefp8.safetensors` (7.4 GB, sha256 `33ea0995f7973d0d…`).

## The failure nobody had hit yet

knapcio's stack had only ever run nvidia-layout checkpoints; tonyd2wild ran derisked only on the v11 dflash2 stack. First boot of the combination died at 0% of load: `AssertionError` in vLLM `load_merged_column_weight` (the fused `gate_up_proj` path), loader-independent (identical with the fast loader disabled).

The generated quantization config diffed **identical** against the known-good tree — the delta is not in the config, it's in what the weights *are*. The test that finds it is a **tensor-name-set diff between base checkpoints**: Blackfrost ships no `input_scale` tensors at all and leaves the three dense (non-MoE) MLP layers BF16, where nvidia quantizes them NVFP4. A config generated under nvidia-layout assumptions builds 4-bit parameter slots, receives BF16 `[12288, 4096]` tensors, and asserts.

Two-stage fix, both measured:

1. **Unblock** — drop the 12 stale `quantized_layers` entries, ignore-list the 9 modules, load them BF16: boots clean, all quality gates pass, **38 tok/s median (−7%)**.
2. **Recover parity** — re-encode the 9 tensors with the stack's own `q_fp8_blk` into a new overlay shard + index + config entries: **41.1 / 40.3 medians vs the 41.0 censored baseline.**

A quantization-mix config is a layout contract, not a family recipe: re-derive it per checkpoint, and when a swap under an existing config fails at 0% of load with a shape assert in a merged-column loader, diff the tensor name sets before touching anything else.

## Measured

Same five-shape usage-based bench as the adoption page, same pair, single-stream:

| | censored lossless8 | Blackfrost stage-1 (dense BF16) | Blackfrost stage-2 (dense FP8) |
|---|---|---|---|
| Median decode | 41.0 tok/s | 37.2 / 39.3 (≈38) | **41.1 / 40.3** |

Quality gates on the final tree: refusal probe 5/5 (direct substantive answers on all five prompts — our own test, not upstream's claim), 3-needle retrieval 3/3 exact at 116K prompt tokens, exact-answer arithmetic, vision (image description correct).

## Cost

~5 h of lane downtime in total across download/build/swap/debug (of which ~90 min was the two boot-failure cycles before the name-set diff found it). Censored trees deleted after gates passed — this lane's rollback is now rebuild-from-library, not a directory repoint.
