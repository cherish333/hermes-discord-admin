"""discord_admin tool — Discord REST API v10 wrapper.

Single tool + action dispatch (OpenClaw-style).
No dependency on gateway.platforms.discord — reads bot token directly from env.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import error as urlerror
from urllib import request as urlrequest

logger = logging.getLogger(__name__)

API_BASE = "https://discord.com/api/v10"

# Channel type codes per Discord API
CHANNEL_TYPES = {
    "text": 0,
    "voice": 2,
    "category": 4,
    "announcement": 5,
    "stage": 13,
    "forum": 15,
}

# ---------------------------------------------------------------------------
# Token / env loading
# ---------------------------------------------------------------------------

def _load_env_file() -> None:
    """Load ~/.hermes/.env into os.environ if not already loaded.

    Hermes' main process already does this on startup; we defend against
    standalone / test invocation.
    """
    if os.environ.get("DISCORD_BOT_TOKEN"):
        return
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception as exc:
        logger.debug("failed to load .env: %s", exc)


def _get_token() -> Optional[str]:
    _load_env_file()
    return os.environ.get("DISCORD_BOT_TOKEN")


def _get_default_guild_id() -> Optional[str]:
    _load_env_file()
    # HOME_CHANNEL is documented as the guild id in this deployment
    return os.environ.get("DISCORD_GUILD_ID") or os.environ.get("DISCORD_HOME_CHANNEL")


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _http(method: str, path: str, body: Optional[dict] = None) -> Dict[str, Any]:
    """Call Discord REST; return {ok, status, data, error}.

    Never raises — always returns a dict so the agent can reason about it.
    """
    token = _get_token()
    if not token:
        return {"ok": False, "status": 0, "error": "DISCORD_BOT_TOKEN not set in ~/.hermes/.env"}

    url = f"{API_BASE}{path}"
    data_bytes = None
    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "hermes-discord-admin/0.1 (+https://github.com/cherish333/hermes-discord-admin)",
    }
    if body is not None:
        data_bytes = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urlrequest.Request(url, data=data_bytes, method=method, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8") or "null"
            return {"ok": True, "status": resp.status, "data": json.loads(raw) if raw != "null" else None}
    except urlerror.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err_json = json.loads(err_body) if err_body else {}
        except Exception:
            err_json = {"raw": "<unreadable>"}
        return {"ok": False, "status": e.code, "error": err_json}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def _action_channel_list(args: Dict[str, Any]) -> Dict[str, Any]:
    guild_id = args.get("guild_id") or _get_default_guild_id()
    if not guild_id:
        return {"ok": False, "error": "guild_id required (or set DISCORD_GUILD_ID)"}
    res = _http("GET", f"/guilds/{guild_id}/channels")
    if not res["ok"]:
        return res
    slim = [
        {
            "id": c["id"],
            "name": c.get("name"),
            "type": c.get("type"),
            "parent_id": c.get("parent_id"),
            "position": c.get("position"),
            "topic": c.get("topic"),
        }
        for c in (res["data"] or [])
    ]
    return {"ok": True, "count": len(slim), "channels": slim}


def _action_channel_create(args: Dict[str, Any]) -> Dict[str, Any]:
    guild_id = args.get("guild_id") or _get_default_guild_id()
    if not guild_id:
        return {"ok": False, "error": "guild_id required"}
    name = args.get("name")
    if not name:
        return {"ok": False, "error": "name required"}
    ch_type_str = (args.get("type") or "text").lower()
    if ch_type_str not in CHANNEL_TYPES:
        return {"ok": False, "error": f"type must be one of {list(CHANNEL_TYPES)}"}
    body = {"name": name, "type": CHANNEL_TYPES[ch_type_str]}
    if args.get("topic"):
        body["topic"] = args["topic"]
    if args.get("parent_id"):
        body["parent_id"] = args["parent_id"]
    if args.get("position") is not None:
        body["position"] = args["position"]
    if args.get("nsfw") is not None:
        body["nsfw"] = bool(args["nsfw"])
    return _http("POST", f"/guilds/{guild_id}/channels", body)


def _action_channel_edit(args: Dict[str, Any]) -> Dict[str, Any]:
    channel_id = args.get("channel_id")
    if not channel_id:
        return {"ok": False, "error": "channel_id required"}
    body: Dict[str, Any] = {}
    for key in ("name", "topic", "position", "nsfw", "parent_id"):
        if args.get(key) is not None:
            body[key] = args[key]
    if not body:
        return {"ok": False, "error": "no fields to edit (provide name/topic/position/nsfw/parent_id)"}
    return _http("PATCH", f"/channels/{channel_id}", body)


def _action_channel_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    channel_id = args.get("channel_id")
    if not channel_id:
        return {"ok": False, "error": "channel_id required"}
    if not args.get("confirm"):
        return {
            "ok": False,
            "error": "destructive action — set confirm=true to proceed",
            "hint": f"this will permanently delete channel {channel_id}",
        }
    return _http("DELETE", f"/channels/{channel_id}")


def _action_channel_send(args: Dict[str, Any]) -> Dict[str, Any]:
    channel_id = args.get("channel_id")
    content = args.get("content")
    if not channel_id or not content:
        return {"ok": False, "error": "channel_id and content required"}
    body = {"content": content}
    if args.get("tts"):
        body["tts"] = True
    res = _http("POST", f"/channels/{channel_id}/messages", body)
    if res["ok"] and isinstance(res.get("data"), dict):
        # Slim response — agent doesn't need the full message
        d = res["data"]
        return {"ok": True, "message_id": d.get("id"), "channel_id": d.get("channel_id")}
    return res


def _action_react(args: Dict[str, Any]) -> Dict[str, Any]:
    channel_id = args.get("channel_id")
    message_id = args.get("message_id")
    emoji = args.get("emoji")
    if not (channel_id and message_id and emoji):
        return {"ok": False, "error": "channel_id, message_id, emoji required"}
    # Unicode emoji must be URL-encoded; custom is name:id
    from urllib.parse import quote
    emoji_enc = quote(emoji, safe=":")
    return _http(
        "PUT",
        f"/channels/{channel_id}/messages/{message_id}/reactions/{emoji_enc}/@me",
    )


ACTIONS = {
    "channel_list": _action_channel_list,
    "channel_create": _action_channel_create,
    "channel_edit": _action_channel_edit,
    "channel_delete": _action_channel_delete,
    "channel_send": _action_channel_send,
    "react": _action_react,
}


# ---------------------------------------------------------------------------
# Tool entry
# ---------------------------------------------------------------------------

def handle_discord_admin(args: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch on 'action' field."""
    action = args.get("action")
    if not action:
        return {"ok": False, "error": f"action required; choose one of {sorted(ACTIONS)}"}
    fn = ACTIONS.get(action)
    if not fn:
        return {"ok": False, "error": f"unknown action '{action}'; valid: {sorted(ACTIONS)}"}
    try:
        return fn(args)
    except Exception as exc:
        logger.exception("discord_admin action %s failed", action)
        return {"ok": False, "error": f"internal error: {exc}"}


