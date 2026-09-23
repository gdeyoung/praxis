# praxis

> Knowledge through practice — hard-won lessons from running a self-hosted AI agent fleet on real hardware.

Everything in this repo was **measured on our own silicon, benchmarked with open scripts, and survived production traffic.** No benchmarks-from-a-slideshare, no vibes. Where we benefited from someone else's work, we say so explicitly ([ATTRIBUTION.md](ATTRIBUTION.md)).

## Why this exists

Most public AI-agent content is either vendor demos or single-session experiments. Almost nobody publishes what happens *after* the demo: the deployment traps, the benchmark methodology bugs, the memory-system design that actually survives months of daily agent traffic. This repo is that layer — the operator's education, paid for in failed transfers, silent degradations, and cold-cache boot times.

## Contents

| Area | What's there |
|---|---|
| [`models/`](models/) | Serving recipes we run in production, with verification gates and honest numbers — [Qwen3.8-Flash-Next on a single DGX Spark](models/qwen3.8-flash-next/), [GLM-5.3-Flash on a 2-node Spark cluster](models/glm-5.3-flash/), plus [deploy-watch](models/deploy-watch.md) |
| [`agents/`](agents/ROLE-TEMPLATE.md) | **Recreate our fleet** — the [role template](agents/ROLE-TEMPLATE.md) every agent/subagent is defined by |
| [`hermes/`](hermes/) | **The Hermes fleet** — operating patterns, agent skill patterns, and the full knowledge-management architecture (below) |
| [`search/`](search/) | [Tiered web access](search/web-access.md) — routing, fallback chains, and quality-drift detection for search backends |
| [`media/`](media/) | [Verification-gated media generation](media/verification-gates.md) — zero-stumble narration, subtitle constraints, hardware encode, pre-production spend gates · [Portal platform](media/portal-platform.md) — one Caddy entry, catalog+provenance JSON, static sections, the deploy pitfalls |
| [`research/`](research/) | [The interest funnel](research/interest-funnel.md) — from a saved-link hoard to an agent that knows what you care about |
| [`LINKS.md`](LINKS.md) | Curated resources that earned a bookmark: recipes, checkpoints, tools, and the reference posts we actually learned from |

### Roadmap (content exists, sanitization in progress)

- Fleet ops telemetry dashboards (agent/bus health at a glance)
- `agent-zero/` — custom skills and dashboards for Agent Zero deployments

## The Hermes fleet section

Everything about running the agent platform itself:

