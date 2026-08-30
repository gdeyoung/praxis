# Tiered web access — routing, fallback, and quality drift

How an agent fleet should touch the web: pick the cheapest tool that works, fall back in order, and detect when your search stack silently rots. Every rule here ran in production for months.

## The decision tree

Match the tool to the page, cheapest first:

```
Need text from a page?
├─ Static / server-rendered ────────────▶ plain HTTP fetch + markdown extract
├─ JS-heavy SPA ────────────────────────▶ local headless-chromium scraper
├─ Needs interaction (login, clicks,
│   scroll, multi-step) ────────────────▶ CDP-driven browser session
│                                           (snapshot DOM, ~800 tokens/page)
└─ Bot-protected (Cloudflare et al.) ───▶ stealth browser: hardened Firefox
                                            build with fingerprint spoofing
```

The tiers matter because of cost: a plain fetch is milliseconds and near-zero tokens; a full browser session is seconds and thousands of tokens. Routing everything through the heaviest tool "to be safe" burns your context budget on navigation chrome. Routing everything through the cheapest fails silently on modern JS pages. The tree is the compromise.

**Search the same way:** a self-hosted meta-search engine (we use [SearXNG](https://docs.searxng.org/)) as primary — no rate limits, no API bill, result mixing across engines — with a lightweight DuckDuckGo client as automatic secondary when the primary times out. Extraction runs through a self-hosted [Firecrawl](https://github.com/firecrawl/firecrawl) instance for the same reason: extraction volume from scheduled jobs will hit any hosted API's tier long before it hits your own hardware's limit.

## Cache discipline

Every fetch through the shared backend gets cached with a TTL. Scheduled jobs (learners, watchers) hit the same URLs daily; serving those from cache turns a crawl into a lookup and keeps you a polite citizen of the sites you monitor. Bust the cache deliberately — one flag — when freshness is the point.

## Quality-drift detection (the part nobody publishes)

Search backends degrade quietly: an engine behind your meta-search changes its markup, results come back empty or garbage, and every downstream agent just... gets dumber. No error fires. This is the failure mode that matters.

Three layers of defense:

1. **Structured quality markers in every digest.** Our autonomous learners report, per cycle, whether search results were usable. That's a time series, not a vibe.
2. **The N-consecutive rule.** A complaint repeated across consecutive autonomous cycles is a defect, not weather. Ours flagged "search tier returns garbage on multi-word queries" four cycles running — that became an escalated bug report with evidence attached, not a shrug.
3. **Probe queries.** A tiny standing set of queries with known-good answers ("site docs page X", a stable Wikipedia article), run on a schedule against each backend tier. Pass = expected domain appears in top 5. Alert on miss-streak ≥ 3. This is a canary for infrastructure that otherwise fails silently.

## Selection rules that survived

- Never let a scheduled job pick the expensive tier interactively when a cached fetch answers the question — check the cache first, always.
- Extraction tools get a per-page token budget; pages over budget come back head+tail truncated with the full text on disk and a pointer. Agents that need more can page in; agents that don't weren't slowed down.
- One scraper change at a time. When extraction quality drops, diff against a known-good reference page before touching config — the markup changed more often than our config did.
