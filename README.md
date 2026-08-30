# praxis

> Knowledge through practice — hard-won lessons from running a self-hosted AI agent fleet on real hardware.

Everything in this repo was **measured on our own silicon, benchmarked with open scripts, and survived production traffic.** No benchmarks-from-a-slideshare, no vibes. Where we benefited from someone else's work, we say so explicitly ([ATTRIBUTION.md](ATTRIBUTION.md)).

## Why this exists

Most public AI-agent content is either vendor demos or single-session experiments. Almost nobody publishes what happens *after* the demo: the deployment traps, the benchmark methodology bugs, the memory-system design that actually survives months of daily agent traffic. This repo is that layer — the operator's education, paid for in failed transfers, silent degradations, and cold-cache boot times.

## Contents

| Area | What's there |
|---|---|
| [`models/`](models/) | Serving recipes we run in production, with verification gates and honest numbers — start with [Qwen3.8-Flash-Next on a single DGX Spark](models/qwen3.8-flash-next/) |
| [`hermes/`](hermes/) | **The Hermes fleet** — operating patterns, agent skill patterns, and the full knowledge-management architecture (below) |
| [`LINKS.md`](LINKS.md) | Curated resources that earned a bookmark: recipes, checkpoints, tools, and the reference posts we actually learned from |

### Roadmap (content exists, sanitization in progress)

- `agent-zero/` — custom skills and dashboards for Agent Zero deployments

## The Hermes fleet section

Everything about running the agent platform itself:

| Doc | What it covers |
|---|---|
| [`hermes/fleet-operations.md`](hermes/fleet-operations.md) | Multi-profile fleet patterns: dependency-map discipline, model routing by task shape, autonomous learning loops, change control |
| [`hermes/agent-skill-patterns.md`](hermes/agent-skill-patterns.md) | Seven skill patterns that survived production: decision queue, knowledge preamble, blue-green runtime upgrades, structured handoff, edit-in-place rule, hard escalation, curator separation |
| [`hermes/knowledge-management/braindb.md`](hermes/knowledge-management/braindb.md) | **BrainDB** — SQLite-native agent memory with vector search, graph traversal, nightly reflection ("dreaming"), and confidence decay |
| [`hermes/knowledge-management/knowledge-flow.md`](hermes/knowledge-management/knowledge-flow.md) | The full knowledge architecture — seven stores with admission tests and matched half-lives, the reflection loop, and the document layer that started on open-source Elasticsearch |
| [`hermes/knowledge-management/learning-workflows.md`](hermes/knowledge-management/learning-workflows.md) | Autonomous learning workflows — the scheduled night-shift learners: fixed 4-unit cycles, tier-ranked persistence, watch lists, self-audit, and the rules that keep ~130 unattended cycles trustworthy |
- [`sparks/field-notes.md`](sparks/field-notes.md) — DGX Spark ops: power-event failure modes, blue-green model swaps, Docker-vs-native NCCL, cluster pairing

## The house rules

1. **Numbers or it didn't happen.** Every performance claim comes with the script that produced it.
2. **Failures are the content.** A lesson that didn't cost anything is usually wrong.
3. **Attribution upstream.** Recipes and checkpoints get named, linked, and credited — see [ATTRIBUTION.md](ATTRIBUTION.md).
4. **Nothing private ships.** No IPs, hostnames, credentials, or customer data ever.

## License

MIT — see [LICENSE](LICENSE). Attribution-noted upstream work remains the property of its authors.
