# The recipe doctor — drift auditing a repo-managed machine

> The repo is the machine: `install.sh` can rebuild the box from nothing, and an
> inventory file (RECIPE.md) lists every deliberate non-stock change. That
> discipline has one enemy — drift. You fix something at 11pm directly on the
> box, the fix works, you never write it down. Six weeks later an update
> clobbers it and nobody remembers what it was. The doctor closes that loop.

Companion to [fleet-operations.md](fleet-operations.md). ~130 lines of bash, no
dependencies beyond coreutils + `git`. Runs from `/usr/local/bin` (immune to
package updates), source-of-truth in the recipe repo, installed by the same
root helper that installs everything else. Never `curl | bash`.

## The pattern

One script walks the inventory **section by section** — every check maps to a
named section of the recipe, so any drift line it prints is a decision, not a
mystery:

| Check | Compares | Against |
|---|---|---|
| packages | installed? | recipe's package list |
| services | enabled/active | recipe's service table |
| plugin pins | installed commit | pinned short-SHA per third-party plugin |
| configs | live config files | repo snapshots (`diff -q`) |
| widget sources | present + enabled | our namespaced widget list |

Exit 0 clean, exit 1 drift, exit 2 fatal (recipe repo missing). Each drift
line means one of exactly two things: **fix the machine** (something broke) or
**fix the repo** (the machine legitimately evolved and the inventory didn't).
There is no third option, and that's the point.

## The gate that makes it stick

A drift auditor that runs only when someone remembers is a quality gate nobody
opens. But daily *notifications* about the same drift is how you train yourself
to ignore alarms. The fix: **notify only when the drift set changes.**

- systemd **user** timer, daily, `Persistent=true` (a laptop that was asleep
  catches up on boot), `RandomizedDelaySec=10m`.
- The timer wraps the doctor with a small `doctor-notify` script: run doctor →
  collect drift/warn lines → SHA-256 them → compare to last run's hash in
  `~/.local/state/<doctor>/last-drift` → notify (or stay silent) → append a
  one-line journal to `history.log`:

  ```
  2026-09-23 16:42 rc=0 sig=e3b0c4...b7852b855 == 34 ok / 0 drift / 0 warn — exit 0 ==
  2026-09-23 16:42 rc=1 sig=a27bff...15b7e6f0488 == 33 ok / 1 drift / 0 warn — exit 1 ==
  ```

  Same drift tomorrow as today → hash matches → silence. New drift, or drift
  that healed → one desktop notification. The journal gives you a timeline of
  the machine's honesty.

## It paid for itself on day one

- First manual run caught **three stale config snapshots**: the live Hyprland
  configs had evolved over four days of tuning (a monitor-layout generator, a
  widget's settings) without the repo snapshots being refreshed. Classic
  recipe rot, invisible until a rebuild.
- Within 20 minutes of the timer going live it caught a **third-party plugin
  vanishing from disk** — no package transaction, no shell history, dir simply
  gone. The doctor noticed and notified before any human would have. (Cause
  under investigation; the detection is the point.)

## Pitfalls (each one bit during bring-up)

- **Empty-input SHA.** `sha256sum` on empty input is
  `e3b0c442...` — a valid hash meaning *zero drift*, not a failure. Don't
  special-case it into an error path; it's your clean-state signature.
- **Pin comparison must be prefix-aware.** Recipe stores 7-char short SHAs,
  `git rev-parse` returns them too — but compare `full.startswith(short)`, not
  string equality, or a longer form silently fails every check.
- **Check the checker.** The first draft had a hand-typed pin list with a
  transposed-digit typo, which "proved" a working pin was drift. Pins come
  from the recipe file, one source of truth, never retyped into the checker.
- **Drift the doctor itself creates** (its own state files, a theme dir it
  generates on first run) must be exempted or it will report itself forever.
- **Keep state out of the repo.** `last-drift` and `history.log` live in
  `~/.local/state/`; committing them turns a machine-history journal into
  merge conflicts.

## Adopting it

Any host you manage as repo-plus-install-script already has the inventory —
the doctor is just the inventory turned executable. Write the checks per
section as you add sections; the useful order is packages → services → pins →
configs, because that's the order a rebuild touches them.
