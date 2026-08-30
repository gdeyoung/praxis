# The knowledge flow — how an agent fleet remembers

The memory architecture our fleet settled on after months of iteration. It started with a simple question: *where should an agent write what it just learned?* The wrong answer — "one big memory" — fails in interesting ways within weeks. This is the right answer we found, layer by layer.

The long-term repository layer started on **open-source Elasticsearch** (self-hosted, free license) before we'd touched anything else — that choice scaled from a single index to the fleet's searchable institutional memory without a rewrite. It's still the backbone.

## The flow

```
        live conversation                    autonomous learning
              │                                     │
              ▼                                     ▼
     ┌─────────────────┐                  ┌──────────────────┐
     │ structured facts │                  │  extract → study │
     │  (entity/graph   │                  └────────┬─────────┘
     │   memory, SQLite)│                           │
     └────────┬────────┘                           ▼
              │                            ┌──────────────────┐
              │ nightly reflection          │ tiered persistence│
              │ ("dreaming": patterns,  ───▶│ top tier → vault  │
              │  insights, decay)           │ routine → search  │
              │                             │ index (ES)        │
              ▼                             └────────┬─────────┘
     ┌─────────────────┐                             │
     │ always-injected │◀──── retrieval ◀────────────┘
     │  preferences    │      (hybrid: vector + FTS + graph)
     └─────────────────┘
```

## The layers, by half-life

| Layer | What lives there | Half-life | Admission test |
|---|---|---|---|
| Session DB | The conversation itself | Days (rotation) | — (automatic, never hand-written) |
| Always-injected prefs | Behavior-changing rules ("never cap thinking-model tokens") | Months | "Does this change behavior *every* turn?" |
| Structured memory (graph/vector) | Facts with attributes + relationships: entities, state, observations | Weeks (confidence decay) | "Is this a fact?" |
| Vault (narrative) | Reasoning, trade-offs, build stories, ideas | Years | "Is this reasoning, not a fact?" |
| Search index (ES) | Business docs, meeting transcripts, research, intel | Years, query-centric | "Will someone search for this?" |
| Skills (procedural) | Numbered steps with commands | Indefinite (curated) | "Is this a repeatable procedure?" |
| Bookmarks | URLs worth revisiting | Months | "Is this a source?" |

The half-life column is the design insight: **each layer's decay rate matches how the knowledge is actually used.** Conversations age out fast; preferences persist until contradicted; narrative reasoning is near-permanent; searchable documents are ageless but query-gated.

## Why a graph+vector SQLite brain *and* a search index

They answer different questions:

- **The brain (SQLite, embeddings + FTS5 + typed relationships)** answers *"what do I know about X and how does it connect to Y?"* — with confidence scores, decay, and a nightly reflection pass that promotes patterns into insights.
- **The search index (Elasticsearch)** answers *"find me the document about the Q3 account review"* — full-text, filters, aggregation, zero semantics needed.

Collapsing them into one store means either your graph queries are slow or your full-text search is primitive. We run both, and the admission test decides where a write lands — never both (duplication drifts).

## The reflection loop (what makes it a *system*)

1. **Extract** — nightly, sessions are mined for structured observations (attribute/value/confidence) by the local model.
2. **Dream** — the memory graph is analyzed: pattern distribution, knowledge hubs, recurring observations, staleness. Output: scored insights + a human-readable report. Confidence decays on a 30-day half-life; below-threshold entities archive rather than delete.
3. **Act** — high-priority insights land in a review queue; recurring error patterns (3+ occurrences) surface as "codify this into a skill" recommendations to the curator.
4. **Curate** — the only path into procedural skills runs through schema validation and review (see [agent-skill-patterns.md](../agent-skill-patterns.md) §7).

## Governance rules that keep it honest

- **One admission test per store.** If you can't name the test, you don't know where it goes — don't write it yet.
- **The dated, live-probed source wins** any disagreement between stores.
- **Facts go to the graph; stories go to the vault; documents go to the index.** The same information in two stores is a bug.
- **Learners never write skills directly** — curator separation (rejection-count monitoring catches misconfigurations).
- **Dreams are not facts.** Reflection output informs, never asserts — otherwise the agent starts citing its own dreams as ground truth.

## Getting started

The stack is deliberately boring: SQLite (graph + FTS5 + brute-force vectors — fine under ~100k entities), Elasticsearch open source for the document layer, markdown vaults for narrative, a cron scheduler for the reflection loop. The interesting part isn't any component — it's the admission tests and the decay rates. Start with those, add stores only when a real question can't be answered.
