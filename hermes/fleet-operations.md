# Operating a multi-profile agent fleet

Patterns from running ~a dozen specialized agent profiles on self-hosted hardware — routing, delegation, autonomous learning loops, and the change-control discipline that keeps it from eating itself. Schematic on purpose: no hostnames, no inventory specifics.

## The shape

```
            ┌─ routers / proxies (LLM access, search backends)
agents ──────┤─ per-role profiles (dev, research, media, ops, QA)
            ├─ shared knowledge stores (memory DB, vaults, ES, bookmarks)
            └─ scheduled jobs (learners, watchdogs, digesters)
```

Each profile gets: its own skills dir, its own memory, its own cron. They share: the dependency map, the knowledge governance rules, and the model router.

## The dependency map (the one practice that matters most)

Every fleet component — model endpoint, service, MCP tool, cron job, script other things call — is a node in a YAML dependency graph with `depends_on` edges. Before ANY change:

1. `depmap impact <id>` — who depends on this?
2. Make the change.
3. Verify every direct dependent, not just the thing changed.
4. Update the map in the same task, bump `checked:` date, push.

New components get declared in the map BEFORE they exist (zero dependents at birth — the node is what makes future changes see them). When prose docs and the map disagree, **the map wins** — it's dated and live-probed; the doc is a memory.

This single habit eliminates the "I restarted X and three cron jobs silently died" class of incident.

## Model routing by task, not by hype

A LiteLLM-style proxy fronts every model in the fleet. Aliases map task types, not model names:

| Task shape | Routes to |
|---|---|
| Fast iteration, cheap | small local model |
| Deep reasoning | big local MoE |
| Code generation | cloud code model |
| Vision | local multimodal |
| Embeddings | dedicated embed service |

Rule that survived contact with reality: **never let thinking-model requests carry `max_tokens` caps** — reasoning tokens count against the cap and you get silently truncated thought. Cap output length in the prompt contract, not the API call.

## Autonomous learning loops (the night shift)

Two learner profiles run on a fixed cycle (fleet knowledge, work knowledge). Each cycle: scan sources → study → persist findings by tier (top-tier insights to the vault, routine to the searchable index) → queue action items for human review. After ~75 cycles the pattern that matters:

1. **Track counts, not vibes** — "how many units landed where" per cycle, trended over weeks.
2. **Learners write everywhere except skills** — the skill curator is a separate background process; learner attempts to write skills generate hundreds of guardrail rejections per day and burn tokens for nothing. Give research crons a vault/bookmark target, never the skill store.
3. **A recurring complaint across N consecutive cycles is an escalated bug report** — our search tier produced garbage results four cycles straight before anyone treat it as a defect rather than weather.
4. **Real-workload validation beats synthetic tests** — when a model swap lands, the learners' overnight cycles are the canary. If the fleet wakes up and runs its loop, the swap holds.

## Change control that fits in one screen

- Impact-check the map before touching anything (see above).
- One variable per change. Hybrid-quantization flip ≠ also bumping context length.
- Rollback must be config-only (`MODE=x bash serve.sh`), with original artifacts untouched.
- Scheduled-work overlap check: before Docker-level changes, check no sibling session is mid-operation on the same host.
- Verify the *user experience*, not the health check — a 200 from `/health` is step zero (see [`models/qwen3.8-flash-next/verification/`](../models/qwen3.8-flash-next/verification/)).

## Knowledge governance (what goes where)

Seven stores, each with a one-line admission test:

| Store | Test |
|---|---|
| Always-injected prefs | "Does this change behavior every turn?" |
| Structured entity DB | "Is this a fact with attributes/relationships?" |
| Session DB | "Was this said in a chat?" (automatic — never hand-write) |
| Vaults | "Is this reasoning or narrative?" |
| Search index (ES) | "Is this a business document?" |
| Skills | "Is this numbered steps with commands?" |
| Bookmarks | "Is this a URL worth revisiting?" |

The failure mode is duplication — the same fact maintained in three places drifts apart. When two stores disagree, the dated, live-probed one wins.
