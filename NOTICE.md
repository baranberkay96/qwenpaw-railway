# NOTICE: QwenPaw template

## Software deployed

| Component | Source | License | How it is used |
|---|---|---|---|
| QwenPaw | https://github.com/agentscope-ai/QwenPaw, tag `v2.2.2` (commit `5c56644a6e130762a236f8c946103e95a0a1eec8`); image `agentscope/qwenpaw:v2.2.2@sha256:ba70a1e6511cca8afa5728d145826b522f835c3405beb9be9e8baa8bad5b1b9b` | Apache License 2.0, Copyright 2025 The QwenPaw Authors (repository `LICENSE`) | Used unmodified as the base image. Third-party software inside the image (Debian packages, Chromium, Xfce, Node.js, Python dependencies) keeps its own licenses. |

QwenPaw, AgentScope and Qwen are names of their respective owners. This is a community template and is not affiliated with or endorsed by the QwenPaw or AgentScope teams.

## Adapted upstream material (Apache-2.0)

- `services/qwenpaw/railway/supervisord.conf`: the three desktop helper programs (system D-Bus, `Xvfb :1 -screen 0 1280x800x24`, `dbus-run-session startxfce4` after waiting for the X socket) follow upstream's `deploy/config/supervisord.conf.template` at `v2.2.2`. Changes: the app program is removed (the app is the container's main process), supervisord logs to stdout, helper logs are size-capped, Xvfb gets `-nolisten tcp`.
- `services/qwenpaw/railway/railway_setup.py`: runs upstream's own `qwenpaw init --defaults --accept-security` (as upstream's `deploy/entrypoint.sh` does) and calls upstream's `qwenpaw.app.auth` helpers to create or update the login. The script itself was written for this template; no upstream code is copied into it.

Apache License 2.0 text: https://github.com/agentscope-ai/QwenPaw/blob/v2.2.2/LICENSE

## Upstream files checked (tag `v2.2.2`, released 2026-10-15, checked 2026-10-20)

- `deploy/Dockerfile`, `deploy/entrypoint.sh`, `deploy/config/supervisord.conf.template`, `docker-compose.yml`, `pyproject.toml` (fetched with `gh api …/contents/<path>?ref=v2.2.2`; identical to the local `_upstream` copy of `main`)
- `website/public/docs/quickstart.en.md` (Docker), `security.en.md` (web authentication, Tool Guard, File Guard, sandbox), `channels.en.md`, `config.en.md` (environment variables, file layout)
- `src/qwenpaw/app/auth.py` (middleware, public paths, loopback bypass, trusted proxies, auto-registration), `app/routers/auth.py`, `app/rate_limiter.py`, `app/routers/healthz.py`, `app/_app.py` (lifespan, `/api/version`, telemetry), `cli/app_cmd.py`, `cli/init_cmd.py`, `cli/providers_cmd.py`, `app/migration.py`, `agents/templates.py`, `config/config.py` (channel, security and agent models, access-control migration), `config/utils.py`, `app/channels/base.py` and channel constructors, `security/secret_store.py`, `security/tool_guard/*`, `utils/telemetry.py`, `local_models/llamacpp.py`, `constant.py`
- Release notes: https://github.com/agentscope-ai/QwenPaw/releases/tag/v2.2.2

The PyPI wheel `qwenpaw==2.2.2` was installed in a local virtual environment to test the setup script and the app natively (see TEMPLATE.md); nothing from it is redistributed.

## Market templates and repositories reviewed (ideas only, nothing copied)

| Template / repo | License | Use |
|---|---|---|
| `qwenpaw` (image `agentscope/qwenpaw:v1.1.0`) | marketplace config only | Read for the starting point (single volume, port variables). |
| `qwenpaw-private-assistant` (image `agentscope/qwenpaw:v2.2.1`) | marketplace config only | Read for approach: `/data` layout for the three state directories, randomized username, Tool Guard forced on, `/api/version` healthcheck. No text copied. |
| `qwenpaw-1` / `RockinPaul/qwenpaw_railway_template` | MIT, Copyright (c) 2026 Paul Zarudnev | Read only. Its documented findings informed this template (no in-container proxy because of QwenPaw's loopback bypass, `0.0.0.0` instead of `::`, seeding `agents.language` before the first init). The code, scripts and prose here were written independently; no files or text were copied. |

All template files (TEMPLATE.md, template.json, README.md, this NOTICE, the Dockerfile and the Railway wrapper scripts) were written for this package.