# ---------------------------------------------------------------------------
# Tool schema (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": sorted(ACTIONS.keys()),
            "description": (
                "Which operation to perform. "
                "channel_list: list channels in guild. "
                "channel_create: create new channel (requires name, optional type/topic/parent_id). "
                "channel_edit: update name/topic/position/nsfw/parent_id of channel_id. "
                "channel_delete: delete channel_id — requires confirm=true. "
                "channel_send: post content to channel_id. "
                "react: add emoji reaction to message_id in channel_id."
            ),
        },
        "guild_id": {
            "type": "string",
            "description": "Guild (server) ID. Defaults to $DISCORD_GUILD_ID or $DISCORD_HOME_CHANNEL.",
        },
        "channel_id": {"type": "string", "description": "Target channel ID."},
        "message_id": {"type": "string", "description": "Target message ID (for react)."},
        "name": {"type": "string", "description": "Channel name (channel_create / channel_edit)."},
        "type": {
            "type": "string",
            "enum": sorted(CHANNEL_TYPES.keys()),
            "description": "Channel type for channel_create. Default: text.",
        },
        "topic": {"type": "string", "description": "Channel topic (text channels)."},
        "parent_id": {"type": "string", "description": "Parent category ID."},
        "position": {"type": "integer", "description": "Sort position."},
        "nsfw": {"type": "boolean", "description": "Age-restrict the channel."},
        "content": {"type": "string", "description": "Message content (channel_send)."},
        "tts": {"type": "boolean", "description": "Send as text-to-speech."},
        "emoji": {
            "type": "string",
            "description": "Unicode emoji (e.g. '👍') or custom 'name:id' (react).",
        },
        "confirm": {
            "type": "boolean",
            "description": "Safety gate for destructive actions (channel_delete).",
        },
    },
    "required": ["action"],
}
