# Operating a chat WebUI over your agent — without forking it

The web interface you actually chat with deserves the same operational discipline as the agent behind it. This is how we run a self-hosted [Hermes WebUI](https://github.com/nesquena/hermes-webui) (MIT, 18k★) as the primary human interface for a fleet — the rules that keep it upstream-updateable, the extension surface that replaces forking, and the operational lessons from nine months of daily use.

> Schematic on purpose: paths and ports are ours; the contracts and failure modes are the transferable part.

## The one rule: never fork the primary interface

A chat UI you use every day is a vending machine for upstream improvements: fixes, features, security patches. Every core file you edit is **fork debt** — it blocks `git pull`, rots silently, and converts a one-command update into an archaeology project. Our standing rule: **the primary human interface must never be forked or core-modified — upstream updateability is a hard constraint.** Customization goes through the sanctioned extension surface instead.

The escape hatch when you *do* need core-shaped behavior: carry patches as a series applied on top of a tag, never commits inside the working tree — and disposition every one at each update (upstream absorbed it? drop ours; still unabsorbed? port it to the extension surface or re-apply). The last such review moved four patches: two dropped (one already superseded by upstream's visibility-based video-preload promotion — grep the remote blob before assuming your hack is still needed), two ported to an extension. Rollback stays one command: a backup tag + a stash of the fork debt.

## The extension surface (custom UI without touching core)

The WebUI's extension system is the no-fork rule's enforcement mechanism — and the pattern generalizes to any SPA you operate but don't own:

- **What an extension is:** static assets served from a managed directory under `/extensions/<path>`, plus declared scripts/stylesheets injected into the app shell (same-origin only). Extension JS runs with full session authority and can call every `/api/*` route the user can.
- **The sidecar pattern:** a stdlib Python HTTP server on `127.0.0.1:<port>` reached through a consent-gated proxy (`/api/extensions/{id}/sidecar/*`) with per-extension token auth. **Injected JS is a thin skin; ALL state and business logic live in the sidecar.** When a UI update breaks the DOM layer, a broken skin is a re-glue, not a rebuild.
- **Update-survival ranking** for anything you bolt on: `iframe/link > HTTP API > container > in-process DOM injection`. Choose the leftmost tier that does the job.
- **Consent is explicit per sidecar**, granted in settings; the proxy strips all inbound credentials and the sidecar validates a per-extension token on every route except `/health`. Token auth **fails closed when WebUI auth is off** — configure authentication before granting consent, or everything 403s.
- **Proxy envelope limits:** responses fully buffered, ~512 KiB body, ~10s upstream timeout, **no streaming**. Anything slower than a few seconds must be start-job + poll — never a long-held request.
- **CSP knobs** for operators: extra connect origins and extra frame origins are env vars; frame-ancestors stays `none` (the UI itself can never be framed). Pinning an external app as a tab needs the frame-origin var.
- Install from a vetted gallery (zip or one-click), or manual manifest. Extension trust model: the code runs as the logged-in user — only install your own builds or vetted entries, never point the managed dir at a user-writable directory on a shared host.

Reference implementations worth cloning (both in the [gallery repo](https://github.com/hermes-webui/hermes-webui-extensions)): a dashboard-cards extension with a complete sidecar scaffold (token auth, start-job/poll for long ops), and an external-app-tab extension that pins any self-hosted app as a tab inside the chat UI.

## Session caps, stranded work, and recovery

The most valuable operational lesson: **when a long agent session dies to a tool-iteration cap, real work is stranded mid-flight** — and there's a recovery pattern.

1. **Find the real knob by grepping the reader, not the schema.** Our cap chain: the streaming layer reads `agent.max_turns` (root fallback, then constructor default) into `max_iterations`. A past session wrote the value to a plausible-but-dead config key, believed the cap was raised, and three later sessions died at the old limit. If the config CLI warns "not a recognized key," that warning is a real signal — verify against the reading source before trusting the change.
2. **Config hot-reloads on mtime** — no server restart; new sessions pick up new limits immediately.
3. **Guardrails are independent of the cap.** Stuck-loop detection (exact-failure repeats, idempotent no-progress) still fires regardless of the cap — raising it only extends legitimate long work. The only cost: a confused-but-not-failing session burns more tokens before summary.
4. **Recovery sequence for a capped session:** the forced final summary is an honest ledger of done vs in-flight → `git status --short` in the affected repo (modified-uncommitted = the stranded work) → check status-tracker files → re-run only the missing gates, cheapest first → commit the whole stranded set → raise the cap so the next pass doesn't repeat it.
5. **The cap is a backstop, not the fix.** The discipline that actually prevents strandings: **commit + deploy per completed batch, not per pass.** Long QA-heavy passes are exactly the shape that burns iterations — checkpoint between batches.

## Serving media in chat (the inline-player contract)

A chat UI for an agent that produces listenable deliverables needs players, not links:

- Emit a token of the exact form `MEDIA:/abs/path` — **no space after the colon**. A space makes the whole line render as literal text with no player, silently. When players are missing, check the emitted token syntax first, not the server.
- Rendering routes local paths through an authenticated media endpoint plus a per-session allow-list; audio/video → player, images → lightbox, PDFs/HTML/CSV → lazy inline loaders.
- Deliverable rule: **anything meant to be listened to or watched goes out via the inline player — never as bare download links.** Bare links are the path for remote/travel delivery and non-playable artifacts only.
- Verify the file exists on disk before emitting the token, one take per line, brief note beside each.

## Ops notes that saved us

- **The backend is a plugin-loading surface.** The server builds agents through the same plugin manager as any other entry point and loads plugins at process start. A plugin newly enabled in config reaches gateway sessions after a gateway restart but **not WebUI sessions until the server itself restarts** — we ran days with the injection silently absent because the server predated the plugin. After enabling ANY plugin: restart this backend too.
- **Auth-gated API probe pattern:** all `/api/*` routes 401 without a session while `/login` returns 200 — that pair is the cheapest liveness + auth check (`curl /login` → 200, `curl /api/health` → 401).
- **Don't restart services for client-side symptoms.** A dead mic transcription path was a wedged browser audio graph (a crashed audio stream leaves AudioContext/MediaRecorder stuck for the whole tab); the STT backend answered a direct probe in 0.57 s. Read logs first; a browser restart was the fix, not a container restart.
- **Immutable-OS update wipes:** an ostree update silently removed every custom systemd unit under `~/.config/systemd/user/` (reboots never did — only updates). Recovery source: the off-box unit backup. After any OS update, list unit files first; if wiped, re-copy, daemon-reload, enable. Watch for runtime version bumps breaking tool commands fleet-wide (grep for the old version string).
- **Reverse-proxy HTTPS exposure:** serving the UI through a mesh-VPN HTTPS proxy (serve rule → loopback) means the proxy's route config is **separate from the systemd unit** — it can be repointed at a throwaway file server, making every session deep-link open a directory listing while the UI itself runs fine. When remote links misbehave, check the proxy's serve rule before the server. Verify with GET, not HEAD (some proxies handle them differently).
- **Restart cost is stated, not hidden:** restarting the backend drops the active tab's connection; sessions persist in the DB and reload. Say so before restarting — the primary interface's uptime is a user-visible surface.

## Related

- [plugin-seam.md](plugin-seam.md) — the plugin architecture this UI's backend shares with the rest of the fleet
- [cron-at-fleet-scale.md](cron-at-fleet-scale.md) — capped-session recovery generalizes: stranded work, honest ledgers, checkpoint discipline
- [fleet-operations.md](fleet-operations.md) — where this UI sits in the multi-profile fleet
