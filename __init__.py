"""hermes-discord-admin plugin — expose discord_admin tool.

Registers a single ``discord_admin`` tool with action-dispatch to:
  - channel_list     : list all channels in the guild
  - channel_create   : create a text/voice/category channel
  - channel_edit     : rename / update topic of a channel
  - channel_delete   : delete a channel (requires confirm=True)
  - channel_send     : send a message to a channel
  - react            : add emoji reaction to a message

All calls go through Discord REST API v10 with DISCORD_BOT_TOKEN.
"""

from __future__ import annotations

import logging

from .discord_admin import TOOL_SCHEMA, handle_discord_admin

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    """Plugin entry point called by PluginManager."""
    ctx.register_tool(
        name="discord_admin",
        toolset="discord",
        schema=TOOL_SCHEMA,
        handler=handle_discord_admin,
        requires_env=["DISCORD_BOT_TOKEN"],
        description="Manage Discord channels and messages (list/create/edit/delete/send/react).",
        emoji="💬",
    )
    logger.info("[discord-admin] tool registered")
