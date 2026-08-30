# A work chief-of-staff — a de-identified writeup

This is a genuine writeup of an agent we run, de-identified: no employer, no customers, no account names. What remains is the architecture — because the pattern generalizes to any knowledge worker with meetings, a pipeline, a market to watch, and more inputs than hours.

## What it is

A specialized agent profile whose job is **the executive's throughput**: capture everything flowing past the human, structure it, and surface only what needs a decision. It is not a chatbot the exec talks to; it's a staff function that runs whether or not anyone's looking.

```
inputs                    chief-of-staff                       human
──────                    ────────────────                     ──────
meeting recordings  ──▶  transcribe → diarize →         ──▶   2-minute
calendar            ──▶  extract insights, actions,           daily digest
email ( triaged )   ──▶  commitments → searchable store        (decisions,
CRM / pipeline      ──▶                                      pre-drafted)
market signals      ──▶  monitor, correlate, escalate    ──▶  weekly exec
                          forecast, brief                        briefing
```

## The loops

**1. The meeting loop.** Every recorded meeting lands as a transcript (a privacy-first local transcription tool — see [ClearVoice](https://github.com/gdeyoung/Clearvoice)). The chief-of-staff pulls each transcript and extracts: decisions made, action items with owners, commitments with dates, risks named, and anything that contradicts a previous meeting. Structured output goes to the searchable knowledge base; the human gets the three lines that matter. Weeks later, "what did we promise them in March" is a query, not an archaeology project.

**2. The pipeline loop.** Deal/account data exports get parsed into a standard shape, stacked by stage and momentum, and turned into a forecast with reasoning attached — not a black-box number. Each deal carries a one-line "why it's at risk / why it moves." The output is a review-ready stack, every data point with its one-line explanation. (House rule from the human: *every* data point gets one line of explanation, or it doesn't ship.)

**3. The market loop.** The same autonomous-learner machinery described in [learning-workflows](../knowledge-management/learning-workflows.md), pointed at the exec's market: competitors, regulators, the accounts' industries. Signals mature across weeks on watch lists; the chief-of-staff correlates them with the pipeline ("that acquisition closes a competitive gap for exactly the deals in stage 3") and escalates when a window opens or closes.

**4. The briefing loop.** Everything funnels into a weekly executive briefing — pipeline movement, market shifts, meetings that mattered, decisions pending — each item with the evidence link. The briefing is assembled from structured stores, not written from vibes, which is why it's consistent week over week.

## How decisions actually flow

The chief-of-staff never acts on the exec's behalf. It files decisions into the queue:

```
DECISION NEEDED [q-117]
  The weekly briefing draft is ready.
  Options: (a) send as-is  (b) hold the pipeline section for the forecast
  Draft: <inline>
Reply: APPROVE q-117 / REJECT q-117 / DECIDE q-117 <instruction>
```

One reply from the human — from any surface, whenever — executes it. The agent's autonomy budget is spent on *preparation*, not action. That's the trust model: **it can prepare and recommend anything; it can execute nothing irreversible without a reply.**

## What makes it work (the honest list)

1. **A real transcription path.** The loop lives or dies on meeting capture. Local, diarized, speaker-labeled — the speaker library matters more than you'd think for "who committed to what."
2. **Structured stores, not chat history.** Everything extracted lands in queryable stores with admission tests (see [knowledge-flow](../knowledge-management/knowledge-flow.md)). A chief-of-staff that remembers only through conversation context is a goldfish with a title.
3. **Fixed digest formats.** Same shape every day, same briefing every week. Consistency is what lets the human skim at speed — novelty in formatting is friction.
4. **The one-line-explanation rule.** Every number, every alert: one line of why. It forces the agent to understand what it's surfacing, and gives the human an audit trail.
5. **Bounded autonomy with pre-drafted actions.** All preparation, no irrevocable execution. This keeps the trust asymmetric in the right direction: the agent works 24/7, the human decides in minutes.
6. **It de-identifies naturally.** Because everything flows through structured stores with governance, the same architecture runs on whatever domain — swap the market feeds and the pipeline schema, and it's a chief-of-staff for a different executive in a different business.

## What it costs

One specialized agent profile, local models for routine extraction, a frontier model only for the weekly briefing prose, the transcription path, and the knowledge stores you'd want anyway. The marginal cost over the existing fleet is one profile and a set of cron jobs. The marginal value is an executive who stops losing capture, forgetting commitments, and finding out about market shifts late.

That's the whole pitch: **a staff function is a system, and systems are what agents are actually good at.**
