# Abliterated requant: pinning a derivative to the stock EXL3 recipe

2026-10-11 — huihui-ai's Qwen3.8-Flash-Next abliteration requantized to the stock 3.05bpw
EXL3 allocation, cut over on both Spark velo lanes. Public artifacts:
[recipe repo](https://github.com/gdeyoung/qfn-abl-exl3) ·
[weights](https://huggingface.co/gdeyoung/Huihui-Qwen3.8-Flash-Next-abliterated-EXL3-3.05bpw-integer).
Build log: `vault fleet/builds/qwen38fn-abl-3bpw-requant-2026-10-11.md`.

## The class-level lesson

Requantizing a community derivative (abliteration, merge, finetune) to an existing serving
recipe is not "run the converter with the same flags." Two converter-era assumptions break:

1. **Allocator drift.** exllamav3 1.4.4 (stock pack era) vs 1.6.x (current) — the LP
   allocator now emits fractional trellis rates under mul1, and the GB10 loader rejects
   them (`trellis dims 56`). The stock packs are all-integer by construction of their era.
   Fix: extract the stock pack's per-tensor allocation from safetensors headers
   (bits = last_dim/16 for trellis tensors) and pin it via the recipe file. Bonus: the
   recipe path skips the LP search and reproduces the stock memory/speed profile exactly.
2. **Index-assembly conventions the converter doesn't perform.** `--ngram_file` copies the
   32GB PLE table but leaves its 132 index entries and the inclusive `total_size` unmerged;
   the loader panics `ple shard 0 not in index`. Whatever pack-assembly step the original
   publisher did by hand must be replicated post-conversion.

Also: serve binaries resolving `src/ptx/*.ptx` relative to CWD (systemd `WorkingDirectory`
masks this in prod; manual launches from `$HOME` panic), and long SSH command strings from
the control host corrupt in transit ~1-in-8 — stage scripts as files, don't inline.

## Numbers (per Spark, single-node, 262k ctx, batch 5)

65 tok/s median decode (usage-token math, thinking-off) vs ~54 stock idle; MTP2 52–63%
acceptance, 3.87 tok/round peak; 1,560 tok/s prefill at 226k; refusal triage 20/20;
needle recovered at 226,497 tokens; temp-0 determinism; vision/tools/streaming/concurrency
all pass. Full battery: repo README.

## Fleet state

Both velo lanes serve `qwen-abl` (id string changed from `qwen` — clients matching on id
string updated at the router, not the wire). Stock packs retained as rollback on both
nodes. ~460G of build scratch (source + failed fractional run) pending cleanup approval.
