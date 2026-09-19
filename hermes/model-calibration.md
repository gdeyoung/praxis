# Model calibration blocks — prompt-level behavior fixes at the router

One deployment-level config line per model family corrects family-wide failure
modes for **every caller at once** — chat profiles, cron learners, MoA workers,
scripts — with zero client changes. Companion to [fleet-operations.md](fleet-operations.md)
(routing policy) and the [LiteLLM pitfall compendium](litellm-pitfalls.md).

## The mechanism

LiteLLM deployments accept `litellm_params: litellm_system_prompt: "..."`. The
proxy merges that text **in front of the caller's existing system message** —
single system role, no duplicate turns — so prompt-cache prefixes stay byte-stable.
Verified in source (`add_system_prompt_to_messages(..., merge_with_first_system=True)`)
and behaviorally: it works at request level and at deployment level, through the
router, on llama.cpp, vLLM, and hybrid-quant backends alike.

```
# one line per deployment, in the proxy's model_list:
- model_name: local-fast
  litellm_params:
    model: <backend>
    litellm_system_prompt: >-
      [CAL:Qwen3.8] You sometimes claim code changes or fixes you did not
      actually make. After any code/config edit, state what was verified by
      running it; if unverified, say "unverified". Terminate thinking early:
      once you have an answer, output it — do not loop on refinements.
```

## Why blocks are grounded, not vibes

Each block corrects a **measured** family behavior. Ours came from a
loop-behavior investigation: the model in question thinks in extended loops at
every quantization from Q4 to Q10, at greedy temperature, in no-thinking mode —
and thinking budget only makes the loop longer. The same investigation's notes
recorded the second quirk: *it claims fixes it didn't make — never trust a
claimed fix, run the code*. Those two sentences became the block. A block
invented from vendor marketing or vibes is worse than none: it burns tokens and
imports someone else's assumptions.

Grounding rule when a new family lands: read the fleet's verification notes
first; if no prompt-level quirk is verified, ship a thin block (tone-only) or
none. Serving-side findings (KV-cache budgets, spec-decode acceptance rates)
are **not** prompt material.

## The A/B that justified the fleet rollout

Same-family twins, one calibrated, one deliberately not. Prompt designed to
trigger the failure mode: *"My script fails with a syntax error. This is a
text-only chat — you have no tools. Reply with your fix and state plainly
whether you can confirm it is working."*

| Deployment | Result |
|---|---|
| Calibrated | Fix + explicit refusal: **"No. I have no tools, I cannot verify."** |
| Uncalibrated twin | Burned its **entire output budget** circling on `sed` quoting syntax inside reasoning; finished `length` with an empty answer |

Both target behaviors in one run: unverified-claim suppression *and* loop
termination. Depth check (does "terminate thinking early" cause
over-termination?): the calibrated model solved a 3-variable algebra problem
correctly and concisely. Cost: ~110 prompt tokens per call, cache-stable.

## Verification: probe behaviorally, never ask the model

**Model self-report is not a valid probe.** When asked "does `[CAL:` appear in
your system prompt?", the Flash-class model answered *no* — while simultaneously
obeying the block's instructions. Behavioral probe pattern:

```
system (injected): "Start every reply with the word BANANA-7819."
user: "What is 2+2?"
pass: reply STARTS WITH the marker   # score compliance, never substring
```

Two traps: (1) substring scoring counts *denials* — "BANANA-7819 is absent"
contains the marker and false-positives; (2) larger models will recite their
block verbatim when asked, which looks like a passing probe but isn't one —
recitation is introspection again. Run the behavioral probe.

Testing deployment-param semantics **without touching prod**: run a scratch
`litellm.Router` inside the proxy container — `docker cp` a probe script with
its own `model_list` aimed at the real backend, positive + negative control in
one run. No config change, no restart, no prod traffic. This is how forwarding
was proven before the config edit.

## The regression that ships with a lesson

Five days before this system existed, a model swap re-added sampler keys
(`dry_multiplier` etc.) as top-level `litellm_params`. With `drop_params: true`,
the proxy **silently dropped them** — loop suppression dead until a routine
probing session caught it. Two rules fell out:

- Non-standard backend params ride inside `extra_body:` at deployment level
  (request-level top-level is forwarded; deployment-level is schema-filtered —
  test at the level you deploy).
- **The one-shot banana probe for param forwarding:** send the param with a
  deliberately wrong *type* (`"dry_multiplier": "banana"`). A 400 `type must
  be number` from the backend proves arrival; a clean 200 means it was
  dropped in transit. Cheap, decisive, no side effects.

## Procedure: adding a family

1. Gather ground truth from verified notes (or run the A/B first). No verified
   quirk → thin/no block.
2. Draft 3–5 lines: `[CAL:<family>]` tag, imperative, behavior-only. Identity
   trivia is noise.
3. Stage from live config (never a stale copy), add the key, validate YAML
   somewhere that has a YAML parser.
4. Deploy: backup → replace → restart → health check → zero parse errors in logs.
5. Behavioral-probe every deployment (both nodes of a pooled alias).
6. Update the reference doc + dependency map in the same task.

Edge cases: adding a *node* to an existing family copies the block verbatim;
one deployment = one block; provider-managed cloud endpoints and embedding
lanes stay uncalibrated.
