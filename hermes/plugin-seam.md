# The plugin seam — small fail-open hooks instead of forking the agent

A three-plugin pattern for bending an agent runtime's behavior without
forking it: one live-state injector, one router-intent interceptor, one
command seatbelt. All share a contract that keeps the host safe: **fail-open,
ephemeral, kill-switchable, zero-output when healthy**. Companion to
[agent-skill-patterns.md](agent-skill-patterns.md).

## The contract (what makes a hook safe to run on every turn)

- **Fail-open.** Any exception inside the plugin returns nothing and logs one
  warning. A broken plugin must never break the agent. This is the difference
  between a customization and a liability.
- **Ephemeral injection.** Context is appended to the *current turn's user
  message at API-call time only* — never persisted to the session database,
  never added to the system prompt. Two payoffs: replayed history stays
  byte-identical, and the prompt-cache prefix survives.
- **Kill-switch by config.** Removing the plugin from `plugins.enabled` in a
  profile disables it without touching code. No plugin is ever load-bearing
  for correctness.
- **Silence is the success state.** Healthy system → hook returns nothing →
  zero tokens. If your hook injects "all clear" lines, it's a token tax with
  no information.

## Plugin 1: fleet-state (live context injection)

**Problem:** autonomous profiles make decisions without knowing fleet state —
a missed cron fire, a dependency nobody has verified in a month, an abnormal
process count. Telling them after the fact means they've already acted on
stale assumptions.

**Pattern:** a `pre_llm_call` hook reads three cheap local signals and injects
up to six lines, only when something is wrong:

| Signal | Source | Fires when |
|---|---|---|
| missed cron fires | the scheduler's own jobs file | an enabled job's `next_run_at` is >6h in the past |
| stale dependency-map nodes | the fleet's dependency map | `host`/`service`/`model-endpoint` nodes unverified >30 days |
| process count | `ps` | hermes processes >40 (an 18-bot fleet runs ~28 normally) |

All reads are local filesystem — no network, no SSH — ~27ms worst case,
sub-millisecond typically. First production catch, within two hours of
shipping: the stale-map signal fired on a browser-control service nobody had
verified in 31 days → verified healthy → map date bumped → signal cleared →
back to silence. That loop *is* the design: signal → verify → record → quiet.

**The lesson that shaped it — semantics of the data source, verified against
source:** the first version counted lock files in the scheduler directory as a
"backlog" signal. Reading the scheduler's code showed those files are flock
fences that are **never unlinked by design** — tombstones, not backlog. The
count said "97 jobs behind" while the jobs file said zero missed fires. Rule:
before building a signal on any file's existence, read the code that writes
it. (The 97 tombstones were deleted; harmless, but they'd have kept growing.)

**Who gets it:** ops-facing profiles only (default, sysadmin, ops hub). Content
specialists get nothing — fleet-ops signals are noise to a composer or a
writer. Per-profile enable, because each profile scans its own plugin
directory; a symlink to the shared install plus one config line.

## Plugin 2: cc-trigger (routing intent, before the chat starts)

**Problem:** some queries should bypass the single-model conversation entirely
and go to a heavier multi-council analysis — but only sometimes, and the
decision must happen *before* the conversation loop spends tokens.

**Pattern:** a `pre_chat` hook sees the raw user message first, returns a
structured verdict, and the host short-circuits into the specialized executor
when triggered. The hook decides *intent routing*; it never mutates the
message. This required a one-line host patch (registering the hook point) —
the subject of [core-patches.md](core-patches.md).

## Plugin 3: command-guard (a seatbelt, not a sandbox)

**Problem:** autonomous agents occasionally compose catastrophic shell
commands. You want a global denylist that blocks `rm -rf /`, `dd of=/dev/`,
force-pushes, and killing critical containers **before execution**, across
every agent harness on the machine.

**Pattern:** a `pre_tool_call` hook matches the command against a plain-text
POSIX-ERE file — one regex per line, editable live, no restarts. Regex
denylists are trivially bypassable (`python -c "shutil.rmtree('/')"`, base64
pipes); the doc says so explicitly: **this is a seatbelt against accidents,
not a sandbox against malice** — the second layer is the host's
LLM-assisted approval mode for flagged commands. Fail-open config governs the
missing-file case (allow) vs a lockdown mode (block).

The pattern list is adapted from an MIT-licensed community list
([davidondrej/skills](https://github.com/davidondrej/skills)) — see
[ATTRIBUTION.md](../ATTRIBUTION.md).

## Adding a signal or a plugin

1. Read the data source's code before trusting its shape (the tombstone rule).
2. One function per signal: healthy → return `None`; unhealthy → one line.
3. Config knob + manifest doc in the same change; version bump.
4. Test triple per signal: fires-when-true, silent-when-false,
   fail-open-on-garbage.
5. Verify through the **real plugin-manager path** (discover → load → invoke),
   not just a config read — then roll to one more profile, then the rest.
   Long-running gateways load plugins at startup only; restart them or wait.

The meta-pattern across all three: small surface, verified data-source
semantics, failure that fails open, and a kill switch. If a customization
can't say how it fails, it isn't ready to run on every turn.
