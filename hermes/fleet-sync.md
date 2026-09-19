# One skill tree, many machines — git-based fleet sync without the merge wars

Twelve agent profiles on the main host, a laptop peer, and occasional
disaster-recovery twins all need the same procedural knowledge (skills,
scripts, plugins). The naive design — bidirectional sync of a shared
directory — fails in ways that cost real incidents. This is the architecture
that replaced it. Companion to [fleet-operations.md](fleet-operations.md).

## The failure it replaces

v1/v2 synced skills bidirectionally between hosts. Two incidents ended that:

- **Cross-contamination:** the main host pushed Linux-specific skills over
  the laptop's carefully tuned local state. Per-host differences are *features*,
  not drift to be normalized.
- **Pull as a loaded gun:** bulk `pull` overwrites local edits wholesale —
  exactly the operation you reach for under time pressure, and exactly the
  one that destroys work.

## The architecture

```
git repo (private, per-fleet):
├── skill-catalog/      # ALL skills — pulled ON-DEMAND, never bulk
├── hosts/<name>/       # per-host backup: profiles, scripts, config
├── shared/             # fleet context docs, standards
├── vaults/             # narrative knowledge (fleet journals)
└── seed-latest.tar.gz  # bootstrap package for new hosts (releases)
```

Four rules carry all the weight:

1. **Push is backup, one-way.** Every host pushes its own subtree. Nobody's
   push can touch another host's state. The push script backs up first, then
   commits — a botched sync is recoverable from the previous commit.
2. **Skills are pull-on-demand.** `pull-skill <name>` installs one skill.
   There is no bulk pull except disaster recovery, which is confirm-gated.
3. **Per-host trees, no shared mutable state.** Hosts share the *catalog*;
   they never share a working directory. Cross-host contamination becomes
   structurally impossible rather than policed.
4. **Local knowledge stays local.** Memory, session history, and the agent's
   structured-fact store are per-host, never synced — synced identity is how
   you get two agents that both believe they're the same person.

## New hosts: seed packages, not clones

A new host starts from a tarball built from the reference host — skills,
plugins, BrainDB modules, council configs — with a one-script installer. No
git history of a machine that isn't this machine, no "clone and prune."

The lesson that refined it: seed *shape* depends on the host's *role*. A
disaster-recovery twin of the main host gets the full-profile seed. A laptop
meant as a lean mobile peer gets a **purpose-built kit** (one profile, a
curated skill subset, its own bot identity, a peer channel home) — seeding it
from the full-profile image produced a bloated, confused device. Match the
seed to the role, and build the kit explicitly rather than subtracting from
the twin.

## Agent-to-agent: message, don't share state

The peer relationship that works is **message-passing** (agent-to-agent
channels, async mailbox files as fallback), not shared mutable knowledge.
Two agents sharing one memory store converge on each other's mistakes;
two agents messaging each other keep separate beliefs and reconcile through
conversation — which is also auditable.

## Hygiene

- The push script is the only sanctioned writer; hand-commits to the repo
  drift the tree from what hosts actually run.
- Skills carry versions in frontmatter; a skill edited on the main host
  re-pushes and other hosts see the bump on next pull-skill.
- After any fleet-wide convention change (a new skill standard, a renamed
  script), grep the repo for the old strings — informal references survive
  file deletions, and stale mentions are how future sessions resurrect dead
  patterns.
