# Deploy and Host QwenPaw with Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/qwenpaw-v2-personal-ai-assistant?referralCode=20H68q)

Run QwenPaw, the open-source personal AI assistant from the AgentScope team, around the clock on Railway. It answers in its own web console and in Telegram, Discord, Slack, DingTalk, Feishu, QQ and WeCom, keeps long-term memory on a persistent volume, and runs skills and scheduled tasks while you are away.

## About Hosting QwenPaw

QwenPaw is a single Python service: a web console and REST API, agents with tools (shell, files, a real Chromium), skills, cron jobs, heartbeats and long-term memory. Self-hosting it needs a machine that never sleeps, durable storage for chats, memory and encrypted keys, and a login, because upstream ships with authentication off. This community template runs the official `agentscope/qwenpaw:v2.2.2` image with all state on one Railway volume, creates the login from generated credentials before the app starts and refuses to start without one, switches chat apps on from variables with sender approval, and sends logs to Railway.

## Common Use Cases

- A private assistant you message from Telegram, Discord, Slack, DingTalk or Feishu that remembers your preferences across conversations
- Scheduled briefings, reminders and recurring checks delivered to a chat, set up in plain language
- Research and document work: web browsing with a real Chromium, PDF and Office files, summaries saved to the workspace
- Several agents with their own personas, models and tools in one instance, reachable from phone and desktop
- A REST API that streams agent replies into your own scripts and services

## Dependencies for QwenPaw Hosting

- An API key for at least one model provider (DashScope, OpenAI, Anthropic, Gemini, OpenRouter, DeepSeek or any OpenAI- or Anthropic-compatible endpoint), entered in the console after the first login. Not needed to deploy.
- Optional bot credentials for the chat apps you want to use
- A Railway volume at `/data` (included)

### Deployment Dependencies

- QwenPaw repository and releases: https://github.com/agentscope-ai/QwenPaw
- Docker image: https://hub.docker.com/r/agentscope/qwenpaw
- Quickstart (Docker): https://github.com/agentscope-ai/QwenPaw/blob/v2.2.2/website/public/docs/quickstart.en.md
- Security (login, Tool Guard, File Guard, sandbox): https://github.com/agentscope-ai/QwenPaw/blob/v2.2.2/website/public/docs/security.en.md
- Channels (how to get bot credentials): https://github.com/agentscope-ai/QwenPaw/blob/v2.2.2/website/public/docs/channels.en.md
- Models and providers: https://github.com/agentscope-ai/QwenPaw/blob/v2.2.2/website/public/docs/models.en.md

### Implementation Details

| Service | Source | Purpose |
|---|---|---|
| QwenPaw | Dockerfile in `services/qwenpaw` on `agentscope/qwenpaw:v2.2.2` (pinned by digest) | Console, API, agents, tools, chat channels, cron and memory on port 8088; healthcheck `/api/version`; volume at `/data`; restart policy always |

**First login**

1. Open the service's public URL once the deployment is healthy.
2. Sign in with `QWENPAW_AUTH_USERNAME` and `QWENPAW_AUTH_PASSWORD` from the service's Variables tab. Both are generated at deploy; the username is random so nobody can lock you out by guessing it.
3. Go to **Settings → Models**, add your provider key and pick the default model.
4. Say hello in **Chat**. The agent first asks a few questions to set up its persona.
5. Chat apps: set `TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`, `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN`, `DINGTALK_CLIENT_ID` + `DINGTALK_CLIENT_SECRET`, `FEISHU_APP_ID` + `FEISHU_APP_SECRET`, `QQ_APP_ID` + `QQ_CLIENT_SECRET` or `WECOM_BOT_ID` + `WECOM_SECRET` and redeploy, or use **Control → Channels**. Message your bot, then approve yourself under **Pending approvals**: unknown senders cannot reach the agent until you approve them.

**Login**: change `QWENPAW_AUTH_PASSWORD` (or the username) and redeploy to reset it; all sessions are signed out. A password changed in the console is kept until you change the variable. The login cannot be switched off in this template.

**Language and timezone**: `QWENPAW_AGENT_LANGUAGE` (`en`, `zh`, `ru` or `id`) and `TZ` are applied on the first boot; later, change them in the console.

**Security notes**: the agent's shell tool and the console's terminal run as root inside the container with access to the volume and network; Railway offers no kernel sandbox for them. Tool Guard is forced on, so risky tool calls wait for your approval. Set `QWENPAW_TOOL_GUARD_DENIED_TOOLS=execute_shell_command` to remove shell access. Upstream's usage telemetry is off by default (`QWENPAW_TELEMETRY_DISABLED=true`).

**Scaling**: QwenPaw is a single-writer process with file-based state. Keep one replica and scale vertically. The template is sized for the Hobby plan (about 0.7-0.8 GB RAM idle, more while the browser runs).

**Pinning and upgrades**: the Dockerfile pins `agentscope/qwenpaw:v2.2.2` by tag and digest. To upgrade, change both to a newer release from https://github.com/agentscope-ai/QwenPaw/releases and redeploy; everything on the volume is kept. Download a backup from the console first.

### Why Deploy QwenPaw on Railway?

An assistant that lives in your chat apps is only useful if it is always online and never forgets. Railway keeps QwenPaw running with automatic restarts, a persistent volume, HTTPS, logs and SSH access, without a server to maintain. You pay for the RAM and CPU the assistant actually uses; model usage is billed by your provider.
