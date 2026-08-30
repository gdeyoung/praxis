# Wiring an external coding harness as a developer subagent

Most agent platforms either have a built-in coder or don't. We did neither: the fleet's orchestrating agent treats **an external CLI coding harness as just another callable worker** — the same delegation primitive used for research or QA tasks, but the worker happens to be a full dev environment. This is the wiring pattern, de-identified from a real deployment.

The harness in our fleet is [OpenCode](https://opencode.ai) driven over a local gateway; nothing here is specific to it — any harness with a CLI, headless mode, or a server API (Claude Code, Codex CLI, Gemini CLI, Aider, Continue) slots into the same socket.

## The socket: four requirements

1. **A callable interface.** A shell command that accepts a task and exits non-zero on failure. (Headless/print mode is ideal; PTY mode works but adds plumbing.)
2. **A working directory per task.** The harness must operate in a checkout it owns — same repo, different workspace — so its edits are diffable and its state can't leak into yours.
3. **Machine-readable results.** A diff, changed-file list, or JSON summary — not just prose. Prose-only harnesses get wrapped by a script that reconstructs a diff with `git status`.
4. **Exit status = truth.** The parent agent trusts exit codes and artifacts, never the harness's self-assessment.

## The wiring (what actually runs)

```
orchestrator (fleet agent)
   │  delegate_task(goal="implement X in repo Y", role=dev)
   ▼
worker session (own context, own terminal)
   │  writes task spec → invokes harness CLI in the repo checkout
   │  harness: plans, edits files, runs tests, iterates
   ▼
verification (parent-side, never the harness's own claim)
   │  git diff in the checkout
   │  test suite run by the PARENT, not the harness
   │  lint + typecheck + security scan
   ▼
integration: parent reviews the diff, then merges or rejects
```

Key property: **the harness never merges its own work.** It gets a checkout, it makes changes, and a separate authority (the parent agent, or a review council) decides what lands. The harness is hands; the parent is judgment.

## Model routing inside the harness

The harness gets its own model routing, and the rules differ from chat:

- **Planning mode gets the strong model.** Plan quality dominates outcome quality; this is the one place premium tokens always pay.
- **Default build mode gets the workhorse.** Routine edits, test fixes, refactors — a fast mid-tier model. Speed and cost matter more than sparkle here.
- **Quick lookups get the small model.** "What does this function do" should not cost frontier prices.

That three-tier split (strong-planner / workhorse-builder / cheap-querier) is the single highest-leverage cost/quality knob in the whole setup.

## What this buys over a built-in coder

- **Best-of-breed rotation.** When a better harness appears, you swap the command and keep the delegation protocol. No platform lock-in, no migration project.
- **Parallel checkout isolation.** Three dev workers = three checkouts of the same repo working simultaneously, no merge interference until the parent integrates.
- **The harness inherits your fleet's knowledge stores.** Because the worker wrapper is one of your agents, it can search your vault/index before coding, and write build lessons back after — the harness alone gives you neither.

## Failure modes we hit (so you don't have to)

- **Harness hangs waiting for input** → always run with a timeout and non-interactive flags; a harness blocked on a prompt is a stuck worker you can't see.
- **Sandbox escapes via the harness's own tool access** → the worker's toolset is scoped: no publishing, no package installs outside the sandbox, no secrets in env. The harness runs with exactly the permissions its task needs.
- **Self-reported success** → the classic. Test counts and diffs or it didn't happen; "all tests pass" from the entity that wrote the tests is a claim, not evidence.

## The minimal version

If you run one agent and one repo: a wrapper script that takes a goal, runs your harness headless in a temp worktree, prints the diff, and exits with the harness's code. That's 20 lines — and it's the same architecture as ours, minus the fleet. Start there.
