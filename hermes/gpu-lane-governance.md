# GPU lane governance — leases, reapers, and the end of anonymous VRAM

Sixteen-plus autonomous agent profiles share two swap GPUs with zero shared
context. Without governance, the failure mode is inevitable: an anonymous
container holds 20 GB of VRAM for half an hour with no owner, while a video
render waits. That incident (a music model squatting on the video GPU, no
owner to call, no policy to invoke) is why this system exists. It was designed
in council, then shipped with a regression suite.

## The design in one table

Three scripts, all on the GPU host, one hard rule: **on-demand GPU containers
start only through `gpu-take`**. Anything else is an unclaimed bypass.

| Component | Role |
|---|---|
| `gpu-take` | atomic per-lane check-and-start under `flock` — claim a container with `--owner profile:task --ttl N` |
| `gpu-reaper` | 5-min cron: TTL expiry, session deadlines, stopping bypassed containers |
| `gpu-status` | one line per GPU: occupancy, claims, sessions, VRAM |

Claims and session state live on tmpfs — wiped at boot, *correctly*: a claim
that survives a reboot would be a lease on hardware that no longer owes
anything. The scripts themselves live on a flash partition that can't hold
exec bits (vfat); a boot hook copies them into `/usr/local/bin` on every
start. An append-only log records every take, release, and eviction.

## Lanes

Two GPUs, two lanes: lane 0 (image/music/writer workloads compete), lane 1
(video only). One on-demand workload per lane at a time. Contention is
*lateral* — music vs. writer on lane 0 — which keeps eviction decisions small
and local instead of global.

## The lease protocol

```bash
# simple claim: 60-minute lease, owned
gpu-take music-model --owner composer:track-x --ttl 60

# multi-step pipeline: the lane is RESERVED across model swaps
gpu-take writer --owner composer:song-1 --ttl 30 --session song-1 --gap 120
gpu-take writer --step --session song-1 --owner composer:song-1   # BEFORE each swap
gpu-take music-model --owner composer:song-1 --ttl 20 --session song-1

# release (pipelines: clear the reservation too)
gpu-take --release music-model --session song-1
```

The design decisions that came out of review (each rejected alternative is a
lesson):

- **Mandatory `--owner profile:task`.** Anonymous GPU use is the original
  sin — without an owner there is no one to page and no arbitration context.
  *Rejected: an owner allowlist* — the fleet grows profiles faster than
  allowlists update.
- **TTLs are honest or you get reaped.** Bounds [5, 480] minutes; overrun =
  reaped = retry with a longer TTL. *Rejected: TTL extension/grace* — every
  grace mechanism becomes a permanent loan.
- **Sessions, not queues, for pipelines.** A session reservation file holds
  the lane across model swaps with a `--gap` (max 10 min) between steps;
  caller discipline orchestrates cross-lane choreography. *Rejected: FIFO
  queueing* — queues serialize workloads that don't actually conflict, and a
  queue is a scheduler, which is a new SPOF.
- **Eviction is immediate for squatters.** A claim arriving at a lane with an
  unclaimed bypass or an expired claim stops it *now*, not at the next reaper
  cycle. Same-container re-take heals instead of evicting (the common "I
  forgot to claim" case self-repairs).
- **A stuck `gpu-take` can't wedge a lane** — the flock wait is capped at 60s.

## The regression gate

After **any** edit to these scripts: `gpu-selftest`, ~60 seconds, 14 checks —
owner rejection, TTL bounds, claim/BUSY, session step semantics, release,
bypass eviction, reaper expiry, clean state. 14/14 or the edit doesn't count
as done. Governance scripts are exactly the kind of code that "works" until
the edge case costs a night of renders; the self-test is cheaper than the
incident.

## Adding a governed container

1. Create it with its device assignment matching the lane.
2. Add its name to the lane lookup in `gpu-take` and the on-demand lists in
   the reaper and status scripts (both the flash source and installed copies).
3. Prove it: `gpu-take <name> --owner sysadmin:verify --ttl 15`, then watch
   the reaper expire it.

## Numbers from the incident that started it

25 minutes of anonymous 20 GB occupancy, one threatened render queue, zero
way to identify the owner — the container name was the only signal, and it
named a *model*, not a task. With governance, the same event is: lane BUSY,
owner on the claim file, TTL counting down, arbitration a DM away. The system
has run since without a recurrence.
