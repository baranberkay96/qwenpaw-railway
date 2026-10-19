#!/usr/bin/env python3
"""Railway setup for QwenPaw. railway-entrypoint.sh runs it before the app.

Every boot, in this order:

1. First boot only: seed the agent language into config.json, then run
   upstream's non-interactive ``qwenpaw init --defaults --accept-security``
   (the same command upstream's Docker entrypoint runs).
2. Login: create QwenPaw's single account from QWENPAW_AUTH_USERNAME and
   QWENPAW_AUTH_PASSWORD, or apply them again when they changed since the
   last boot. Exits 1 (the app is not started) without a working login.
3. ``security.trusted_proxies`` in config.json from QWENPAW_TRUSTED_PROXIES.
4. Chat channels of the default agent (its agent.json) from channel
   variables, with access control switched on when a channel is first
   taken over from variables.

Bookkeeping lives in ``$QWENPAW_SECRET_DIR/railway-template-state.json``
(salted digests only, no clear-text credentials).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

SUPPORTED_LANGUAGES = ("en", "zh", "ru", "id")
DEFAULT_LANGUAGE = "en"
MIN_PASSWORD_LENGTH = 12
STATE_FILE_NAME = "railway-template-state.json"
INIT_COMMAND = ("qwenpaw", "init", "--defaults", "--accept-security")
INIT_TIMEOUT_SECONDS = 600
FEISHU_DOMAINS = ("feishu", "lark")

# agent.json channel key -> ((config field, Railway variable), ...).
# All listed variables of a channel must be set for it to be enabled.
CHANNEL_VARIABLES: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "telegram": (("bot_token", "TELEGRAM_BOT_TOKEN"),),
    "discord": (("bot_token", "DISCORD_BOT_TOKEN"),),
    "slack": (
        ("bot_token", "SLACK_BOT_TOKEN"),
        ("app_token", "SLACK_APP_TOKEN"),
    ),
    "dingtalk": (
        ("client_id", "DINGTALK_CLIENT_ID"),
        ("client_secret", "DINGTALK_CLIENT_SECRET"),
    ),
    "feishu": (
        ("app_id", "FEISHU_APP_ID"),
        ("app_secret", "FEISHU_APP_SECRET"),
    ),
    "qq": (
        ("app_id", "QQ_APP_ID"),
        ("client_secret", "QQ_CLIENT_SECRET"),
    ),
    "wecom": (
        ("bot_id", "WECOM_BOT_ID"),
        ("secret", "WECOM_SECRET"),
    ),
}


class SetupError(Exception):
    """A problem that must stop the boot (the app is not started)."""


def _build_logger() -> logging.Logger:
    """Own handler, no propagation: importing qwenpaw reconfigures logging."""
    logger = logging.getLogger("railway.setup")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[railway] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


LOGGER = _build_logger()


def log(message: str) -> None:
    LOGGER.info(message)


def env(name: str) -> str:
    return os.environ.get(name, "").strip()


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return data


def write_json_atomic(path: Path, data: Dict[str, Any], mode: int) -> None:
    """Replace *path* atomically, keeping the mode of an existing file."""
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        pass
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def directory_from_env(name: str) -> Path:
    value = env(name)
    if not value:
        raise SetupError(f"{name} is not set (the Dockerfile sets it)")
    return Path(value).expanduser().resolve()


# --- 1. first boot ---------------------------------------------------------


def agent_language() -> str:
    language = env("QWENPAW_AGENT_LANGUAGE").lower() or DEFAULT_LANGUAGE
    if language in SUPPORTED_LANGUAGES:
        return language
    log(
        f"QWENPAW_AGENT_LANGUAGE '{language}' is not shipped upstream "
        f"(choose one of {', '.join(SUPPORTED_LANGUAGES)}); "
        f"using '{DEFAULT_LANGUAGE}'",
    )
    return DEFAULT_LANGUAGE


def set_default_agent_language(working_dir: Path, language: str) -> None:
    """Align the default agent's own ``language`` with its persona files.

    When config.json already lists the default agent (it always does after
    seeding), upstream creates its agent.json from a fallback profile whose
    ``language`` defaults to "zh", whatever ``agents.language`` says. That
    field drives memory prompts and the replies channels send to unknown
    senders, so it is set once here, right after the first init.
    """
    agent_path = default_agent_file(working_dir / "config.json", working_dir)
    agent = read_json(agent_path)
    if agent.get("language") == language:
        return
    write_json_atomic(agent_path, {**agent, "language": language}, 0o600)
    log(f"first boot: default agent language set to '{language}'")


def first_boot_init(working_dir: Path) -> None:
    """Seed the persona language, then run upstream's non-interactive init.

    Upstream copies the persona files (AGENTS.md, SOUL.md, PROFILE.md, ...)
    once, in ``agents.language`` (default "zh"), and never replaces them
    afterwards, so the language has to be in config.json before init runs.
    """
    config_path = working_dir / "config.json"
    if config_path.exists():
        return
    language = agent_language()
    log(f"first boot: initialising {working_dir} (agent language '{language}')")
    write_json_atomic(config_path, {"agents": {"language": language}}, 0o644)
    try:
        result = subprocess.run(
            INIT_COMMAND,
            check=False,
            timeout=INIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        config_path.unlink(missing_ok=True)
        raise SetupError(f"'{' '.join(INIT_COMMAND)}' did not run: {exc}") from exc
    if result.returncode != 0:
        # Without config.json the next boot retries the whole first boot.
        config_path.unlink(missing_ok=True)
        raise SetupError(
            f"'{' '.join(INIT_COMMAND)}' exited with {result.returncode}",
        )
    run_optional(
        "default agent language", set_default_agent_language, working_dir, language
    )
    log("first boot: initialisation complete")


# --- state ------------------------------------------------------------------


def load_state(path: Path) -> Dict[str, Any]:
    try:
        return read_json(path)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        log(f"ignoring unreadable {path.name} ({exc}); it is rebuilt now")
        return {}


def credential_digest(salt: str, *parts: str) -> str:
    message = "\0".join(parts).encode("utf-8")
    return hmac.new(salt.encode("ascii"), message, hashlib.sha256).hexdigest()


# --- 2. login ----------------------------------------------------------------


def login_variables() -> Tuple[str, str]:
    username = env("QWENPAW_AUTH_USERNAME")
    password = env("QWENPAW_AUTH_PASSWORD")
    if not username:
        raise SetupError(
            "QWENPAW_AUTH_USERNAME is empty. The template generates it; "
            "the console must not run without a login.",
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SetupError(
            f"QWENPAW_AUTH_PASSWORD is empty or shorter than "
            f"{MIN_PASSWORD_LENGTH} characters. The template generates one.",
        )
    return username, password


def load_auth_module() -> Any:
    try:
        from qwenpaw.app import auth as qwenpaw_auth  # type: ignore
    except Exception as exc:  # any import failure must stop the boot
        raise SetupError(f"cannot import qwenpaw.app.auth: {exc!r}") from exc
    return qwenpaw_auth


def load_auth_data(qwenpaw_auth: Any) -> Dict[str, Any]:
    data = qwenpaw_auth._load_auth_data()  # pylint: disable=protected-access
    if data.get("_auth_load_error"):
        # Upstream treats an unreadable auth.json like "no account yet",
        # which leaves the API open. Fail closed instead.
        raise SetupError(
            "auth.json in QWENPAW_SECRET_DIR exists but cannot be read. "
            "Restore it from a backup or delete it to recreate the login.",
        )
    return data


def password_matches(qwenpaw_auth: Any, user: Dict[str, Any], password: str) -> bool:
    return bool(
        user.get("password_hash")
        and user.get("password_salt")
        and qwenpaw_auth.verify_password(
            password,
            user["password_hash"],
            user["password_salt"],
        ),
    )


def replace_login(
    qwenpaw_auth: Any, data: Dict[str, Any], username: str, password: str
) -> None:
    """Set username and password; rotating jwt_secret signs out all sessions."""
    pw_hash, pw_salt = qwenpaw_auth._hash_password(password)  # pylint: disable=protected-access
    user = {
        **data["user"],
        "username": username,
        "password_hash": pw_hash,
        "password_salt": pw_salt,
    }
    updated = {**data, "user": user, "jwt_secret": secrets.token_hex(32)}
    qwenpaw_auth._save_auth_data(updated)  # pylint: disable=protected-access


def sync_login(state: Dict[str, Any]) -> Dict[str, Any]:
    """Make sure the account exists and follows the Railway variables.

    The variables are applied when they change. A password changed in the
    Console is kept until the variables change again.
    """
    username, password = login_variables()
    qwenpaw_auth = load_auth_module()
    data = load_auth_data(qwenpaw_auth)
    login_state = state.get("login") or {}
    salt = login_state.get("salt") or secrets.token_hex(16)
    digest = credential_digest(salt, username, password)
    user = data.get("user")

    if not user:
        if qwenpaw_auth.register_user(username, password) is None:
            raise SetupError("QwenPaw refused to create the login account")
        log(f"login: account '{username}' created")
    elif login_state.get("digest") == digest:
        log(f"login: account '{user.get('username')}' unchanged")
    elif user.get("username") == username and password_matches(
        qwenpaw_auth,
        user,
        password,
    ):
        log(f"login: account '{username}' already matches the variables")
    else:
        replace_login(qwenpaw_auth, data, username, password)
        log(
            f"login: account updated from the variables (user '{username}'); "
            "existing sessions were signed out",
        )

    check = load_auth_data(qwenpaw_auth).get("user") or {}
    if not check.get("username") or not check.get("password_hash"):
        raise SetupError("login account is missing after setup")
    return {**state, "login": {"salt": salt, "digest": digest}}


# --- 3. trusted proxies -----------------------------------------------------


def parse_networks(raw: str) -> List[str]:
    networks: List[str] = []
    for entry in (part for part in re.split(r"[\s,]+", raw) if part):
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            log(f"QWENPAW_TRUSTED_PROXIES: '{entry}' is not an IP or CIDR, skipped")
            continue
        if network.prefixlen == 0:
            log(f"QWENPAW_TRUSTED_PROXIES: '{entry}' would trust everyone, skipped")
            continue
        if str(network) not in networks:
            networks.append(str(network))
    return networks


def apply_trusted_proxies(config_path: Path) -> None:
    """The variable is authoritative while it exists (empty = trust none)."""
    if "QWENPAW_TRUSTED_PROXIES" not in os.environ:
        return
    networks = parse_networks(env("QWENPAW_TRUSTED_PROXIES"))
    config = read_json(config_path)
    security = dict(config.get("security") or {})
    if security.get("trusted_proxies") == networks:
        return
    security["trusted_proxies"] = networks
    write_json_atomic(config_path, {**config, "security": security}, 0o644)
    log(f"security.trusted_proxies = {networks}")


# --- 4. chat channels -------------------------------------------------------


def default_agent_file(config_path: Path, working_dir: Path) -> Path:
    config = read_json(config_path)
    profiles = (config.get("agents") or {}).get("profiles") or {}
    default = profiles.get("default") or {}
    workspace = default.get("workspace_dir") or str(
        working_dir / "workspaces" / "default",
    )
    return Path(workspace).expanduser() / "agent.json"


def optional_channel_fields(key: str) -> Dict[str, str]:
    if key != "feishu" or not env("FEISHU_DOMAIN"):
        return {}
    domain = env("FEISHU_DOMAIN").lower()
    if domain in FEISHU_DOMAINS or domain.startswith(("http://", "https://")):
        return {"domain": domain}
    log("FEISHU_DOMAIN must be 'feishu', 'lark' or an http(s) URL; ignored")
    return {}


def channel_update(
    key: str, current: Dict[str, Any], managed: bool
) -> Optional[Dict[str, Any]]:
    """New channel config, or None when the variables do not manage it."""
    fields = CHANNEL_VARIABLES[key]
    values = {field: env(variable) for field, variable in fields}
    present = [variable for field, variable in fields if values[field]]
    if len(present) == len(fields):
        updated = {**current, **values, **optional_channel_fields(key)}
        updated["enabled"] = True
        if not managed:
            # Unknown senders get their ID and wait for approval in the
            # Console (Control > Channels > access control).
            updated["access_control_dm"] = True
            updated["access_control_group"] = True
        return updated
    if present:
        missing = [variable for field, variable in fields if not values[field]]
        log(f"channel {key}: also set {', '.join(missing)} to enable it")
    if managed:
        cleared = {field: "" for field, _ in fields}
        return {**current, **cleared, "enabled": False}
    return None


def apply_channels(agent_path: Path, state: Dict[str, Any]) -> Dict[str, Any]:
    if not agent_path.exists():
        log(f"channels: {agent_path} not found yet; variables apply on the next boot")
        return state
    agent = read_json(agent_path)
    channels = dict(agent.get("channels") or {})
    managed = dict(state.get("channels") or {})
    for key in CHANNEL_VARIABLES:
        current = dict(channels.get(key) or {})
        updated = channel_update(key, current, bool(managed.get(key)))
        if updated is None:
            continue
        if updated.get("enabled"):
            managed[key] = True
            if updated != current:
                verb = "updated" if current.get("enabled") else "enabled"
                log(f"channel {key}: {verb} from variables")
        else:
            managed.pop(key, None)
            log(f"channel {key}: variables removed, channel disabled")
        channels[key] = updated
    if channels != (agent.get("channels") or {}):
        write_json_atomic(agent_path, {**agent, "channels": channels}, 0o600)
    return {**state, "channels": managed}


# --- main -------------------------------------------------------------------


def run_optional(step: str, func: Callable[..., Any], *args: Any) -> Any:
    """Run a non-critical step; a failure is logged and the boot goes on."""
    try:
        return func(*args)
    except Exception as exc:  # pylint: disable=broad-except
        log(f"{step} skipped: {type(exc).__name__}: {exc}")
        return None


def main() -> int:
    try:
        if env("QWENPAW_AUTH_ENABLED").lower() != "true":
            raise SetupError("QWENPAW_AUTH_ENABLED must be 'true'")
        working_dir = directory_from_env("QWENPAW_WORKING_DIR")
        secret_dir = directory_from_env("QWENPAW_SECRET_DIR")
        state_path = secret_dir / STATE_FILE_NAME
        config_path = working_dir / "config.json"

        first_boot_init(working_dir)
        state = sync_login(load_state(state_path))
        write_json_atomic(state_path, state, 0o600)

        run_optional("trusted proxies", apply_trusted_proxies, config_path)
        agent_path = run_optional(
            "channels",
            default_agent_file,
            config_path,
            working_dir,
        )
        if agent_path is not None:
            new_state = run_optional("channels", apply_channels, agent_path, state)
            if new_state is not None and new_state != state:
                write_json_atomic(state_path, new_state, 0o600)
    except SetupError as exc:
        log(f"FATAL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
