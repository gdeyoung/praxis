# Monitoring an agent fleet — passive checks, death signatures, alert discipline

How to watch ~a dozen self-hosted hosts running an agent platform without waking an LLM 96 times a night, and how to read the evidence when a box dies. Everything here ran in production across multiple real outages — including the ones our own monitoring caused.

The schematic: a **poller + watchdog + digest** set of scheduled jobs on a dedicated ops profile, a JSON state file (`status`, `down_since` epochs, `last_alert` per service), alert delivery to a messaging platform, and a central syslog/metrics store that receives telemetry from every host. The monitoring layer is deliberately dumb and cheap — the intelligence lives in the *triage procedure*, not the monitors.

A complementary layer audits the agent platform itself (sessions age, cron metadata failures, log stalls) rather than hosts — for that we vendor and pin [AtlasOmnia/hermes-loops](https://github.com/AtlasOmnia/hermes-loops) (MIT) with one local patch carried as a diff, and resolve its anonymized job labels against the jobs DB so failures have names.

## Triage procedure (in order)

1. **Probe the host directly** — ping plus a TCP check of its known service ports. This classifies the outage before anything else:
   - ICMP unreachable + all ports filtered → **host-level** (power off, hard hang, NIC down)
   - Ping OK, port closed → **service-level** (host up, container/process dead)
2. **Ask for the physical state EARLY.** Fans spinning? LEDs? Anything on the console? One answer reorders the whole diagnosis: still powered + dark/unresponsive = hard *hang* (RAM, GPU/PCIe wedge, VRM — not a power drop); fully off = power-path failure; frozen text on console = kernel panic → **photograph it before power-cycling** — it's the only pre-crash kernel evidence that survives for free. (We once misdiagnosed a hard hang as a PSU power-drop because physical state wasn't established until after the verdict.)
3. **Read the poller state** for the affected host; convert `down_since` epochs to local time. That's the *monitored* drop time.
4. **Scan monitor outputs backward** for the last-healthy → first-fail transition. Absence of the host name in a poll's output = healthy at that poll.
5. **Decode the error signature at the transition:**
   - `urlopen error timed out` → host was hanging (NIC up, not answering) — kernel wedge, near-death
   - `No route to host` → host fully off the network — power off, thermal trip, PSU, or completed hang
   - `Connection refused` → host UP, the service process died — SSH in and read container/system logs
   
   A timeout → no-route progression across consecutive polls = the hang → drop sequence (host-level, hardware/OS).
6. **Check alert delivery.** `ALERT FAILED ... HTTP Error 400` in the same outputs means the notification died (bad chat ID, malformed message formatting). Monitoring worked; the human was never told — usually why they're asking instead of already knowing.
7. **Cross-reference recent work** on that host. A box BIOS-fixed the same morning going dark again at night is a recurring hardware issue, not software.
8. **Root-cause from the metrics store — it works even when the box never comes back clean.** Linux keeps much of its log state in RAM; a hard crash wipes the on-box evidence. But if every host ships 10-second metric samples to a central store, you can pull the last hour before the drop and read the death signature (next section).
9. **Host-level down = physical check needed.** You cannot read logs on a dark box. Once it boots, pull the journal and container state to confirm root cause before declaring it fixed.

## Death signatures (metrics forensics)

Reading a `date_histogram` aggregation (30-minute buckets over the full day) over the metrics store:

| Signature | Verdict |
|---|---|
| Flat/idle values → instant cessation mid-sample | **Hardware** (power/PSU/board halt). Software cannot do this. |
| Ramp before the drop (memory climbing, load spiking, temps) | **Software/OOM/thermal** — chase the ramping process |
| Metrics stop, host still powered (fans on) | **Hang** — marginal RAM idle-lock, GPU/PCIe wedge, VRM/board caps; PSU demoted |
| Metrics stop, host fully off | **Power path** — see below |
| Only one host gaps in the window | Failure local to that box (PSU, cable/strip, board) — *if* every host is UPS-protected; an unprotected host gaps alone on a genuine house blip shorter than UPS transfer time |
| Multiple hosts gap together | **House/mains event** — escalate to the power path |