| Doc | What it covers |
|---|---|
| [`hermes/fleet-operations.md`](hermes/fleet-operations.md) | Multi-profile fleet patterns: dependency-map discipline, model routing by task shape, autonomous learning loops, change control |
| [`hermes/litellm-pitfalls.md`](hermes/litellm-pitfalls.md) | **Operating an LLM router proxy in production** — thirty silent-failure modes across config/DB/fallback layers, and the probe that catches each: ghost models, dead-hop masking, timeout-retry token amplification, hot-reload nukes, vendor-edge lies |
| [`hermes/model-calibration.md`](hermes/model-calibration.md) | Per-model-family prompt blocks injected at the router — grounded behavior fixes for every caller at once, with the A/B that justified rollout and the behavioral-probe method |
| [`hermes/plugin-seam.md`](hermes/plugin-seam.md) | Small fail-open hooks instead of forking the agent: live-state injection, intent routing, command seatbelt — the contract that makes per-turn plugins safe |
| [`hermes/core-patches.md`](hermes/core-patches.md) | Five-file patch series carried against the vendored runtime (zero-result search failover, admin-route probe collision, shutdown hygiene) — upstreamable, revertible, no fork |
| [`hermes/gpu-lane-governance.md`](hermes/gpu-lane-governance.md) | Leases + reapers for shared GPUs: `gpu-take` claims with owners and TTLs, session reservations for pipelines, 14-check regression gate |
| [`hermes/lan-service-bridges.md`](hermes/lan-service-bridges.md) | LAN services as agent tools — one-file stdio wrappers vs streamable-HTTP bridges, and the probe-before-you-bridge decision rule |
| [`hermes/cron-at-fleet-scale.md`](hermes/cron-at-fleet-scale.md) | ~100 scheduled jobs: the lock-tombstone lesson, missed-fire detection from the jobs DB, transports matched to attention |
| [`hermes/fleet-sync.md`](hermes/fleet-sync.md) | One skill tree, many machines: one-way git backup, pull-on-demand skills, per-host trees, role-matched seed packages |
| [`hermes/delegation-mechanics.md`](hermes/delegation-mechanics.md) | How a parent supervises workers: live transcripts, done-markers, bounded parallelism, YAML-defined councils, when not to delegate |
| [`hermes/external-harness-wiring.md`](hermes/external-harness-wiring.md) | Wiring an external coding harness (OpenCode/Claude Code/Codex class) as a callable dev subagent — the four-requirement socket |
| [`hermes/fleet-monitoring.md`](hermes/fleet-monitoring.md) | **Monitoring the fleet** — passive checks, death signatures, UPS forensics, the alert-discipline rules that keep alerts trusted |
| [`hermes/webui-operations.md`](hermes/webui-operations.md) | **Operating the chat WebUI** — the no-fork rule, extension sidecars over core patches, capped-session recovery, inline media players |
| [`hermes/fleet-economics.md`](hermes/fleet-economics.md) | The cost model: owned silicon vs API-only, where cloud is genuinely cheaper, routing rules that stop silent cost drift |
| [`hermes/agent-skill-patterns.md`](hermes/agent-skill-patterns.md) | Seven skill patterns that survived production: decision queue, knowledge preamble, blue-green runtime upgrades, structured handoff, edit-in-place rule, hard escalation, curator separation |
| [`hermes/recipe-doctor.md`](hermes/recipe-doctor.md) | **The recipe doctor** — drift-auditing a repo-managed machine: inventory-turned-executable checks, notify-only-on-change gating, and the pitfalls that bit during bring-up (empty-SHA clean state, prefix-aware pin compare, check-the-checker) |
| [`hermes/knowledge-management/braindb.md`](hermes/knowledge-management/braindb.md) | **BrainDB** — SQLite-native agent memory with vector search, graph traversal, nightly reflection ("dreaming"), and confidence decay |
| [`hermes/knowledge-management/knowledge-flow.md`](hermes/knowledge-management/knowledge-flow.md) | The full knowledge architecture — seven stores with admission tests and matched half-lives, the reflection loop, and the document layer that started on open-source Elasticsearch |
| [`hermes/knowledge-management/learning-workflows.md`](hermes/knowledge-management/learning-workflows.md) | Autonomous learning workflows — the scheduled night-shift learners: fixed 4-unit cycles, tier-ranked persistence, watch lists, self-audit, and the rules that keep ~130 unattended cycles trustworthy |
- [`sparks/field-notes.md`](sparks/field-notes.md) — DGX Spark ops: power-event failure modes, blue-green model swaps, Docker-vs-native NCCL, cluster pairing

The fleet's desktop layer is documented in its own repo: [gdeyoung/omarchy-recipes](https://github.com/gdeyoung/omarchy-recipes) — recipe-repo discipline, the measured update-overwrite model, and plugin hygiene for Omarchy (Arch + Hyprland) machines.

## The house rules

1. **Numbers or it didn't happen.** Every performance claim comes with the script that produced it.
2. **Failures are the content.** A lesson that didn't cost anything is usually wrong.
3. **Attribution upstream.** Recipes and checkpoints get named, linked, and credited — see [ATTRIBUTION.md](ATTRIBUTION.md).
4. **Nothing private ships.** No IPs, hostnames, credentials, or customer data ever.

## License

MIT — see [LICENSE](LICENSE). Attribution-noted upstream work remains the property of its authors.
