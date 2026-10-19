#!/bin/sh
# shellcheck shell=sh
# QwenPaw on Railway. Railway's init (podman-init) is PID 1; this script is
# its child and ends by exec'ing the app, so the container lives and dies
# with QwenPaw and Railway's restart policy covers crashes.
#
#  1. railway_setup.py: first-boot init with the chosen agent language, the
#     login account from variables (fails closed), trusted proxies, chat
#     channels from variables.
#  2. Desktop helpers from upstream's image (system D-Bus, Xvfb :1, Xfce)
#     under supervisord in the background, for the agent's headed browser
#     and desktop screenshots. Their logs stay in /var/log/qwenpaw-desktop.
#  3. exec `qwenpaw app` on 0.0.0.0:$PORT in the foreground.
set -eu

THREAD_CAP=8

log() {
    printf '[railway] %s\n' "$*" >&2
}

is_true() {
    case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
        true|1|yes|on) return 0 ;;
    esac
    return 1
}

# CPU quota of this container (cgroup v2, then v1), else nproc; capped.
# Railway hosts expose all host cores to nproc, while the service only gets
# a share of them; llama.cpp sized from nproc stalls (STANDARD Rule 8.15).
cpu_threads() {
    n=""
    if [ -r /sys/fs/cgroup/cpu.max ]; then
        read -r quota period < /sys/fs/cgroup/cpu.max || true
        case "${quota:-}:${period:-}" in
            *[!0-9:]*|:*|*:) ;;
            *) if [ "$period" -gt 0 ]; then n=$(( (quota + period - 1) / period )); fi ;;
        esac
    elif [ -r /sys/fs/cgroup/cpu/cpu.cfs_quota_us ] && [ -r /sys/fs/cgroup/cpu/cpu.cfs_period_us ]; then
        quota=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us)
        period=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)
        case "${quota}:${period}" in
            *[!0-9:]*|:*|*:) ;;
            *) if [ "$period" -gt 0 ]; then n=$(( (quota + period - 1) / period )); fi ;;
        esac
    fi
    if [ -z "$n" ]; then
        n=$(nproc 2>/dev/null || echo 1)
    fi
    case "$n" in
        ''|*[!0-9]*) n=1 ;;
    esac
    if [ "$n" -lt 1 ]; then n=1; fi
    if [ "$n" -gt "$THREAD_CAP" ]; then n=$THREAD_CAP; fi
    printf '%s' "$n"
}

PORT="${PORT:-8088}"
case "$PORT" in
    ''|*[!0-9]*) log "FATAL: PORT must be a port number, got '${PORT}'"; exit 1 ;;
esac
export PORT

# The login is not optional here: QwenPaw is an agent with shell, file and
# browser tools behind a public domain.
if [ -n "${QWENPAW_AUTH_ENABLED:-}" ] && ! is_true "${QWENPAW_AUTH_ENABLED}"; then
    log "QWENPAW_AUTH_ENABLED='${QWENPAW_AUTH_ENABLED}' ignored: this template always requires the login"
fi
export QWENPAW_AUTH_ENABLED=true

# uvicorn rewrites the client address from X-Forwarded-For for peers listed
# in FORWARDED_ALLOW_IPS. QwenPaw skips the login for loopback clients, so a
# forged "127.0.0.1" would get in. Keep uvicorn's default (trust loopback
# only); QwenPaw's own security.trusted_proxies is the safe knob.
if [ -n "${FORWARDED_ALLOW_IPS:-}" ]; then
    log "FORWARDED_ALLOW_IPS ignored: it would let forged proxy headers skip the login"
fi
unset FORWARDED_ALLOW_IPS

if [ -z "${LLAMA_ARG_THREADS:-}" ]; then
    LLAMA_ARG_THREADS=$(cpu_threads)
fi
export LLAMA_ARG_THREADS
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-$LLAMA_ARG_THREADS}"

if ! awk '$5 == "/data" { found = 1 } END { exit !found }' /proc/self/mountinfo 2>/dev/null; then
    log "WARNING: /data is not a mounted volume; chats, memory, login and keys are lost on redeploy"
fi

mkdir -p "$QWENPAW_WORKING_DIR" "$QWENPAW_BACKUP_DIR" "$QWENPAW_SECRET_DIR"
chmod 700 "$QWENPAW_SECRET_DIR"

cd /app
/app/venv/bin/python /app/railway/railway_setup.py

# The login and channel credentials are now stored on the volume. Keep them
# out of the app's environment, so `env` in the agent's shell tool and in
# skill scripts does not print them. (A root shell can still read the
# container's initial environment from /proc/1/environ; see TEMPLATE.md.)
unset QWENPAW_AUTH_USERNAME QWENPAW_AUTH_PASSWORD QWENPAW_AGENT_LANGUAGE \
    QWENPAW_TRUSTED_PROXIES \
    TELEGRAM_BOT_TOKEN DISCORD_BOT_TOKEN SLACK_BOT_TOKEN SLACK_APP_TOKEN \
    DINGTALK_CLIENT_ID DINGTALK_CLIENT_SECRET \
    FEISHU_APP_ID FEISHU_APP_SECRET FEISHU_DOMAIN \
    QQ_APP_ID QQ_CLIENT_SECRET WECOM_BOT_ID WECOM_SECRET

mkdir -p /var/log/qwenpaw-desktop
/usr/bin/supervisord -c /app/railway/supervisord.conf &
log "desktop helpers starting under supervisord (pid $!)"

LOG_LEVEL=$(printf '%s' "${QWENPAW_LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')
case "$LOG_LEVEL" in
    critical|error|warning|info|debug|trace) ;;
    *) log "QWENPAW_LOG_LEVEL '${LOG_LEVEL}' is not valid; using info"; LOG_LEVEL=info ;;
esac

export DISPLAY="${DISPLAY:-:1}"
log "starting QwenPaw on 0.0.0.0:${PORT} (login required, ${LLAMA_ARG_THREADS} local-model threads)"
# 0.0.0.0, not "::": uvicorn's single-worker asyncio socket on "::" is
# IPv6-only and Railway's healthcheck and edge connect over IPv4.
exec qwenpaw app --host 0.0.0.0 --port "$PORT" --log-level "$LOG_LEVEL"