Gaps between histogram buckets = down periods; count them for reboots.

Gotchas that cost us wrong conclusions:

- **Syslog datastreams roll at UTC midnight.** A crash near 18:00 US-Central sits in the *next day's* index (00:00Z). List the rollover indices before concluding "no logs after time X."
- **Log inputs often do NOT resume after agent/container restarts while metrics keep flowing.** Absence of syslog ≠ absence of telemetry — check the metrics datastreams too.
- **A single failed poll ≠ outage.** The poller itself can blip; wait for a second consecutive DOWN.
- **A gap in one cron's output ≠ host downtime.** We once saw a stability probe log ~50 of ~160 scheduled runs overnight while the host was continuously up (scheduler tick skips under load). Cross-check host-level watchers before calling an outage; report probe density honestly.

## Power-path forensics

- **UPS event logs are the authoritative mains-blip record.** A 2–5 second drop that never trips any monitor lands in `/var/log/apcupsd.events` on UPS-protected hosts as dated `Power failure.` / `Power is back.` lines. In a suspected blip, read the events file on every protected host — **majority rules** (in one incident, 3 of 4 units logged the same 07:00:52 drop; the fourth stayed silent on transfer sensitivity, not absence of the event).
- **Instant death + immediate fresh boot (~30 s–2 min later) + no shutdown sequence anywhere + no kernel fault = AC power loss with BIOS "Restore on AC Power Loss" enabled.** Not a crash, and not an agent/user action. Verify by matching the death timestamp against UPS event logs.
- **CMOS battery physics — do not get this backwards.** A dead CMOS/CR2032 battery *cannot crash a running system*: with AC present the RTC/CMOS circuit runs off the PSU +3.3VSB rail. A dead battery explains BIOS settings loss *after* power removal, boot failure, clock reset — not runtime death. Correct pattern: battery explains the settings-wipe symptom; a separate local power-path failure explains the runtime death. Diagnose them as two failures.
- **S3 suspend mimics a hang exactly** (dark screen, network dead, fans on). Check suspend/sleep config before calling it a hang.
- The **single-host-gap inference** only holds if you know which hosts are UPS-protected and which sit on bare mains. Maintain that list.

## Hard-hang follow-through (when it's the box itself)

After classifying a hard hang, run the hardware ladder and capture evidence before each destructive step:

