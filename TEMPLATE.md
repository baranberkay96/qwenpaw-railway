# QwenPaw v2 Personal AI Assistant: Railway template spec

## Listing

| Field | Value |
|---|---|
| Name | **QwenPaw v2 Personal AI Assistant** (`v2` = major version of the pinned `v2.2.2`; upstream spelling "QwenPaw") |
| Description | Always-on personal AI assistant with chat apps, memory and skills. (66 chars, unchanged) |
| Category | AI/ML |
| Tags | qwenpaw, agentscope, ai-agent, personal-assistant, telegram, discord, slack, dingtalk, feishu, llm |
| Icon | `https://cdn.jsdelivr.net/gh/agentscope-ai/QwenPaw@v2.2.2/website/public/qwenpaw-symbol.svg` (upstream symbol pinned to the tag, HTTP 200 `image/svg+xml` checked) |

The description holds as written:
- **Always-on**: one service with restart policy `ALWAYS`; heartbeats, cron jobs and memory consolidation ("dream" job) run inside the app. All state is on a volume.
- **Chat apps**: Telegram, Discord, Slack, DingTalk, Feishu/Lark, QQ and WeCom can be switched on from variables; these and Mattermost, Matrix, MQTT, WeChat, XiaoYi, Yuanbao, OneBot and Twilio voice are also available in the Console. Their SDKs are already in the official image.
- **Memory and skills**: upstream's ReMe long-term memory, `MEMORY.md` and 16 built-in skills (cron, PDF/Office files, browser, news and more) are enabled on the first boot.

## Base market template

