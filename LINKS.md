# Links — resources that earned a bookmark

Curated, not comprehensive. Everything here was used on real hardware in this fleet and earned its place. (Related: [ATTRIBUTION.md](ATTRIBUTION.md) for work praxis builds on.)

## Serving recipes
- tonyd2wild — [GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark](https://github.com/tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark) — the recipe this fleet's [GLM-5.3 deployment](models/glm-5.3-flash/) is built on; seven day-0 fixes, patched SM121 image
- RedHatAI — [GLM-5.3-Flash-NVFP4](https://huggingface.co/RedHatAI/GLM-5.3-Flash-NVFP4) — corruption-free NVFP4 checkpoint (DGX Spark / GB10)

- [blazux/qwen3.8-Flash-DGX](https://github.com/blazux/qwen3.8-Flash-DGX) — single-Spark Qwen3.8-Flash-Next recipe; the hybrid fp8 side-layer conversion writeup is the best quantization-bandwidth analysis we've read
- [tonyd2wild's repos](https://github.com/tonyd2wild?tab=repositories) — DS4F deployments and Spark tooling (2Wild-Beast, Model-Eval, DeepSeek-Harness series); his config discipline is the standard we hold ourselves to
- [build.nvidia.com](https://build.nvidia.com) — NVIDIA's Spark/GB10 project hub: firmware, examples, forums where the Spark practitioner community actually lives

## Checkpoints

- [RadixArk/Qwen3.8-Flash-Next-NVFP4](https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4) — the NVFP4 build our production config runs
- [Qwen/Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) — official
- [Qwen/Qwen3.8-Flash-Next-FP8](https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8) — official FP8, verified listing

## Model serving

- [vllm-project/vllm#53896](https://github.com/vllm-project/vllm/pull/53896) — Qwen3.8-Flash-Next support PR (watch it land)
- [vllm-project/vllm](https://github.com/vllm-project/vllm) — the serving layer everything above runs on

## Agent frameworks & memory

- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) — the agent runtime this fleet runs; skills, cron, multi-profile
- [getzep/graphiti](https://github.com/getzep/graphiti) — temporal knowledge-graph engine; the closest public analog to our memory design
- [asg017/sqlite-vec](https://github.com/asg017/sqlite-vec) — SQLite vector extension; our planned upgrade path from brute-force search

## Community

- [r/LocalLLaMA](https://www.reddit.com/r/LocalLLaMA/) — where the practitioner posts that seeded half this repo were found
