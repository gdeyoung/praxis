# DGX Spark operations — field notes

Odds and ends from running DGX Spark class machines as always-on inference nodes. Companion to the serving recipes in [`models/`](../models/).

## Power events are a first-class failure mode

These boxes are small, dense, and often on consumer-grade power. What we learned the hard way:

- **Loss of an input power phase can brown out the GPU rail** without tripping the host. Symptom: model serves, but every kernel launch takes ~10× normal and nobody's monitoring catches it because the process is "up." A power-cycle (full AC removal) restores normal. Watch actual inference latency, not process state.
- **No UPS on the Spark = accept data-loss windows.** We treat them as disposable compute: nothing stateful lives on a Spark; the model library and configs live on the NAS, and re-provisioning a Spark is a scripted 30-minute job. That conversion — from "server" to "cattle with a 30-min rebuild" — is what makes running three of them sane.

## The blue-green model swap

Never upgrade a serving model in place:

1. New model/quant lands beside the old (disk permitting).
2. Verification gate runs against the new endpoint ([the 7 checks](../models/qwen3.8-flash-next/verification/)).
3. Router alias flips — the one-line change every consumer sees.
4. Old artifacts stay untouched for a rollback window.
5. After N days green, reclaim disk.

The alias flip is the entire cutover. Consumers never know an IP or a port.

## Docker vs. native for NCCL/IPC work

Docker silently degrades NCCL to TCP sockets when it can't set up the shared-memory/IPC path — you lose ~40% of native prefill throughput on multi-GPU work and nothing errors. If you're doing RoCE/multi-node tensor parallelism on DGX-class hardware, run a native venv deployment, and verify the transport: NCCL debug logs must show `NET/IB`, not socket. (Lesson source: a 2× DGX Spark TP2 deployment writeup in the community — [credit in ATTRIBUTION](../ATTRIBUTION.md).)

Also on GB10: pin `flashinfer==0.6.18` — 0.6.17 crashes on the NVFP4 MoE fallback kernel, and the `shuffleInputRowsKernel` OOB error masquerades as a CUTLASS `status=7`, which will send you debugging the wrong library for an afternoon.

## The cluster pairing lesson

Two single-node vLLM instances on paired machines ≠ a 2-node cluster, but for latency-tolerant batch traffic the pairing (round-robin by alias, each node independently restorable) has better steady-state availability than true TP2 — a node loss halves capacity instead of zeroing it. We run dense decode on the pair and keep true TP for the models that genuinely need the pooled memory.

## Checklist: adding a Spark to the fleet

- [ ] Static IP, SSH key auth only
- [ ] Boot target multi-user; no desktop session
- [ ] Model dir on local NVMe, library + configs on NAS (don't serve weights over the network)
- [ ] Watchdog: health-poll the endpoint, alert (don't auto-restart) on repeated failure
- [ ] Rebuild script tested end-to-end — if you haven't run it, you don't have one
