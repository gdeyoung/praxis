# Cron at fleet scale — 100 jobs, three transports, and the tombstone lesson

An agent fleet's real workload is not chats; it's **scheduled jobs** —
learners, watchdogs, digests, syncs, escalations. Ours runs ~100 enabled jobs
across three delivery transports (local files, bot DMs, phone push), and the
operating lessons are all about what the scheduler's *files* do and don't
mean. Companion to [agent-skill-patterns.md](agent-skill-patterns.md) and
[plugin-seam.md](plugin-seam.md).

## Ground truth: the jobs database, not the lock directory

The scheduler's working directory contains `.fire-*.lock` files — one per
fire, accumulating forever. They look like a backlog. **They are tombstones.**

Reading the scheduler's source settled it: the locks are flock fences, held
only while the firing process lives, **never unlinked by design**. Ninety-seven
lock files meant "ninety-seven fires have ever happened," not "ninety-seven
jobs are behind." The first version of our fleet-state plugin counted them as
a backlog signal and injected a false warning into every turn — until the
source read showed the files carry no liveness information at all.

**The rule that generalizes:** before building any monitor on a file's
existence, size, or count — read the code that writes it. Files are APIs
with undocumented semantics; the docs are the writer.

The real signal lives in the jobs database: an **enabled** job whose
`next_run_at` is hours in the past is a genuinely missed fire (scheduler
wedged, or the job failing to advance). That check, run per-turn by the
[plugin-seam](plugin-seam.md) fleet-state hook, has been silent for weeks on
a healthy fleet and caught real wedges within hours. Grace matters: one
grace period for timezone wobble, then flag.

## Three failure classes, three detectors

| Failure | Detector |
|---|---|
| Job wedged (scheduler didn't advance it) | `next_run_at` in the past beyond grace |
| Job runs but fails | per-job status in the output record; escalation digest |
| Job silently stopped (disabled, deleted) | enabled-count drift vs. the known baseline |

The lock directory detects none of these. Sweep the tombstones occasionally
(cosmetic), but never alert on them.

## Delivery transports, matched to attention

- **Local file only** — no notification wanted (watchdog probes, archive
  sweeps). Silent by design; failures surface via the missed-fire check.
- **Bot DM** — work that an agent profile should *see and act on* the next
  time it runs (digests into a profile's chat, escalation queues).
- **Phone push** — things a human must see same-day even if no agent session
  happens (spend anomalies, decision queues aging, hardware alerts).

The mistake is defaulting everything to phone push: attention is the scarce
resource; each job earns its transport. An agent-visible DM costs one line in
a bot chat. A push costs a human glance — spend those on what only a human
can decide.

## Retry and escalation

Failed fires retry on the scheduler's own backoff; a job failing *repeatedly*
(retries exhausted) goes to an escalation digest rather than push-per-failure
— one daily summary line beats a 3 a.m. storm of the same error. Watchdogs
that *watch other watchdogs* (a meta-watchdog confirming the digest job
itself fired) close the loop: the fleet-state missed-fire check covers the
scheduler, the escalation digest covers job-level failures, and the meta
check covers the digest.

## Scheduling around a shared model backend

A hundred jobs don't fire into a vacuum — most call an LLM, and the local
backends have finite slots (see [litellm-pitfalls.md](litellm-pitfalls.md)
for what happens when scheduled riders collide on a single-slot backend:
queue → timeout-kill → caller-retry → 5.6× token amplification). Audit the
job list for identical weekday+hour clusters and stagger them; book at the
schedule layer, because the router has no queue feature. The ambient
scheduled fleet also doubles as the canary for proxy changes — if all jobs
stay green after a config edit, the edit didn't hurt anything.

## Related

- [fleet-monitoring.md](fleet-monitoring.md) — the passive-monitoring doctrine and outage triage these jobs implement: death signatures, UPS forensics, alert discipline
- [litellm-pitfalls.md](litellm-pitfalls.md) — the collision/amplification failure modes behind the stagger rule
