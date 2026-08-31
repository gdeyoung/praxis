# Verification gate — what "deployed" means here

No model swap is complete until every check below passes on the live endpoint, through the router the agents actually use. A 200 from `/health` is step zero, not success.

| # | Check | Pass condition |
|---|---|---|
| 1 | Coherence | Fixed prompt → sensible, on-format completion |
| 2 | Determinism | Same prompt at T=0, twice → byte-equal outputs |
| 3 | Prefix cache | Repeat long prompt → cache HIT (second TTFT collapses) |
| 4 | Prefill / decode | Usage-based numbers within expected band (see [benchmarks](../benchmarks/)) |
| 5 | Tool calling | OpenAI tools round-trip: model emits correct name + args |
| 6 | Router path | Request through the LiteLLM router → correct backend fingerprint |
| 7 | Real workload | One scheduled agent cycle runs end-to-end on the new backend |

Check 7 is the one people skip: synthetic passes don't predict whether the first real multi-step agent session works. Our learners' overnight cycles are the canary — if the fleet wakes up and runs its loop, the swap is done.

Rollback test: the previous layout/model must be restorable by config alone (one env var or alias), with the original artifacts untouched on disk.
