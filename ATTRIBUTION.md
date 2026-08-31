# Attribution

Praxis documents our operational experience. Where that experience started from someone else's published work, this file names them. Their code and checkpoints remain theirs.

## Recipes & configurations

| What | Author | Where | How we use it |
|---|---|---|---|
| Single-DGX-Spark Qwen3.8-Flash-Next recipe (NVFP4 + MTP + hybrid fp8 mode) | **blazux** | [github.com/blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX) | Starting point for our production serving config on one DGX Spark. We added verification gates, benchmark methodology, and fleet integration. Repo has no license file at time of writing — we link and credit rather than copy. |
| DS4F (DeepSeek-V4-Flash) NVFP4-KV deployment recipes & DGX Spark tooling | **tonyd2wild** | [github.com/tonyd2wild?tab=repositories](https://github.com/tonyd2wild?tab=repositories) | Reference for our two-node Spark cluster deployments (DeepSeek-Harness series, 2Wild-Beast, 2Wild-Model-Eval). |

## Model checkpoints

| Checkpoint | Publisher | Where |
|---|---|---|
| GLM-5.3-Flash NVFP4 recipe + SM121-patched image | **tonyd2wild** | [github.com/tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark](https://github.com/tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark) |
| GLM-5.3-Flash NVFP4 checkpoint | **RedHatAI** | [huggingface.co/RedHatAI/GLM-5.3-Flash-NVFP4](https://huggingface.co/RedHatAI/GLM-5.3-Flash-NVFP4) |
| Qwen3.8-Flash-Next NVFP4 | **RadixArk** | [huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4](https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4) |
| Qwen3.8-Flash-Next (official) | Qwen team | [huggingface.co/Qwen/Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) |

## vLLM support

- Qwen3.8-Flash-Next vLLM support PR — community contribution under review: [vllm-project/vllm#53896](https://github.com/vllm-project/vllm/pull/53896)

## Heritage

| Project | Note |
|---|---|
| ClearVoice | Evolved from an earlier "krisp-linux" meeting-recorder concept; GPL-3.0 lineage retained. Independent PyQt6 application. |

## Standing note

If you find your work referenced here without adequate credit, open an issue and it will be fixed promptly. Measurement results published in this repo are our own, produced on our hardware; any errors in them are also our own.
