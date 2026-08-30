# The interest funnel — from saved links to an agent that knows what you care about

A knowledge worker saves thousands of links and reads almost none of them. This is the pipeline that turns that hoard into an agent advantage: triage the stream, extract the interests, watch them continuously, and feed the good stuff back as daily digests and content ideas.

## The funnel

```
save anything interesting (browser ext, phone, agent)
        │
        ▼  ~thousands accumulated
TRIAGE ── dedupe, tag, classify, link-extract ──▶ organized library
        │
        ▼
PATTERN EXTRACTION ── what does this person actually care about?
        │              (category/time-of-day/engagement analysis)
        ▼
RECURRING TRACKERS ── agent watches the standing interests:
        │              releases, bills, competitors, price drops
        ▼
DAILY DIGEST ── only the delta, ranked by learned relevance
        │
        ▼
IDEATION ── mature signals become project/content candidates
```

## Stage detail

**1. Capture with zero friction.** The saving act must cost one action (bookmarklet, share-sheet, hotkey). Any taxonomy demanded at save time will be abandoned within a week — tagging happens downstream, by the agent, where it can be consistent. Our library: an open-source bookmark manager ([Karakeep](https://karakeep.com) class) with an API, because the agent needs programmatic access to do the downstream work.

**2. Triage, don't curate.** The agent processes the inbox: dedupe by URL/content, extract full text, classify against the emerging category tree, tag, and file. Unread is fine — the library is a searchable asset, not a todo list. The guilt-based model of read-everything is dead; what replaces it is "everything is *findable*."

**3. Extract the interest pattern.** Periodically (weekly), the agent analyzes the accumulated corpus: category distribution, save-rate trends, source quality (what you save from repeatedly), engagement (what you actually return to). Output is an explicit interest model — categories with weights, sources ranked, gaps named. This model is *derived from behavior*, not from what you'd claim you care about. The two differ, and the behavioral one is the better predictor.

**4. Stand up recurring trackers.** Each durable interest gets a standing watch (the same machinery as [learning-workflows](../hermes/knowledge-management/learning-workflows.md)): the agent monitors the release feeds, the legislative trackers, the competitor channels, and reports only deltas. Interest + watch = the agent knowing about the thing before you needed to ask.

**5. Digest the delta.** Daily: what changed across your trackers, what's newly saved worth attention, what matured. Ranked by the interest model, capped in length. The digest earns its slot in the morning or it gets tuned — readership is tracked the same way everything else is.

**6. Close the loop into ideation.** Signals that persist across weeks (a topic you keep saving about, a tracker that keeps firing) surface as project candidates and content ideas with the evidence trail attached. The funnel's endpoint isn't "informed human" — it's "human with a prioritized queue of things worth making."

## Why the agent version beats read-it-later apps

The app model stops at stage 2 — an organized pile. The agent model continues: it *reads* what you saved (summaries, entities, connections between items weeks apart), it *watches* forward, and it *proposes*. The difference is between a filing cabinet and a research assistant.

The compounding effect is the point: every saved link makes the interest model sharper, every sharper model makes the trackers better-targeted, every tracker-week makes the digest more signal. Six months in, the agent's model of your interests is better than your own notes about them — it has the counts.

## Minimal viable version

One person, one agent: bookmark manager with API + a daily cron that (a) triages the inbox, (b) runs 2–3 trackers on your top categories, (c) emits a 10-line digest. Skip the interest-model analysis for the first month — categories from your existing tags are enough to start. Add pattern extraction when the volume makes manual category care untenable. That's the on-ramp; the full funnel grows from what annoys you first.
