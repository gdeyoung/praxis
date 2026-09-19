# LAN services as agent tools — two bridge patterns, one decision rule

Every service on the LAN wants to be an agent tool. Two patterns cover both
directions of the mismatch, and the failure mode to avoid is bridging the one
that doesn't need it. Companion to [fleet-operations.md](fleet-operations.md).

## Pattern A: wrap the HTTP service (the service has no MCP)

A LAN REST API — a knowledge gateway, a media server, a ComfyUI instance —
becomes an agent tool with **one Python file**: stdlib only (`urllib`, `json`),
stdio transport, credentials in env vars.

Why stdio and not an HTTP server per tool: no ports to manage, no containers,
no new network surface, no health checks. The agent host spawns the process;
the process talks HTTP to the service on localhost-or-LAN; the agent never
sees a URL or key. Five tools is the practical ceiling for one wrapper —
search, get, save, delete, health covers most REST APIs without becoming a
second API to document.

The generic recipe (works for any LAN REST API):

1. List the endpoints worth exposing (resist "all of them" — agents do better
   with five verbs than fifty).
2. One file, one function per endpoint, JSON in/out, errors as structured
   text the model can read.
3. Env vars for URL + key. Never inline; never in the tool description.
4. Register in each agent harness's config as a stdio command.
5. `--test` flag that exercises every tool without an agent in the loop —
   the bridge ships testable or it doesn't ship.

## Pattern B: bridge the stdio server (the MCP speaks stdio, the host flakes)

The opposite direction: the tool *is* an MCP server, but the agent host's
stdio transport spawns it fresh per session — and some servers don't survive
that. Symptoms: "MCP event loop is not running," "unreachable after 8
consecutive failures" on new sessions while existing sessions work.

**The fix** is a long-lived process behind a streamable-HTTP bridge (e.g.
supergateway) under systemd: the MCP server starts once, the agent host
connects over HTTP, cold-start races disappear.

## The decision rule: probe before you bridge

The expensive mistake is migrating *healthy* stdio servers because one broke.
The failure mode is real but **not universal** — in our audit, exactly one of
a dozen stdio servers actually failed cold-start; the rest initialized in
under 1.5s across three spawns.

Probe every stdio MCP before recommending migration: spawn each 3 times, run
a tool call on each, record init/call timings and errors. Then categorize:

| Probe result | Action |
|---|---|
| 3/3 cold starts, fast | leave alone |
| event-loop / unreachable failures | migrate to HTTP bridge |
| call fails with an HTTP 401 | **not a transport bug** — rotate the key |
| works via deprecated package alias | update the package reference |

The probe surfaces three distinct problem classes at once — transport
failures, auth failures wearing transport costumes, and package drift — and
each has a different fix. A 401 is not a transport bug; a deprecation warning
is not a transport bug. Migrate only what the probe convicts.

This probe-then-recommend loop is the general pattern for any "should I
migrate/rotate/refactor" question with non-trivial cost: measure the actual
population before changing it. One flaky instance is a bug report, not a
fleet-wide mandate.
