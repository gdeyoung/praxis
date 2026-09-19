# Core patches without a fork — five files, upstreamable, zero maintenance debt

Every agent runtime eventually needs one behavior it doesn't have. The fork is
the trap: a forked runtime carries a merge debt that compounds with every
upstream release. The alternative: a **patch series of five files, kept as
uncommitted working-tree diffs against the vendored upstream**, each one small,
upstreamable, and self-documenting. When a new release lands, `git stash` →
update → `git stash pop` → resolve at most five small conflicts. Companion to
[plugin-seam.md](plugin-seam.md) (the hook system that makes most patches
unnecessary).

## The rules that make it survivable

1. **Patch only what a plugin cannot do.** Our plugin seam handles injection,
   interception, and guarding. Only two of the five patches *add* a hook
   point; the rest are bug fixes or hardening. Before patching, ask whether a
   hook would do.
2. **Every patch carries its date and rationale in a comment.** Six months
   later, "why is this here" must be answerable from the diff alone.
3. **Each patch is independently revertible.** No patch depends on another.
   Drop one, the other four still apply.
4. **Every patch is an upstream-issue candidate.** If it isn't general enough
   to propose upstream, it's probably a local workaround that deserves a
   comment saying so — and a plan to delete it.

## The five

### 1. Web-search failover: success-with-zero-results is a failure

**The incident:** a meta-search backend (SearXNG) returned `success: true` with
an empty results array — for *days*. Every upstream engine was
CAPTCHA-suspended; the healthz was green; queries "succeeded." Agents received
empty result pages and concluded the information didn't exist.

**The patch** (`web_tools.py`, ~44 lines): after any provider returns, check
for success-with-zero-results; on failure or emptiness, roll over to the next
*available* provider in a deterministic quality order, logging the hop.
Failover on emptiness, not just on errors — because the most dangerous
failure mode of a search backend is the silent one.

### 2. Context-length probing: don't hit admin-only routes on proxies

The runtime probes `GET /v1/models/{model}` to learn each model's context
window. On OpenAI-compatible *proxies* that route collides with an
admin-only model-info endpoint: every probe logs a 401 plus a full auth
traceback in the proxy's log — noise at both ends, on every model, on every
session start.

**The patch** (`model_metadata.py`): probe that path only when the server was
positively identified as LM Studio / vLLM / llama.cpp. Proxies get their
context from the payload path they actually implement. Also preserves the
canary comment: never read `max_tokens` (output cap) as a context *window* —
that collapses a 1M-context model to its output limit and poisons the cache.

### 3. Hook point: `pre_chat` (intent routing before the conversation)

The plugin system had `pre_llm_call` / `post_llm_call` but nothing *before*
the conversation loop starts. Intent routing ("this query should go to the
multi-council executor instead of a chat") needs the raw user message before
tokens are spent.

**The patch** (`plugins.py` + `conversation_loop.py`, one line + 19 lines):
register `pre_chat` as a valid hook; in the loop, invoke it before per-turn
setup; a structured verdict short-circuits into the specialized executor.
The [cc-trigger plugin](plugin-seam.md) is its only consumer — the patch
exists to make the behavior pluggable rather than hardcoded.

### 4. MCP shutdown: GeneratorExit must propagate

During interpreter shutdown, an MCP server task's `finally` block swallowed
`GeneratorExit` (a `BaseException`, invisible to `except Exception`) while
cancelling child tasks on a closing event loop — producing a spew of
"Task was destroyed but it is pending" warnings on every exit.

**The patch** (`mcp_tool.py`, ~13 lines): let GeneratorExit propagate
(`raise`), guard the task cancels against a closed loop, and await them
catching `CancelledError | GeneratorExit`. Clean shutdowns, no warnings.

### 5. (And the one that got away with being a plugin)

Worth stating: the fifth behavior change we needed — live fleet-state
injection on every turn — required **zero core patches**. The existing
`pre_llm_call` hook was enough. The pattern holds: patch the runtime only
when no hook seam exists; add the seam as a patch; build the behavior as a
plugin on the seam. See [plugin-seam.md](plugin-seam.md).

## Why not fork / why not PR everything today

Upstream PRs are the endgame (the web-search failover and the GeneratorExit
fix are strong candidates — the field-report pattern applies), but the
working-tree patch series is the *holding pattern* that keeps us current with
upstream releases at the cost of five stash-pops. The failure mode it
prevents: a fork that works for three months, misses four releases, and
becomes unmigratable exactly when a security fix lands.

House hygiene: the series should also exist as a saved patch file
(`git diff > patches/series.patch`) committed somewhere durable, so a careless
`git clean` can't eat it. Ours doesn't yet — noted in the fleet's own notes,
fixed before this page's method claim is fully honest.
