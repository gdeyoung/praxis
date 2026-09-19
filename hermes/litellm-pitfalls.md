# Operating an LLM router proxy in production — the pitfall compendium

Thirty failures, each one paid for. A router proxy (LiteLLM in our case — but
every pitfall here is about the *architecture*, two config layers plus a
fallback mesh, and applies to any member of that family) is the single point
of failure for an agent fleet: every profile, cron learner, and worker calls
through it. These are the ways it silently breaks, and the probe that catches
each one. Companion to [fleet-operations.md](fleet-operations.md) (policy) and
[model-calibration.md](model-calibration.md) (per-model prompt blocks).

## Layer 1: config defines models, the DB defines access

The proxy has *two* persistence layers: `config.yaml` (deployments, routing,
fallbacks) and a Postgres DB (virtual keys, each carrying its own static model
allowlist). Neither knows about the other's changes.

- **New model = three steps, and the third is a trap:** config edit + restart,
  then a SQL `array_append` sweep adding the model to every key that should
  see it — then **wait ~60s, because key auth is cached in Redis**. Post-grant
  calls through existing keys still 403 "model not in allowed models" until
  the TTL expires. The 403 body listing the key's models is proof you're in
  the cache window, not proof the grant failed. Do not re-grant.
- **Rename an alias = sweep the DB** (`array_replace` across all keys — they
  store static arrays). **Swap the backend *behind* an unchanged alias = config
  edit + restart only.** Keys authorize the alias name, never the upstream
  model string.
- **`/v1/models` can list ghosts** — aliases deleted from config but still
  present in some key's allowlist. Ghosts are callable-but-failing. When
  counting routes, diff the admin model-info endpoint against `/v1/models`;
  extras in the latter are ghosts. Scrubbing allowlists + restart clears them.
- **Key-management API calls can lie:** `/key/update` returns 200 with the
  updated model list *while writing nothing* for some key types. Verify in
  Postgres; fall back to direct SQL.
- **The token column stores hashes.** You cannot recover a key from the DB, and
  you cannot find a key by prefix-search. Match keys by model membership, not
  token text.

Case-sensitive table names round out the layer: quote them in SQL.

## Layer 2: the fallback mesh masks its own failures

Fallback chains are the feature that keeps the fleet alive when an upstream
dies — and the reason a dead component can stay dead for **weeks** with every
metric green.

- **A group with no fallback entry hard-fails** (`No fallback model group
  found`). New model groups default to *no chain*; audit chains after every
  addition.
- **A dead hop is invisible until probed directly.** Our end-to-end failover
  test "passed" (200, right content, 35s) while the intended cloud hop had
  been dead the whole time — the chain silently fell through to a local hop.
  **Read the response's model field / system fingerprint on every failover
  test.** A 200 proves the chain works; only the model field proves *which hop
  served it*. (Fingerprint, not model field, for llama.cpp-family hops — they
  echo the requested alias string.)
- **A dead *primary* is just as invisible.** A utility alias pointed at a
  backend that had been down for two weeks; every request walked the chain and
  returned 200 on the wrong model. 667 requests in 48h, zero errors anywhere.
  Detection signature: spend-log volume for the alias ≫ actual generation
  count in the backend's container logs.
- **Timeouts live under `litellm_params.timeout`, not model level.** A
  verification script reading the wrong location prints "no timeouts" for
  every deployment and is believed.
- **Timeout-kill × caller-retry = token amplification.** Queued request hits
  the deployment timeout → proxy kills it client-side (*no spend row*) →
  caller retries with full context → 65% prefix-cache miss → re-prefill →
  deeper queue. Measured 5.6× amplification (engine ingested 52M tokens the
  spend logs recorded as 9M). Fix both knobs: timeout above worst-case
  queue+decode, and a parallelism cap so the queue drains. The engine-to-log
  token ratio *is* the health metric.
- **There is no queue feature.** `max_parallel_requests` rejects excess with
  429 (internally retried with backoff), then cooldown marks the deployment
  dead and fallbacks route around it. For single-slot backends: cap
  parallelism at 1 so overflow backs off and fails over instead of holding
  connections for the full timeout, and stagger scheduled riders. A booking
  service in front of the proxy would be a new SPOF in front of the existing
  one — wrong trade.

## Probing: how to test without fooling yourself

- **A healthz green means nothing.** A meta-search backend returned
  `success` + zero results for *days* while every upstream engine was
  CAPTCHA-suspended. Zero results is a failure — fail over on it (see
  [core-patches.md](core-patches.md)).
