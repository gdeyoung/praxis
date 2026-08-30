# Fleet economics — the cost model for self-hosted agent infrastructure

Rough numbers, honestly labeled: what a self-hosted agent fleet costs to run versus API-only, where cloud is genuinely cheaper, and the routing rules that prevent silent cost drift. Hardware-specific where it matters, directionally correct everywhere. Your costs will differ; the *shape* of the analysis won't.

## The stack being costed

A dozen agent profiles (dev, research, media, ops, QA, security, chief-of-staff…) on six servers: two mid-range GPU servers, two DGX Spark-class compact boxes, two storage/service boxes, all bought used or at launch pricing over three years. Local models served via a router proxy with cloud fallback for SOTA tasks.

## Capital vs operating (the honest table)

| Cost line | Self-hosted | API-only equivalent |
|---|---|---|
| Hardware (amortized 3 yr) | ~$40–70/mo across the fleet | $0 |
| Power (24/7, ~0.9–1.4 kW average) | ~$100–160/mo at $0.12/kWh | $0 |
| Network + UPS + misc | ~$10/mo | $0 |
| Inference | $0 marginal | Dominant line — scales with usage |
| SOTA cloud usage (the 5%) | ~$15–60/mo | (this, ×20) |
| Maintenance time | 2–4 hr/mo | ~0 |

**The crossover:** if your fleet's aggregate token volume stays under roughly 2–5M tokens/day, pure API is cheaper in cash terms and you should probably take it — self-hosting for cash reasons at low volume is a hobby, not a strategy. Above that line, owned silicon wins on cash and adds capabilities APIs can't sell you: unlimited cheap context for autonomous learners, private data guarantees, zero rate limits, and no per-request anxiety about "was this question worth a query?"

## Where cloud is actually cheaper

Be honest about this or the routing table lies to you:

- **SOTA reasoning quality** — the frontier models are genuinely better at hard reasoning than anything that fits on two 24 GB cards. Fighting that with volume is false economy on the tasks that matter most.
- **Bursty, rare capabilities** — a vision task you run weekly doesn't justify a vision model's VRAM residency.
- **Anything during a hardware incident** — cloud fallback isn't defeat, it's the reason the fleet survives a dead node without stopping.

Our split lands around **90–95% local tokens / 5–10% cloud spend**. The cloud line stays small because of the rules below.

## Routing rules that prevent silent cost drift

Cost drift in an agent fleet is death by a thousand model-choice defaults. Four rules stop it:

1. **Route by task shape, not model name.** Aliases (`local-fast`, `local-heavy`, `cloud-dev`, `embed`) map to implementations. Consumers never hardcode a model, so swapping implementations is a one-line alias change, and cost changes are visible in exactly one place.
2. **SOTA allowlist.** Exactly two cloud models are authorized for premium routing (a frontier reasoning model and a long-context model). Anything else routes local-first. No "just try GPT-X" — every new model gets an explicit decision before it enters the table.
3. **Code models never fall back upward.** The code-generation alias has a hard rule: on failure, retry local, never silently route to a premium cloud model. The day a retry loop quietly pointed at a frontier API is the day you learn what a token bill looks like when an agent loops.
4. **Scheduled jobs default to the cheapest tier that works.** Learners and watchers run on local models, full stop. Autonomous volume × premium pricing is the single fastest way to light money on fire.

## The capability dividend (why we still do it)

Cash parity undersells it. What the hardware actually buys:

- **Unmetered context.** The learners' nightly cycles would be unaffordable at API prices — hundreds of thousands of tokens nightly, every night, for months. That's the flywheel; you can't rent the flywheel.
- **Privacy.** Meeting transcripts, personal documents, and work data never cross a boundary we don't control.
- **No rate limits.** Scheduled jobs at 06:00 don't queue behind anyone.
- **The hardware is multi-tenant.** The same GPUs serve inference, transcription, image and video generation. Amortizing across workloads is where the real economics live.

## Decision rules if you're starting

- Under ~2M tokens/day: API-only, spend the difference on better prompts and evals. Seriously.
- 2–20M/day with privacy needs or autonomous workloads: one good used GPU server beats three bad ones. Buy the biggest single cards you can power and cool.
- Above that, or with media generation in the mix: the fleet shape looks like ours — two inference-focused boxes, one GPU box for generation workloads, one boring storage box, and a router in front of everything.

The last rule is the one that matters: **every model request flows through one proxy with aliases.** Whatever else you skip, don't skip that — it's the difference between a fleet you can reason about and a credit-card surprise.