| Market template | Source | State on 2026-10-20 | Verdict |
|---|---|---|---|
| `qwenpaw` | image `agentscope/qwenpaw:v1.1.0` | 8 projects, 5 active | Outdated (v1.1.0). **No login configured**: the console, its shell tool and the API are open to anyone with the URL. No healthcheck. Volume only on `/app/working`, so where secrets end up depends on upstream fallbacks. |
| `qwenpaw-private-assistant` ("QwenPaw Private Assistant") | image `agentscope/qwenpaw:v2.2.1`, start command that rewrites upstream's supervisord template | 3 projects, 0 active | **Strongest base.** Kept: one `/data` volume holding the three state directories, login forced on from generated credentials, randomized username, Tool Guard forced on, `/api/version` healthcheck, 30 s draining. Problems: the app still runs under supervisord with `autorestart=unexpected`, so a crashed or exited app leaves a running container that serves nothing while the restart policy never fires; persona files stay Chinese (the README tells users to switch); no chat-channel variables; the password variable has no effect after the first boot; upstream telemetry is sent without anyone seeing the consent prompt; the shell tool is denied outright. |
| `qwenpaw-1` (`RockinPaul/qwenpaw_railway_template`, MIT) | Dockerfile on `agentscope/qwenpaw:v2.2.1` | 1 project, 0 active | Good security notes (no in-container proxy, `0.0.0.0` bind, measured 401 through Railway's edge), refuses to boot without a password, seeds `agents.language` before the first init. Problems: fixed username `admin` (five wrong passwords lock it for 15 minutes, so anyone can lock the owner out), app logs stay in files inside the container, same supervisord restart gap, and the seed fixes only the persona files: the default agent's own `language` stays `zh` (verified natively on v2.2.2, see Verification results), so access-control replies and memory prompts stay Chinese. Read only; no file or text copied (see NOTICE.md). |

Upstream references checked at tag `v2.2.2`: `deploy/Dockerfile`, `deploy/entrypoint.sh`, `deploy/config/supervisord.conf.template`, `docker-compose.yml` (three volumes, `init: true`, port bound to `127.0.0.1`, auth variables commented out), and the Docker quickstart, security and channels docs. QwenPaw also has a desktop app (Tauri); this template uses the server mode (`qwenpaw app`) that the official image runs.

## Pinned versions

| Component | Source | Version | Released | Checked |
|---|---|---|---|---|
| QwenPaw | `agentscope/qwenpaw:v2.2.2@sha256:ba70a1e6511cca8afa5728d145826b522f835c3405beb9be9e8baa8bad5b1b9b` (multi-arch index; amd64 manifest `sha256:cc39d717…`, 1.06 GB compressed) | v2.2.2 = git tag `v2.2.2`, commit `5c56644a6e130762a236f8c946103e95a0a1eec8`; PyPI `qwenpaw 2.2.2` | 2026-10-15 | 2026-10-20 |

Image tags were checked with the Docker Hub API (`/v2/repositories/agentscope/qwenpaw/tags/v2.2.2`: present, same digest as `latest`) and the registry API (image config: `Cmd ["/entrypoint.sh"]`, `Entrypoint ["docker-entrypoint.sh"]`, `WorkingDir /app`, runs as root, Node 25.6.0 base, Python 3.11 venv in `/app/venv`).

The service is built from `services/qwenpaw/Dockerfile` (repo `baranberkay96/qwenpaw-railway`, root `/services/qwenpaw`), a thin layer on the pinned image that adds `railway/` (entrypoint, setup script, supervisord config). Upgrade: change the tag and digest in the Dockerfile, read the release notes, redeploy. The build fails early if the upstream helpers the setup script imports (`qwenpaw.app.auth`) disappear. The volume keeps everything.

## Architecture

```
 Telegram / Discord / Slack / DingTalk / Feishu / QQ / WeCom ◄── outbound bot connections
                              ▲                                   (no inbound ports needed)
 ┌────────────────────────────┴──────────────────────────────────────────────┐
 │ QwenPaw (agentscope/qwenpaw:v2.2.2 + railway/ wrapper)                    │
 │  podman-init (PID 1) → railway-entrypoint.sh                              │
 │   1. railway_setup.py  first boot: language seed + `qwenpaw init`         │
 │                        every boot: login account, trusted proxies,        │
 │                        channels in the default agent's agent.json          │
 │   2. supervisord (background): dbus · Xvfb :1 · Xfce  (headed browser)    │
 │   3. exec qwenpaw app --host 0.0.0.0 --port $PORT   ← main process       │
 │        console (SPA) + REST API + SSE, auth middleware on /api/*          │
 │        agents, tools (shell, files, Chromium), cron, heartbeat, memory    │
 │  volume /data: working/ (config, workspaces, chats, memory, skills)       │
 │                working.secret/ (login, encrypted provider keys, master key)│
 │                working.backups/ (Console backups)                          │
 └────────────────────────────┬──────────────────────────────────────────────┘
                              │ HTTPS (Railway edge) → :8088, healthcheck GET /api/version
                       Console login: QWENPAW_AUTH_USERNAME / QWENPAW_AUTH_PASSWORD
```

One service, no database: QwenPaw stores everything in files and embedded stores under its working directory. Upstream's own compose file is a single container too; nothing was dropped. The X display and Xfce session are kept because the agent's headed browser mode and desktop screenshots use them (upstream runs them in the image).

### Why the app runs outside supervisord

Upstream's entrypoint makes supervisord the main process and runs the app as one of its programs (`autorestart=unexpected`, 5 start retries, logs in `/var/log/app.*.log`). On Railway that has two failure modes: the app's logs never reach Railway's log view, and when the app exits cleanly or gives up after 5 fast crashes, supervisord keeps the container alive with no app, so Railway sees a running deployment and never restarts it. Here the app is the container's main process (logs go to Railway, any exit restarts the container through `ALWAYS`), and supervisord only keeps the three desktop helpers alive. Railway's init being PID 1 (Rule 8.3) is no problem for either: supervisord does not need to be PID 1, and upstream's own compose file runs the image with `init: true`, the same arrangement.

### Network binding

`qwenpaw app` is uvicorn with one worker, so it binds `0.0.0.0` (Rule 8.2: an asyncio socket on `::` is IPv6-only, and Railway's healthcheck and edge connect over IPv4). Nothing else in the project connects to it; the REST API is used through the public domain. Nothing proxies inside the container: QwenPaw skips its login for loopback clients (`security.allow_no_auth_hosts` = `127.0.0.1`, `::1`, needed by its own CLI and skills), so an in-container reverse proxy would switch the login off.

## Service: QwenPaw

| Setting | Value |
|---|---|
| Source | repo `baranberkay96/qwenpaw-railway`, root `/services/qwenpaw` (Dockerfile) |
| Start | image ENTRYPOINT `/app/railway/railway-entrypoint.sh` (no start command override) |
| Healthcheck | `GET /api/version` on `PORT=8088`, timeout 600 s. Public by design and answered as soon as uvicorn listens, which is after the app's startup hook ran. Upstream's readiness probe `/api/healthz` cannot be used: it sits behind the login (verified: 401 without a token, 200 with one). |
| Public domain | yes, target port 8088 |
| TCP proxy | none |
| Volume | `/data` (`QWENPAW_WORKING_DIR=/data/working`, `QWENPAW_SECRET_DIR=/data/working.secret`, `QWENPAW_BACKUP_DIR=/data/working.backups`, set in the Dockerfile). Upstream's Docker docs use three volumes at `/app/working*`; Railway gives one volume per service. |
| Restart policy | `ALWAYS` (always-on agent; a clean exit must restart too) |
| Replicas | 1 (single writer on the volume; two instances would poll the same bots twice) |
| Draining | `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=30`; a native SIGTERM test shut the app down cleanly in about 1 s |

### What the wrapper does on every start

| Step | Effect |
|---|---|
| `QWENPAW_AUTH_ENABLED` | Always exported as `true`; a different value is logged and ignored. |
| `FORWARDED_ALLOW_IPS` | Unset (logged if present). uvicorn would otherwise take the client address from `X-Forwarded-For`, and a forged `127.0.0.1` would skip the login. |
| First boot (no `config.json`) | Writes `{"agents":{"language": QWENPAW_AGENT_LANGUAGE}}`, runs `qwenpaw init --defaults --accept-security` (what upstream's entrypoint runs), then sets the default agent's own `language` in its `agent.json` (upstream leaves it at `zh` in this path). On failure the seed is removed and the boot stops, so the next start retries cleanly. |
| Login | No account yet: creates it from `QWENPAW_AUTH_USERNAME` / `QWENPAW_AUTH_PASSWORD`. Variables changed since the last applied pair: username and password are reset to them and all sessions are signed out (JWT secret rotated). Unchanged: nothing is touched, so a password changed in the Console stays. The state file stores a salted HMAC of the applied pair, not the password. **Fails closed**: empty username, password under 12 characters, or an unreadable `auth.json` stop the boot (upstream treats an unreadable `auth.json` as "no account" and serves the API without login). |
| `QWENPAW_TRUSTED_PROXIES` | Validated (`/0` and non-IP entries are dropped) and written to `security.trusted_proxies` in `config.json`. |
| Channel variables | See below. Written to `workspaces/default/agent.json` (mode 0600). |
| Environment | `QWENPAW_AUTH_USERNAME`, `QWENPAW_AUTH_PASSWORD`, `QWENPAW_TRUSTED_PROXIES`, `QWENPAW_AGENT_LANGUAGE` and all channel credentials are unset before the app starts, so `env` in the agent's shell tool or a skill script does not print them. |
| `LLAMA_ARG_THREADS`, `OMP_NUM_THREADS` | When empty: the container's CPU quota from `/sys/fs/cgroup/cpu.max` (v1 fallback, then `nproc`), capped at 8 (Rule 8.15). llama.cpp's `llama-server`, which QwenPaw Local spawns, reads `LLAMA_ARG_THREADS`. |
| `/data` check | Logs a warning when `/data` is not a mounted volume. |

### Chat channels from variables

| Channel | Variables (all of a row are needed) | Transport |
|---|---|---|
| Telegram | `TELEGRAM_BOT_TOKEN` | long polling |
| Discord | `DISCORD_BOT_TOKEN` | gateway WebSocket |
| Slack | `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` | Socket Mode |
| DingTalk | `DINGTALK_CLIENT_ID` + `DINGTALK_CLIENT_SECRET` | Stream mode |
| Feishu / Lark | `FEISHU_APP_ID` + `FEISHU_APP_SECRET` (+ optional `FEISHU_DOMAIN` = `lark`) | WebSocket long connection |
| QQ | `QQ_APP_ID` + `QQ_CLIENT_SECRET` | WebSocket |
| WeCom | `WECOM_BOT_ID` + `WECOM_SECRET` | WebSocket |

All of them connect outwards, so no extra ports or domains are needed. Variable names follow upstream's own channel naming (`*_BOT_TOKEN`, `*_CLIENT_ID`, ...); upstream's running app does not read them itself, so the wrapper writes them to the agent config.

Rules:
- When all variables of a channel are set, the channel is enabled with those credentials on every start (the variables win).
- The first time a channel is taken over from variables, **access control is switched on** for direct and group messages: an unknown sender gets a reply with their ID and lands in **Control → Channels → Pending approvals**; nothing reaches the agent until you approve them. Upstream's default is open to everyone who finds the bot, which for an agent with shell and file tools means anyone could use it. If you switch access control off in the Console, it stays off.
- Removing the variables of a channel the template enabled disables it and clears its credentials. Channels you configure in the Console are never touched.
- Partial sets (e.g. Slack bot token without app token) are logged and not applied.

### Variables

None is required at deploy.

| Variable | Default | Notes |
|---|---|---|
| `PORT` | `8088` | Healthcheck port = app port = domain target port (Rule 8.1); upstream's default port |
| `QWENPAW_AUTH_USERNAME` | `paw-${{secret(10, "…")}}` | Random so that nobody can lock the owner out by failing five logins against a guessable name |
| `QWENPAW_AUTH_PASSWORD` | `${{secret(32)}}` | Applied when it changes (see above) |
| `QWENPAW_AGENT_LANGUAGE` | `en` | First boot only; `en`, `zh`, `ru`, `id`; anything else falls back to `en` with a log line |
| `TZ` | `UTC` | Stored as `user_timezone` on the first boot (checked natively); later in Console settings |
| `QWENPAW_TOOL_GUARD_ENABLED` | `true` | Upstream variable; forces the guard on regardless of the Console toggle; empty lets the Console decide |
| `QWENPAW_TOOL_GUARD_DENIED_TOOLS` | empty | Upstream variable; e.g. `execute_shell_command` to remove shell access |
| `QWENPAW_TELEMETRY_DISABLED` | `true` | Upstream variable. Upstream asks for consent interactively and, with `--defaults`, sends an install ping plus daily activity pings (v2.2.2). Nobody sees that prompt on Railway, so it is off by default |
| `QWENPAW_DISABLED_CHANNELS` | `imessage,sip` | Upstream variable (image default `imessage`); SIP needs inbound UDP |
| `QWENPAW_TRUSTED_PROXIES` | private + CGNAT ranges | So the login rate limiter sees client IPs instead of Railway's edge (otherwise 50 wrong logins per minute from anyone lock every user out for 15 minutes); assumption, see Open questions |
| `TELEGRAM_BOT_TOKEN` … `WECOM_SECRET` | empty | 13 optional channel variables, see above |
| `LLAMA_ARG_THREADS` | empty | Override for local-model threads |
| `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` | `30` | Graceful stop window |

Not set on purpose: LLM provider keys (QwenPaw has no provider-key environment variables; keys are entered in Settings → Models and stored encrypted in `working.secret/`, which the agent's file tools are blocked from); `QWENPAW_CORS_ORIGINS` (same-origin console); `QWENPAW_OPENAPI_DOCS` (keeps `/docs` off); `security.sandbox_enabled` (stays upstream's `false`, see Security model).

Why no LLM key is needed at deploy: `qwenpaw init --defaults` with no provider prints "No LLM provider configured" and finishes, and the app boots without a model (verified natively with the v2.2.2 wheel). The Console then walks through provider setup.

## Security model

- **Login**: required on every `/api/*` route except upstream's public ones (`/api/version`, `/api/auth/status`, `/api/auth/login`, `/api/auth/register` once an account exists returns 403, UI language and upload-limit settings, frontend plugin assets). The Console SPA itself is static. Verified natively from a non-loopback address: `/api/skills`, `/api/agents`, `/api/healthz` return 401; a forged `X-Forwarded-For: 127.0.0.1` still gets 401; a wrong password gets 401; the right one returns a bearer token that opens the API.
- **API**: `POST /api/auth/login` with the username and password returns a token (`expires_in` in seconds, `-1` for a long-lived token); send it as `Authorization: Bearer {token}`.
- **Built-in terminal and shell tool**: v2.2.2 adds an authenticated terminal in Chat, and the agent has an `execute_shell_command` tool. Both run **as root inside the container**, with access to the volume and the network. Railway has no Docker-in-Docker or privileged containers, and QwenPaw's kernel sandbox needs bubblewrap with user namespaces or Landlock, neither verified on Railway, so `security.sandbox_enabled` stays off (upstream default). What protects you: the login, Tool Guard (forced on; risky calls wait for approval in the Console, catastrophic commands are denied), File Guard (agent file tools cannot open `working.secret/`), the Skill Scanner (upstream default `warn`), and channel access control. What does not: a prompt-injected agent that gets a shell command approved can read anything in the container, including `/proc/1/environ` (the container's initial environment, which holds all Railway variables) and the master key that decrypts stored provider keys. Approve shell commands like you would on your own server, or set `QWENPAW_TOOL_GUARD_DENIED_TOOLS=execute_shell_command`.
- **Loopback bypass**: QwenPaw trusts `127.0.0.1`/`::1` without login (its CLI and skills call the local API). Inside the container that means any process, including the agent's shell, can call the API. This is upstream's design and the reason nothing proxies inside the container.

## First login

1. Wait for the deployment to turn healthy (the first deploy builds a small layer on a ~1 GB image and initialises the volume).
2. Open the public URL. Sign in with `QWENPAW_AUTH_USERNAME` and `QWENPAW_AUTH_PASSWORD` from the service's Variables tab.
3. **Settings → Models**: add a provider (DashScope, OpenAI, Anthropic, Gemini, OpenRouter, DeepSeek, any OpenAI- or Anthropic-compatible endpoint, ...) and choose the default model.
4. Say hello in **Chat**. The default agent starts with upstream's bootstrap conversation (who you are, how it should behave), then deletes `BOOTSTRAP.md`.
5. Chat apps: set the channel variables and redeploy, or use **Control → Channels**. DM the bot, then approve yourself under **Pending approvals**.

## Improvements over market templates

1. **Current release, pinned twice**: v2.2.2 by tag and index digest (market: v1.1.0 and v2.2.1, tag only).
2. **App is the main process**: logs in Railway's log view and any app exit restarts the container (market templates keep upstream's supervisord arrangement, where a dead app leaves a healthy-looking container).
3. **Login that cannot be switched off, cannot be locked out by guessing the name, and can be rotated from Railway**: generated random username and password, applied again whenever the variables change, Console password changes kept otherwise (market: none at all, a fixed `admin` name, or a first-boot-only password).
4. **Fails closed** when `auth.json` is unreadable, where upstream would serve the API without login.
5. **Credentials kept out of the app's environment** after they are stored (market templates leave the login password in the agent's environment).
6. **Consistent agent language**: persona files and the agent's own `language` follow `QWENPAW_AGENT_LANGUAGE` (market: Chinese persona, or English persona with a Chinese agent setting).
7. **Seven chat apps from variables** with approval-based access control on by default; removing the variables cleanly disables them (market: Console only, upstream's open-to-everyone default).
8. **Per-client login rate limiting** through `security.trusted_proxies`, and a guard against `FORWARDED_ALLOW_IPS`.
9. **Telemetry off by default** because the consent prompt is never shown on Railway; documented switch to enable it.
10. **Shell tool allowed but guarded**: Tool Guard forced on, risk documented, one variable to remove shell access (one market template denies shell entirely; the others leave the guard to the Console).
11. **Local models will not stall on Railway's many-core hosts**: llama.cpp threads follow the CPU quota, capped at 8.
12. Desktop helpers hardened: Xvfb never listens on TCP, their logs are size-capped; iMessage and SIP hidden because they cannot work on Railway; warning when `/data` is not a volume.

## Resource estimate

Railway prices: RAM $10/GB-month, vCPU $20/vCPU-month, volume $0.15/GB-month.

| Service | Idle RAM / CPU | Typical RAM / CPU | Notes |
|---|---|---|---|
| QwenPaw | ~0.7-0.8 GB / 0.02-0.05 vCPU | 1.0-1.5 GB / 0.1-0.3 vCPU | The app alone measured 540 MB RSS idle in a native run (macOS arm64, v2.2.2 wheel, no X stack); Xvfb + Xfce + D-Bus add an estimated 150-250 MB. Chromium sessions add 300-600 MB while browsing. A local GGUF model adds its own size in RAM and is slow on CPU. |
| Volume | ~10 MB after init (measured) | 1-3 GB | Chats, memory indexes, media from chat apps, browser profile, backups; local models are 1-9 GB each |

Estimated monthly cost: **idle ≈ $8**, **typical ≈ $15-20**. LLM usage is billed by your provider.

Minimum plan: **Hobby**. Trial's 1 GB RAM per service is enough to boot but not for browser work. Hobby's 5 GB volume limit fits normal use; large local models need Pro.

## Verification results (2026-10-20, no Docker)

Docker was not used (host disk constraints). **The Dockerfile has not been built and the container has not been run.** Checks done instead:

| Check | How | Result |
|---|---|---|
| Image tag and digest | Docker Hub API, registry API (index + amd64 manifest + config blob) | `v2.2.2` exists, index `sha256:ba70a1e6…`, amd64 and arm64; config as described above |
| Tag → commit | `gh api repos/agentscope-ai/QwenPaw/commits/v2.2.2` | `5c56644a…`; `deploy/` files identical between v2.2.2 and the local `_upstream` copy (main, 16 commits ahead) |
| Scripts | `sh -n`, `dash -n`, `bash -n`, shellcheck 0.10 (`-s sh`), ruff (E,F,W,B,UP,S), `py_compile`, configparser parse of `supervisord.conf` | clean |
| `railway_setup.py` against the real QwenPaw 2.2.2 (PyPI wheel in a local venv, real `qwenpaw init`) | 20 scenarios: first boot in en/zh, unsupported language, re-boot, password variable change, Console password change kept, username rename, lost state file, short password, empty username, auth flag off, corrupt `auth.json`, init failure, missing CLI, all 7 channels on, token change, access control off kept, variable removal, partial Slack, Feishu `lark`, trusted proxies with junk/empty/absent | all as specified; upstream's `load_agent_config` validates the patched `agent.json` |
| Native app run on the generated volume | `qwenpaw app` bound to `fe80::1%lo0` (non-loopback for QwenPaw), curl | boots in seconds with no LLM key; `/api/version` 200; `/api/healthz`, `/api/skills`, `/api/agents` 401 unauthenticated, also with forged `X-Forwarded-For: 127.0.0.1`; register 403; wrong login 401; token login works; agent language `en`; fake Telegram token rejected by Telegram, app keeps serving; SIGTERM shutdown in ~1 s |
| Entrypoint flow | entrypoint with stubbed `supervisord` and app | auth flag forced, `FORWARDED_ALLOW_IPS` dropped, setup failure stops the boot, bad `PORT` stops the boot, app gets `--host 0.0.0.0 --port 8088`, no credential variables in the app environment |
| CPU thread cap | function extracted and run under dash with fake cgroup files | quota rounding, `max`, garbage, v1 fallback and cap of 8 all correct |
| Docker build, container run, desktop helpers, Linux-specific behaviour | Docker | **not run (unverified)** |

## Verification checklist

- [ ] Build log: the `RUN` check passes (`qwenpaw.app.auth` import, tools present); build finishes.
- [ ] Deploy log: `[railway] first boot: initialisation complete`, `login: account 'paw-…' created`, `desktop helpers starting`, `starting QwenPaw on 0.0.0.0:8088`; no `/data is not a mounted volume` warning; healthcheck `/api/version` passes.
- [ ] `curl https://{domain}/api/skills` → 401; with `-H "X-Forwarded-For: 127.0.0.1"` → 401; `curl -X POST https://{domain}/api/auth/register -H 'Content-Type: application/json' -d '{"username":"x","password":"y"}'` → 403.
- [ ] Sign in with the generated credentials; add a provider key; a chat reply arrives.
- [ ] Deploy logs show no `Ignoring proxy headers from untrusted source` warning after a login attempt (if they do, note the address and adjust `QWENPAW_TRUSTED_PROXIES`).
- [ ] Ask the agent to open a web page with the browser tool (headed mode uses Xvfb); check `railway ssh` → `tail /var/log/qwenpaw-desktop/*.log` for Xfce/D-Bus errors.
- [ ] Telegram: set `TELEGRAM_BOT_TOKEN`, redeploy, DM the bot → pending-approval reply in English; approve in Control → Channels; the next message is answered.
- [ ] Persistence: tell the agent a fact, create a cron job, redeploy; the fact is remembered and the job still runs; provider key still works.
- [ ] Change `QWENPAW_AUTH_PASSWORD`, redeploy: old sessions are signed out, the new password works.
- [ ] `railway ssh`: `tr '\0' '\n' < /proc/$(pgrep -of "qwenpaw app")/environ | grep -c AUTH_PASSWORD` → 0. The deploy log line `starting QwenPaw … (… N local-model threads)` shows N ≤ 8.
- [ ] Restart test: `railway ssh` → `kill $(pgrep -of "qwenpaw app")`; the deployment restarts by itself and comes back healthy.

## Open questions

- **The image has never been built or run.** The first Railway build is the first build. Likely failure points: the build-time `qwenpaw.app.auth` import (should behave like `qwenpaw auth reset-password`, which imports the same module) and the Xfce session under supervisord without upstream's exact environment.
- `QWENPAW_TRUSTED_PROXIES` assumes Railway's edge connects from a private or CGNAT address and appends the client to `X-Forwarded-For` (or sets `X-Real-IP`). If not, QwenPaw ignores the headers (logged) and rate-limits per edge IP, which is upstream's behaviour. Not verified on Railway.
- RAM figures are estimates built on one native measurement without the X stack.
- `LLAMA_ARG_THREADS` assumes the llama.cpp build QwenPaw downloads reads `LLAMA_ARG_*` environment variables (recent llama.cpp does); not exercised.
- Access-control approvals and real chat replies were not exercised end to end (no real bot tokens or LLM key).
- Whether QwenPaw's optional kernel sandbox (Landlock fallback) works on Railway's kernel was not tested; it stays off.
