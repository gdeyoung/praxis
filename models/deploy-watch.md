# Deploy-watch — bounded verification for model swaps and service rolls

"Restart and pray" is the default deployment method for self-hosted inference. This is the replacement: a small state machine that babysits a change through verification and reports the outcome to chat, then cleans itself up.

## The shape

```
you: flip the change (one variable — see the gate below)
      │
      ▼
deploy-watch starts ──▶ polls on an interval with a HARD BUDGET
      │                     (e.g. every 30s, max 20 min, then declare failed)
      ├─ readiness probe passes ──▶ run the verification suite
      │        ├─ suite green ──▶ write marker + report success + exit
      │        └─ suite red  ──▶ report failure + evidence + exit
      └─ budget exhausted ──▶ report timeout + what the logs said + exit
```

Everything the watcher does is: **bounded poll → verify → report → self-clean.** No daemon that outlives the task, no unbounded loops, no state that persists past the outcome.

## The three components

1. **State file** (one line of JSON): what's being watched, since when, last status. Humans can `cat` it; the agent can too. If the watcher dies, the state file tells the next session what was in flight.
2. **Marker files** for outcomes: `.deploy-ok`, `.deploy-failed`, `.deploy-timeout` in a scratch dir. Crude, grep-able, and immune to the "did that job finish?" ambiguity that plagues log-parsing.
3. **A scheduled poller** (cron, every minute) that checks in-flight state files, advances them through the state machine, and delivers the final report to the chat surface where the human actually is. When nothing is in flight, the poller exits silently — it must be a no-op on idle, or you'll train yourself to ignore it.

## The pre-flight gate (before the watch even starts)

The watcher verifies *behavior*, not liveness — so the change itself must be pre-gated:

- **Dependency impact check** — nothing downstream depends on the thing you're about to break (our fleet: the dependency map; minimum viable version: `grep -r` for the endpoint/name across configs).
- **One variable per change.** Model swap ≠ also-new-config ≠ also-new-driver. If two things changed, the watcher's evidence is uninterpretable.
- **Rollback is config-only.** `MODE=old bash serve.sh`, or a symlink flip. If rollback is a rebuild, you didn't design the change, you designed an outage.

## Why the report goes to chat (not a log)

The outcome message — with the verification numbers inline — lands where the human already lives. "Deploy OK: 33.3 tok/s no-think, 31.9 thinking, tool-call PASS, prefix-cache HIT, round-trip through router PASS" is a complete decision record in two lines. The log has more; the message has *what it means*.

This closes the loop the blue-green pattern opens: blue-green gives you reversibility, deploy-watch gives you **the verdict** — bounded in time, evidence-attached, delivered. A swap isn't "done" when the container starts; it's done when the watch reports green.

## Failure classes this catches

| Failure | Without deploy-watch | With |
|---|---|---|
| Cold boot slower than expected | Impatient manual restarts break it worse | Timeout budget absorbs it; report notes actual boot time |
| Serves but degraded (bad quant, wrong ctx) | "It's up" = declared done | Verification suite fails → flagged with evidence |
| Crash-loop | Discovered hours later by a user | Poller sees readiness never stabilize → alert |
| Watcher itself dies | N/A | State file + marker files reveal the gap next session |

## The minimal version

A `while` loop with a deadline, a curl, and a `notify` function is 15 lines of bash and captures 80% of the value. The remaining 20% — marker files, self-cleaning cron integration, evidence collection — you add after the first time a silent partial deploy costs you an evening.
