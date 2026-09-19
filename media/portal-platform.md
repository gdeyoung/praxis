# Self-hosted portal platform — one entry point for an agent fleet's output

How a multi-agent system publishes everything it makes — games, apps, reports, media, learning notes, skills — behind one URL with an app-store UX, using nothing but Caddy and static files. The intelligence lives in the **generators**, not the servers: every section is a build-time catalog plus a vanilla HTML page, with no runtime database and no SPA framework. Live on a single NAS box since 2026-08-18, ~12 sections, ~575 media files indexed.

> Schematic on purpose: no hostnames, no IPs, no port of our instance. The pattern is the product.

## Architecture

```
Browser → single Caddy entry (one port, one container)
   ├── /                hub (hero + category doors + live status chips)
   ├── /games/<id>/     static, self-contained (folder drop = live)
   ├── /arcade/         app-store catalog page (apps.json + screenshots)
   ├── /apps/<id>/*     reverse_proxy → per-app internal container
   ├── /media/          generated-asset library (catalog JSON + thumbs)
   ├── /studio/         published-work player (published catalog JSON)
   ├── /reports/ /learn/ /skills/  static generated sections
   └── /live/api/*      optional read-only status API (JSON, key-auth)
```

**Rules that made it durable:**

- **Zero build step, zero runtime deps.** Vanilla HTML/CSS/JS. Self-hosted fonts (never a CDN). A section page is one file fetching one catalog JSON with a cache-buster.
- **Static-generated as the foundation; live APIs bounded and optional.** A read-only status API can layer on (15s TTL cache, per-block isolation so one failing block serves `{"error"}` while the rest answer, credential scrubbing on every output string) — but the hub renders fine without it. Sections that need live data get it; nightly sections get staleness chips instead. Live-at-serve-time was explicitly rejected as an architecture.
- **Single-entry routing.** One Caddy container owns the port. Static sections get `handle_path` routes; backend apps get internal-only containers (never `ports:`) proxied under `/apps/<id>/*`. Ports 80/443 belong to the NAS's own nginx — never bind them.
- **Naming conventions:** containers `<platform>-*`, one bridge network (no fixed subnet — it collided with the NAS's bridge), appdata-rooted bind mounts only.

## The catalog/provenance system

Every generated section ships a JSON catalog + a provenance block. This is the part worth copying:

```json
"provenance": {
  "built": "2026-09-19T18:48:31Z",
  "counts": [
    {"value": 575, "definition": "files in the catalog (unique by sha256)"},
    {"value": 1, "definition": "archived (flag only, files never move)"}
  ],
  "sources": [{"label": "media scan", "path": "...", "present": true}]
}
  ```

- **Counts carry definitions.** A bare number with meaning only in hover text is not done — every count states what it counts, and competing counts sit side by side instead of being hidden.
- **Sources are named, with presence dots.** Missing sources are called out, not silently skipped.
- **Staleness contract.** A `refresh.json` (per-section `{last_ok, duration_s, error}`, served no-cache) plus a provenance footer on every section page: counts + definitions + built-when + a STALE chip. The user can always answer "how fresh is this number" without asking.
- **Degrade-don't-fall-over.** Pipelines are step-isolated: a failing step stamps its section and the pipeline CONTINUES; exit nonzero at the end, not at the first failure.
- **Atomic JSON writes** (tmp+rename), and every string that ships gets a credential scrub pass.

## The media library (the hardest section)

Index-only design: originals never move. A catalog script hashes + ffprobes the scan targets in place, derives 512px thumbs (waveform posters for audio), and writes SQLite + JSON. Scan targets are a **curated list** (`targets.conf`) — never auto-scan a whole work tree, or test dirs and smoke tests flood the portal. Originals rsync to the server nightly; the catalog regenerates hourly.

UX contract (learned the hard way, each rule from a real complaint):

- **No flat file walls.** A media surface must offer latest-first, project grouping, time filters, sorts, collapsible sections, in-page modal previews, provenance, and a path back to the originating chat.
- **Time filters form a clean non-overlapping calendar progression** (hour → today → yesterday → week → last week → month → all) — never overlapping rolling windows.
- **Reversible archive over delete; trash is quarantine + restore, never `rm`.** Archive is a flag; trash moves to a dated quarantine dir but keeps the catalog row and tags.
- **Manage controls are SECTION-SCOPED.** Restore/Untrash buttons exist only inside the Archive and Trash tabs. Derive manage controls from the active view, never from file flags alone — flag-keyed controls leak Restore buttons into browsing contexts where they read as noise.
- **Chat attribution.** Correlate each source folder to the agent session that generated it (title + content-mention + time-window matching against the session DB) → stamp `chat`/`chat_title` per file → group by chat, search matches chat titles, and a "continue in chat" deep-link in every modal. Generated media without provenance is half a product.
- **Published work gets its own section** (player-grade UI, queues, waveforms) — a working-files library and a published library have different jobs.

**Writes** go through a tiny key-auth API (tag/archive/trash/unarchive) that **regenerates and ships both catalogs in the same request** — otherwise UI changes are invisible until the next nightly sync. The key file is generated per-deploy, gitignored. Never ship a write API on a public surface without auth.

**Content boundaries are split surfaces, not tabs.** Content classes that must not mix (different audience, different sensitivity) get fully separate portals: own page, own catalog, own route and mount. No cross-links. A tab inside the main portal is one flag-flip away from appearing in every view; a separate surface is a build-time split in the catalog generator, enforced at build time, not serve time.

## Deploy & ops pitfalls (all bit us)

1. **`docker compose up -d` does not attach newly-added volumes.** Adding a bind mount and running a normal deploy leaves the running container with the old mount set — routes 404 despite a valid config. Fix: `up -d --force-recreate`. When a new route 404s post-deploy, **check mounts first** (`docker inspect ... .Mounts`).
2. **A new static section touches FOUR configs, and a green deploy hides the missing ones:** (1) Caddyfile route, (2) compose volume mount, (3) deploy script mkdir+scp+verify-URL, (4) every sync pipeline that ships the section's files. `caddy validate` cannot catch a missing mount — the route is valid, the mount doesn't exist.
3. **Config-only changes do NOT reload Caddy.** `up -d` recreates nothing when only the bind-mounted Caddyfile changed. `docker restart <caddy>`, wait for health, then curl the affected route and verify it actually changed.
4. **Sub-path fetch paths (the #1 app bug):** apps under `handle_path /app/<id>/*` get the prefix stripped, so the app sees `/`. Frontend fetches must be document-relative (`api/items`), never origin-absolute (`/api/items`) — the latter escapes the prefix and 404s.
5. **Screenshots and catalog entries are generated by script, never hand-authored.** A hand-typed catalog entry dropped a field mid-file; generator scripts with assert-verify (every game dir has an entry, every URL matches the route pattern) guarantee validity by construction. New IDs must be added to the generator's tables or the catalog silently omits them.
6. **`.gitignore` does not apply to already-tracked files.** A broad `git add -A` committed a transient lock file before its ignore rule existed; a key file sat tracked for days while believed ignored. Verify with `git ls-files | grep <name>`, never by command chaining (a chained `&&` where the first check fails silently skips the second). If a key ever sat in git: rotate, restart the validating service, bound exposure with `git log --all -- <file>`.
7. **Large generated single-file writes can corrupt.** 9-15KB files arrived with mangled declarations, hallucinated method names, invented JSON keys. Defenses: run validators after EVERY generated write; prefer validated formats (JSON refusals saved a catalog cold); ≤3 bad spots → targeted patch, pervasive → clean rewrite. Never trust a big generated file untested.
8. **Verify after health, not after `up -d`** — instant curls race the port bind. Wait on `docker inspect -f '{{.State.Health.Status}}'`.
9. **Deploy reports must name WHERE the visible change lands.** "Shipped + verified" with the entry page untouched by design reads as nothing-happened. Name the exact URL + page position of the visible delta; remind about hard-refresh (pages are ETag-cached).
10. **A verification step that logs `skipped: <error>` and reports green is a dead guard.** After adding any check, run the pipeline once and grep for the check's own OK lines, not just for absence of failure. Absence of failure is the failure mode the guard exists to catch.
11. **Verification without a browser is possible but must be labeled.** Extract every inline `<script>` and compile with `new vm.Script()`; then run the exact shipped script body in Node against the live server, fetch the real catalog, execute the same render logic, assert expected strings. State plainly that literal DOM insertion is verified by simulation, not a real browser.
11. **Automation browsers can't decode h264** — prove video plumbing server-side (ffprobe) and trust desktop browsers for decode. Audio decode IS provable (readyState + advancing playhead). Also: codec-stripped headless images fail on files that are fine; use a full-codec image for media verification.
12. **Kill processes by port via `ss`, never `pkill -f` with the port in the pattern** — the pattern text appears in the shell's own command line and kills it.

## What we rejected, and why

- **A dashboard framework** (Next.js/React SPA) for the whole platform — a rebuild-everything dependency for a browsing UX that one fetch + render loop already does. Zero-build static pages survive infrastructure churn.
- **Live reads at serve time** as the foundation — every page render blocked on backend queries; a static catalog with a staleness chip answers "is this fresh" without a runtime dependency.
- **A heavier backend (self-hosted Supabase-class).** A single small backend (PocketBase) covers auth/leaderboards for games; the full platform needs nothing beyond it. Upgrade only when an app genuinely needs it, on a dedicated port/subdomain — never a subpath (their APIs are host-root shaped).
- **In-page tabs for content classes that must not mix.** See the split-surface rule above.
- **Auto-scanning the whole work tree** for media — test dirs flood the catalog; curated targets only.

## Related

- [verification-gates.md](verification-gates.md) — the generation-side quality gates that feed this library
- [fleet-monitoring.md](../hermes/fleet-monitoring.md) — how the sections' freshness contracts are watched
- [cron-at-fleet-scale.md](../hermes/cron-at-fleet-scale.md) — the refresh pipelines that regenerate catalogs on schedule
- [knowledge-management/](../hermes/knowledge-management/) — the stores the generated sections surface
