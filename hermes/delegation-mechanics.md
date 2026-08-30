# Delegation mechanics — how a parent agent supervises workers

The architecture diagrams say "spawn subagents." This is what that actually means operationally: bounded parallelism, live transcripts you can tail, worker templates as context blocks, and multi-role execution from declarative definitions.

## The primitives

1. **Bounded parallelism.** A small fixed concurrency (we run 3) per parent. More workers than that and the parent spends its turns context-switching instead of judging results; fewer and you lose the parallelism you spawned for. The number is a dial, not a dogma — but it's always bounded.
2. **Append-only live transcripts.** Every worker streams its assistant text, tool calls, and tool results to a log file under a per-task directory. The parent (or the human) can `tail -f` any worker mid-run. This single design decision converts "black box that will message me later" into "observable process I can audit live."
3. **Done-markers in band.** Workers signal completion with a literal terminal marker string (ours: `final |`) written to the transcript. The poller greps for the marker; when seen, the result is complete. Simple, grep-able, no bespoke protocol.
4. **Workers are leaf-scoped.** By default a worker cannot spawn its own workers or ask the human questions. It either does the work or returns "blocked, here's why." Nesting exists but is opt-in per design; unbounded recursive spawning is how fleets eat themselves.
4b. **Isolation by default.** Each worker gets its own conversation, working directory, and toolset. The only channel back is the final summary. Intermediate tool output never floods the parent's context — that's the entire point of delegating.
5. **Templates as context blocks.** Worker types are defined once (purpose, models, tools, scope-in/scope-out, standards, reporting format) as short text blocks. A parent spawning a worker passes the block as the task context. Adding a worker type = writing one block, not wiring a new subsystem. (See [agents/ROLE-TEMPLATE.md](../agents/ROLE-TEMPLATE.md) for the schema.)

## The supervision loop

```
parent ──▶ dispatch(goal, context, worker-type)
              │
              ├─ keep working (delegation returns immediately)
              ▼
        worker streams ──▶ live/<id>/transcript.log   (tail-able, append-only)
              │
              ├─ done-marker seen ──▶ parent reads final summary
              │                         │
              │                         ├─ verify claims with a handle (URL,
              │                         │   path, exit code) before acting on them
              │                         └─ integrate; dispatch follow-ups if needed
              ▼
        timeout / silent worker ──▶ kill + rescope + redispatch, never blind-wait
```

**Verify-then-trust on return.** Worker summaries are self-reports. For anything with an external side effect — an upload, a publish, a file written at a shared path — the parent requires a handle (URL, ID, absolute path) and checks it before telling the human "done." A worker that says "deployed successfully" without a verifiable artifact gets treated as not-done.

## Multi-role execution from YAML (councils)

For tasks that need deliberate disagreement — reviews, evaluations, design calls — define the roles declaratively instead of free-styling them per task:

```yaml
council: code-review
rounds: 2
members:
  - role: architect     # judges structure, naming, coupling
  - role: security      # threat-models the diff
  - role: qa            # hunts edge cases, writes the failure list
synthesis: weighted-merge   # how member outputs combine
```

The executor loads the YAML, runs members (sequentially or in parallel), for additional rounds feeds member outputs to each other, and merges per the synthesis rule. Roles are reusable across councils; a council is data, not code. The win: you version and diff your review process like any other artifact.

## When *not* to delegate

- **Mechanical multi-step work with no judgment** — a single script does it cheaper and verifiably.
- **Anything needing user interaction** — workers can't ask questions; you'll rediscover the requirement mid-task.
- **Work that must outlive the session** — background delegation dies with the parent. Durable work goes to the scheduler (cron), not a subagent.

These three exceptions catch most bad delegations before they're spawned.