- **`max_tokens=8` on a reasoning model is a false negative:** everything
  lands in `reasoning_content`, `finish_reason: length`, content null —
  "alias dead." Use ≥60 and read the reasoning channel before declaring
  failure.
- **Single-slot backends look dead under occupancy.** One active long
  generation queues your probe until curl times out. Diagnose occupancy (log
  timings climbing, CPU pinned) before breakage; test the alias twice.
- **Model self-report is not a probe.** Asked "is this text in your system
  prompt?", a Flash-class model said *no* while obeying the text's
  instructions. Behavioral probes only — see [model-calibration.md](model-calibration.md).
- **An invalid probe param triggers fallback** — the proxy retries the 400,
  walks the chain, and answers 200 *from a different backend*. Read the engine
  fingerprint on every probe response; an unexpected signature mid-debug means
  your probe fell over, not that the deployment died.
- **The wrong-type param probe** ("banana" where a number belongs) is the
  cheapest forwarding test that exists: a 400 type-error from the backend
  proves the param *arrived*; a clean 200 means something dropped it.

## Cloud vendors: their edge lies during diagnosis

- **Vendors swap upstream models behind live routes** and validate model
  strings (unlike llama.cpp backends, which ignore the model field entirely).
  A stale string = hard 400 from the vendor while everything else works. The
  response's model field can stay stale at the vendor — cosmetic; verify swaps
  on their models page.
- **Edge CDNs misreport bot-blocks as auth errors.** "Invalid API key" /
  "Missing API key" from a direct probe was actually a bot-signature ban.
  Never diagnose key health from an ad-hoc probe; test *through* the proxy. If
  you must isolate: a browser-UA probe from inside the proxy container
  separates edge (403) from key (401 with the real key).
- **Pin a browser User-Agent on Cloudflare-fronted deployments.** The proxy's
  own client doesn't reliably pass the edge; a pinned UA makes every call pass
  by construction. This single header line ended a recurring outage class.
- **Subscription credentials are not API keys.** A `sub_…` token in the config
  was a *subscription* credential — wrong type, rejected as `invalid_api_key`.
  Grep the whole secrets store before declaring "get a new key"; the live one
  may be fine and simply mis-wired.

## Config-editing hygiene

- The config is bind-mounted: edit the **host** file; `docker cp` into the
  container path fails. After host-side in-place edits, container reads can
  throw `Stale file handle` (old inode) until restart — not corruption.
- **Hot-reload with an empty payload returns success and drops every
  deployment.** `POST /config/update` with `{}` answers "Config updated
  successfully," then every request 400s `no healthy deployments` — and the
  follow-on "no fallback group" errors point you at the wrong layer entirely.
  Recovery is a restart (re-reads the intact on-disk config). The success
  message reflects the request, not the router. After *any* reload: check the
  `/v1/models` count before touching anything else.
- **Validate YAML where a YAML parser exists.** Our NAS-OS host python lacks
  PyYAML; the container has it. Stage → validate → scp → restart, or run the
  whole load/mutate/dump cycle inside the container. Never round-trip
  comment-bearing configs through a YAML dumper.
- **Disable by commenting out, not deleting** — `# DISABLED <date>: reason`
  headers make re-enable audits trivial and keep the key/endpoint references.
- **Doctrine drifts.** A routing decision recorded in prose ("this alias gets
  a 600s timeout") is not self-enforcing; later edits silently regress it.
  When answering "what is alias X doing," read the live config, and treat the
  plan/credential identity as a separate claim resolvable only by expanding
  the configured key reference and probing the upstream with it.

## Spend-log auditing

- Schema traps: the alias column is `model_group`; the timestamp is
  camelCase quoted `"startTime"`; `cache_hit` is *text* containing `"None"`
  (casting blows up — filter on `IN ('True','t','1')`); statuses are lowercase.
- **Attribute traffic before comparing windows.** The session doing the deploy
  generates benchmark and verification rows that swamp organic traffic — our
  "before" rows averaged 52k–125k prompt tokens because the *inspection
  session itself* was the traffic. Filter by caller; use the scheduled-job
  fleet as the ambient canary that a change hurt nothing.

## The sampler passthrough trap (short version)

With `drop_params: true`, non-OpenAI-standard sampler keys (`dry_multiplier`
and friends) are **silently dropped** at deployment level unless they ride
inside `extra_body` — request-level top-level is forwarded, deployment-level
is schema-filtered; test at the level you deploy. This exact trap disabled
loop suppression for five days after a model swap, until the wrong-type probe
caught it. Full story and the calibration-block system built on the same
probe: [model-calibration.md](model-calibration.md).
