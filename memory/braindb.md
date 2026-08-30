# BrainDB — SQLite-native agent memory with a sleep cycle

**A local-first memory system for AI agents: one SQLite file providing vector search, knowledge-graph traversal, keyword/FTS5 search, and — the part nobody else publishes — a nightly reflection pipeline ("dreaming") with confidence decay.**

Runs in production on a self-hosted [Hermes Agent](https://github.com/NousResearch/hermes-agent) fleet. Zero external databases, zero network dependencies beyond your own inference endpoint.

## Design in one screen

```
sessions ──1:30AM──▶ extraction ──▶ observations ─┐
                                                  ├─▶ hybrid search (vector+FTS5+graph)
memory entities ◀── LLM observation extractor ────┘        │
      │                                                    ▼
      ├── embeddings (768d, batched)              context injection (<200ms)
      ├── relationships (typed, weighted)                  │
      └── confidence + timestamps                          ▼
             │                                      agent turn context
             ▼
   2:00AM "dreaming": pattern analysis → scored insights →
   reflection artifacts → action queue; confidence decay
   (30-day half-life) archives stale memories
```

## Why SQLite

The design bet: an agent fleet's memory fits in one SQLite file comfortably under ~100k entities, and brute-force vector search over that scale is sub-perceptible inside a 200ms context-injection budget. No vector DB, no graph server, no container — just a `.db` file you can `scp`, version, and restore. The cost is O(n) search, which we accepted deliberately (see Limitations).

## What "dreaming" actually does

Most agent-memory writeups stop at retrieval. The interesting half is what the system does *to itself* overnight:

1. **Pattern analysis** — entity/relationship distributions, knowledge hubs, temporal clustering
2. **Observation analysis** — recurring attributes, high-confidence knowledge coverage
3. **Insight generation** — scored insights (0.0–1.0) with evidence and recommended actions
4. **Reflection artifacts** — structured JSON + human-readable reports per cycle
5. **Confidence decay** — 30-day half-life; entities below 0.3 are archived, not deleted
6. **Error patterns** — recurring failures (3+ occurrences) surface as recommendations to codify a skill

The insight-to-action queue closes the loop: high-priority dream items land in a review file the agent checks on its next session.

## Numbers from production

| Operation | Measured |
|---|---|
| Context injection end-to-end | <200ms (keyword ~5ms, FTS5 ~50–100ms, context build ~20ms) |
| Graph traversal, 3-hop on 10k nodes | ~0.9ms |
| Embedding, per entity (768d, batched) | ~0.5s |
| LLM observation extraction, per session | ~2–5s |

## Lessons that cost us something

1. **Mock embeddings poison the well.** Early dev used hash-based fake vectors. Real embeddings have negative components; mocks don't — that one asymmetry became the detector, plus a re-index migration script. Change embedding provider = plan a migration, always.
2. **FTS5 index drift is real.** Check `entity_embeddings` row count against entity count periodically; drift means writes bypassed the indexer.
3. **Scheduled extraction without a marker file double-processes.** `cron_marker.json` (last-run timestamp + capped session-ID ring) is load-bearing.
4. **Don't inject dreams into every turn.** Reflection output is for meta-analysis questions, not daily context — otherwise the agent starts citing its own dreams as facts.
5. **Schema verification before queries.** Our priority scorer initially read a column that didn't exist (`entity_id` vs `source_id`/`target_id`). `PRAGMA table_info` first, always.

## Known limitations (honest)

- Brute-force O(n) vector search — fine under ~100k entities, by design
- sqlite-vec unavailable on our host (extension loading disabled); would be the upgrade path
- Entity resolution is fuzzy+cosine, not a full dedup pipeline
- Reflection quality depends on the extraction model; garbage sessions produce shallow dreams

## Architecture index

| Component | Role |
|---|---|
| `braindb_core.py` | CRUD, hybrid search, graph ops, priority scoring |
| `braindb_tool.py` | Tool interface for the agent runtime |
| `braindb_cron.py` | Nightly session extraction (marker-tracked) |
| `braindb_extraction.py` | LLM observation extraction |
| `braindb_dreaming.py` | Reflection engine (the sleep cycle) |
| `braindb_decay.py` | Confidence decay + archival |
| `context_injector.py` | Cross-session context injection |
| `braindb_backup.py` | Backup/restore |

Full schema and design spec live in the private fleet repo; publishable on request.
