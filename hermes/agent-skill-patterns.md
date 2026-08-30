# Agent skill patterns that survived production

Skill patterns from a self-hosted agent fleet — each one earns its place by being used daily for months, not by being clever. Companion to [fleet-operations.md](fleet-operations.md).

## 1. The decision queue (async human-in-the-loop)

**Problem:** Autonomous agent work hits decision points (publish this? delete that? spend money?) and either stalls or guesses.

**Pattern:** The agent never blocks. It completes everything it can, then files each pending decision into a queue message:

```
DECISION NEEDED [queue-id]
  What: publish the benchmark post to the vendor forum
  Draft: <the actual draft, inline>
  Impact: public, attributable, reversible-within-24h
Reply APPROVE <id> / REJECT <id> / DECIDE <id> <instruction>
```

The human replies with the command from any surface (chat, email reply, Telegram). The agent parses reply-commands on the next turn and executes.

**Why it works:** the human's cost per decision drops to one tap; the agent's autonomy never violates the "show me the draft first" rule for irreversible actions. Our rule set: anything public-facing, destructive, or spend-approving goes through the queue; everything else proceeds with labeled assumptions.

## 2. The knowledge preamble

**Problem:** Long-running agent work loses the thread between sessions; new sessions re-derive context expensively or wrong.

**Pattern:** Every substantive task starts with a ≤3-line preamble the agent composes before acting:

```
Known: <verified facts relevant to the task>
Changed since last: <what moved>
Blocked: <what's stuck and why>
```

It's cheap (3 lines), forces a read-before-write pass, and surfaces stale assumptions *before* they contaminate the work. The discipline is the length cap — prelists that grow become reports nobody reads.

## 3. Blue-green runtime upgrades for the agent itself

**Problem:** upgrading the agent runtime (framework, model routing, config schema) risks bricking the only thing that runs your automation — including the automation that would fix it.

**Pattern:** staging profile clone. The agent runtime installs live in side-by-side directories; a staging clone gets the upgrade first, a smoke suite (tool calls, cron fire, memory load, one full agent turn) runs against it, and only a green suite promotes the clone to primary — by symlink flip, with the old runtime untouched for instant rollback. Production upgrade happens in one atomic rename, never in place.

**Corollary:** hold upgrades on a staging-green-but-unpromoted state indefinitely when a release has a known regression. "Green on staging" is a necessary condition, not a schedule.

## 4. Structured handoff (compaction with loss markers)

**Problem:** context windows compact mid-task and the summary quietly drops load-bearing facts.

**Pattern:** when compacting a session, the handoff note carries: active state (files, processes, endpoints touched), blocked items with the exact error text, verification steps already passed, and — critically — a "do not resume stale work" clause naming the tasks that were superseded. The compacted summary is treated as *reference*, not instruction; the newest human message always wins.

## 5. The edit-in-place / restore-ladder rule for shared files

**Problem:** scripted edits to shared config/docs truncate files when the script fails between open and write.

**Pattern:** three layers —
1. Build the new content fully, sanity-gate it (non-empty, expected size), then write. Never stream-transform into the destination.
2. Prefer fuzzy patch tools over hand-rolled replace scripts.
3. When truncation happens anyway: restore ladder = fleet-synced backup copy → session-context snapshot → git. Reconstruct from backup + re-apply verified diffs; **never retype from memory** (transcription drift is guaranteed and subtle).

## 6. Escalation as a hard rule, not a mood

**Problem:** agents retry failing paths, burning hours and sometimes making things worse.

**Pattern:** two identical failures with the same error = mandatory stop. The agent must then output: what's known, what was tried, the exact error, and one precise question for the human. Retrying a third time is a rule violation, not persistence. The counter resets only on *new information* (different error, changed environment).

## 7. Curator separation for learned knowledge

**Problem:** autonomous learners that can write to the skill store produce hundreds of malformed-edit rejections and occasionally corrupt procedural knowledge.

**Pattern:** separate the researcher from the curator. Learners and research crons write findings to free-form stores (vault notes, bookmarks, a review queue). A single background curator — with schema validation and a review gate — is the only writer allowed into the procedural skill store. Rejection counts get monitored; a spike means a cron is misconfigured.

---

Each pattern exists because its absence cost us something real: a zeroed config file, a bricked runtime, forty minutes of retry-spam, a draft published unreviewed. That's the admission price for this list.
