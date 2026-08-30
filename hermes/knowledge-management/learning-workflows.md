# Autonomous learning workflows — the night shift

Two learner agents run unattended on a fixed daily cycle: one studies the **fleet domain** (self-hosted AI infrastructure — ~75 cycles), the other the **work domain** (a sales engineer's accounts, market, and competitors — ~59 cycles). Nobody prompts them. Every morning there's a digest of what was learned, what was verified, and what needs a human decision.

We've never seen this pattern published. Most "autonomous agent" demos are single-session chat loops; this is a scheduled researcher with source-verification rules, tiered persistence, and its own health monitoring, running daily for months.

## The cycle (fixed, 4 units, same every day)

```
06:00 ─▶ 1. SCAN     curated sources: watch lists, feeds, repos, docs
        2. STUDY    pick the highest-value units, research properly
        3. VERIFY   every claim gets a source; unverifiable → dropped
        4. PERSIST  tier-ranked writes (below) + action queue + digest
```

The unit count is deliberately small. Four verified units beat twenty skims — early experiments with more units produced exactly the degradation you'd expect: shallow reads, hallucinated summaries, unverified claims. Fixed scope forces selection, and selection is where the quality comes from.

## The tier system (what a finding earns)

Every unit's insights are ranked before persistence:

| Track | Meaning | Destination |
|---|---|---|
| 1–5 | Useful, routine knowledge | Search index (queryable, not pushed at anyone) |
| 6 | Durable insight — changes future decisions | Vault (narrative note, human-reviewable, semantic-search indexed) |

Plus an **action queue**: anything needing a human decision (a monitored event that matured, a proposal worth approving, a defect found) goes to the decision queue with the evidence attached. Learning that never reaches a decision is trivia.

## Watch lists — the compounding trick

The highest-value pattern: **persistent watches on things that usually don't change.** A unit re-examines a tracked item each cycle (a dependency's release feed, a regulatory bill, a competitor's event schedule) and files "no change" or the delta. Examples from real cycles:

- A vendor acquisition tracked from rumor → confirmation → close-date estimate, feeding a "how long is the window uncontested" analysis
- A model ecosystem watched until a needed feature (upstream framework support for a specific architecture) actually merged
- A legislative tracker that caught the official site being restored after an outage, making a previously-unverifiable compliance mechanism citable

Watches turn the learner from a news-reader into an **institutional memory with trend detection**. Single-cycle agents can't do this; the value is in the delta across weeks.

## The learners audit themselves

One unit per cycle is routinely spent on **self-examination**: the gap-scanner audits its own tooling and proposes fixes. Real catches: three defects in its own source-scanner (false-positive patterns, title-join misses), an index-drift repair, entity-hygiene in its own memory. An autonomous system that never inspects itself degrades silently; scheduling the self-audit makes the degradation loud.

## Rules that make it trustworthy

1. **Source or it didn't happen.** Every claim in a digest carries a verifiable source. Terminology must be grounded (no invented product/version names — verify the exact string against the source). Unverifiable → dropped, not softened.
2. **Track counts, not vibes.** Each digest reports how many units landed in which tier. Trends over weeks expose degradation long before the prose quality does.
3. **A complaint repeated across N consecutive cycles is a bug report, not weather.** Four cycles flagging the same search-tier garbage became an escalated defect with evidence attached.
4. **Learners never write skills.** Findings go to vault/index/queue; only the curator touches procedural knowledge (see [agent-skill-patterns.md](../agent-skill-patterns.md) §7). Before we split this, learners generated ~100+ malformed-edit rejections per day.
5. **Health monitoring is separate.** An independent daily job checks both learners ran, parses their output markers, and alerts on missing/short cycles. The watcher is not watched by the watched.

## What the morning looks like

A digest lands: four units, tier placement per insight, one or two queued decisions with evidence, occasionally a watch-maturity alert that's been compounding for weeks. Reading it costs two minutes. The decisions are pre-drafted and one-reply executable (`APPROVE`/`REJECT`/`DECIDE <instruction>`).

That's the whole interface between an autonomous research organization and a human with a day job.