1. Memtest from the boot menu (verify the option actually exists in the bootloader config — don't recite from general knowledge).
2. Suspect the **DIMM count before the sticks**: daisy-chain boards can idle-lock with 4 DIMMs even when every stick passes memtest — drop to 2 and retest.
3. Lock RAM to JEDEC (no overclock profile) to eliminate speed-training marginality. Confirm the *live* config with `dmidecode -t memory`, never by asking.
4. If clean DIMMs still crash: read the machine-check-error **Bank + reporting core** from the boot-time decode. Different cores, same bank, clean DIMMs = shared memory path → the CPU package's memory controller/fabric (a CPU swap is the discriminating test), board traces as fallback. We ended a multi-week crash saga this way — 2-stick config still fabric-flooded, MCE signature pointed at the package, CPU swap gave 44h clean under probe load, zero MCEs.

**Surviving evidence rules:** a reboot resets what you can prove — after a power-cycle, kernel messages only cover the new boot. Capture forensics (central telemetry, photographed console) *before* advising a power-cycle when the crash might repeat. And run `date` on the host before interpreting its timestamps — clock-skew between hosts desynchronizes box-local logs against true-UTC metrics; verify the timezone config on every host once, then trust it.

## The NAS-boot gotcha (Unraid-class systems)

After an **unclean shutdown**, Unraid boots with the array STOPPED and holds there indefinitely — no Docker, no app containers, no telemetry agent — until someone starts the array from the web UI. The signature: "host rebooted on its own, came back, but services stayed down for hours." Find the web-UI login → docker image mount → docker start sequence in syslog to learn who recovered it and when. During triage, **"when did services actually return" ≠ "when did the host boot."**

**Flash syslog mirroring** so kernel messages survive hangs on the boot flash (verified recipe, all our Unraid boxes):

```bash
printf 'syslog_flash="1"\n' > /boot/config/rsyslog.cfg
/usr/local/emhttp/plugins/dynamix/scripts/rsyslog_config
/etc/rc.d/rc.rsyslogd restart
tail /boot/logs/syslog   # verify live writes
```

Wrong paths that all failed: a `[syslog]` section in the main config is a no-op; there is no `/etc/rc.d/rc.syslog` (it's `rc.rsyslogd`); `local_server=` is the remote-receiver feature, not mirroring. The correct key is `syslog_flash`. Pair it with central UDP forwarding so the flash copy is the third redundancy, not the only one.

## Alert discipline (the rules that keep alerts trusted)

A monitoring stack's real failure mode isn't missing an outage — it's training the human to ignore it.

- **Never gate alerts on a single noisy sensor.** A UPS watchdog fired CRITICAL "imminent shutdown" every 5 minutes because apcupsd reported `TIMELEFT=1` while `STATUS=ONLINE BCHARGE=100` — a runtime-estimation artifact at full charge (direct query showed 17.7 real minutes). Correct logic: alert on `STATUS != ONLINE` OR low charge OR (low time AND low charge). A watchdog that cries CRITICAL at 100% charge trains the user to ignore every alert it ever sends.
- **Stale poller targets alert on services you intentionally stopped.** After any failback, decommission, or migration, the endpoint list still holds the old URLs. Sweep them, repoint to production (curl each health route and require 200 *before* adding it), prune orphaned state keys (else a phantom "recovered" alert fires), then run the poller once manually and require a clean N/N up line. A failback must restore monitor coverage too — we once ran a production service unwatched for three days while the stopped fallback hosts alerted.
- **Same-URL model swaps still need a name sweep.** When the *model* changes behind a *stable* endpoint, the URL keeps 200ing — no DOWN fires — but the target name goes stale. Rename, prune, re-run. And before treating any such alert as stale naming, probe the URL fresh: one "stale name" alert was actually a live OOM crash-loop (109 container restarts). Trust the monitor until the probe says otherwise.
- **A DOWN alert arriving right after YOU changed a monitored service = assume YOUR change broke it until proven otherwise.** Check restart counts and boot logs before touching the monitor. High restart count with the same OOM in every boot is config over-commit, not a flaky host. Related: a service that survives startup and same-day benchmarks has NOT been memory-validated — activation spikes under real mixed load appear hours later.
- **Error spikes on downstream services are cascade, not cause.** Router error spikes when an upstream GPU box dies: fix the dark host, not the spike. The failure modes behind router-side cascade are cataloged in [litellm-pitfalls.md](litellm-pitfalls.md).
- **Alert on transitions only, not every poll** — state file + alerted flag, one message per incident.
- **"Did you reboot my server?" gets answered with evidence in the first reply.** Audit your own automation first (job list + grep for reboot/shutdown/poweroff across your own scripts) — it's cheap, and a clean audit plus the death signature converts an accusation into a diagnosis in one turn. If the audit finds your own automation IS the actor: own it in the first reply, kill it immediately, state exactly what was removed. Never defend, never minimize.

## The passive-monitoring hard rule

> **Monitoring must be passive — never drive periodic inference load on a GPU host.**

"Is it working?" means ping, `/health`, log-tail, alert-on-down — checks that cost the box nothing. We once ran a */15 cron performing a full TTS generation (~35 s at 100% GPU, fans full-bore every 15 minutes) as a "health check"; it hijacked the box. Real-inference roundtrips are ONLY for bounded repair-validation soaks, deleted the moment the verdict lands. If a liveness blind spot demands deeper coverage — e.g. a service 500ing real requests while `/health` stayed 200 — watch passively (scan logs for error-rate transitions), do not synthesize load. **Probe cost must match the question asked.**

## Related

- [cron-at-fleet-scale.md](cron-at-fleet-scale.md) — the job-hygiene layer these monitors run on (locks, missed-fire detection)
- [fleet-operations.md](fleet-operations.md) — the dependency-map change control that prevents "your change broke it" incidents
- [gpu-lane-governance.md](gpu-lane-governance.md) — lease discipline for the hosts being monitored
