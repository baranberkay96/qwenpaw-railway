# QwenPaw v2.2.2 for Railway: the official image plus a small wrapper.
#
# Nothing of QwenPaw is rebuilt. The wrapper (railway/) points QwenPaw's
# three state directories at the Railway volume, creates the login account
# from variables before the app starts, applies optional chat-channel
# variables, and runs the app in the foreground on $PORT. Upstream's desktop
# helpers (D-Bus, Xvfb, Xfce) keep running under supervisord.
#
# Pinned by tag and by the multi-arch index digest of agentscope/qwenpaw:v2.2.2
# (published 2026-10-15). Upgrade: change both, read the release notes, and
# check that the qwenpaw.app.auth helpers imported below still exist.
FROM agentscope/qwenpaw:v2.2.2@sha256:ba70a1e6511cca8afa5728d145826b522f835c3405beb9be9e8baa8bad5b1b9b

# Upstream's Docker layout uses three volumes (/app/working,
# /app/working.secret, /app/working.backups). A Railway service gets one
# volume, so all three live under /data. QWENPAW_SECRET_DIR (login, encrypted
# provider keys and the master key that decrypts them) stays a sibling of the
# working directory: QwenPaw's File Guard blocks agent file tools there.
ENV QWENPAW_WORKING_DIR=/data/working \
    QWENPAW_SECRET_DIR=/data/working.secret \
    QWENPAW_BACKUP_DIR=/data/working.backups \
    PORT=8088 \
    DISPLAY=:1 \
    PYTHONUNBUFFERED=1

COPY --chmod=0755 railway/railway-entrypoint.sh /app/railway/railway-entrypoint.sh
COPY --chmod=0644 railway/railway_setup.py /app/railway/railway_setup.py
COPY --chmod=0644 railway/supervisord.conf /app/railway/supervisord.conf

# Fail the build (not the first boot) when the wrapper or the upstream
# helpers it relies on are missing. Importing qwenpaw creates a lock file in
# QWENPAW_WORKING_DIR; /data is removed again so the image ships it empty
# (the Railway volume is mounted there at runtime).
RUN sh -n /app/railway/railway-entrypoint.sh \
    && /app/venv/bin/python -m py_compile /app/railway/railway_setup.py \
    && /app/venv/bin/python -c "from qwenpaw.app.auth import _hash_password, _load_auth_data, _save_auth_data, register_user, verify_password" \
    && for tool in qwenpaw supervisord Xvfb dbus-daemon dbus-run-session startxfce4 awk; do \
           command -v "$tool" >/dev/null || { echo "missing in base image: $tool" >&2; exit 1; }; \
       done \
    && rm -rf /data

EXPOSE 8088

# Replaces the node base image's docker-entrypoint.sh and upstream's
# /entrypoint.sh (which runs the app under supervisord with logs in files).
ENTRYPOINT ["/app/railway/railway-entrypoint.sh"]
CMD []
