# hermes-discord-admin

Discord server administration plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Gives the agent a single `discord_admin` tool with 6 actions:

| action | what it does |
|---|---|
| `channel_list` | list all channels in the guild |
| `channel_create` | create a text/voice/category/forum channel |
| `channel_edit` | rename / update topic / move |
| `channel_delete` | delete a channel (requires `confirm=true`) |
| `channel_send` | post a message to a channel |
| `react` | add an emoji reaction to a message |

All calls go straight through **Discord REST API v10** with your bot token — no dependency on the running gateway bot instance, so the tool keeps working even if gateway reloads.

## Requirements

- Hermes Agent installed (uses the plugin system in `hermes_cli/plugins.py`)
- A Discord bot added to your guild with scopes: `bot` + permissions `Manage Channels`, `Send Messages`, `Add Reactions`, `Read Message History`
- `DISCORD_BOT_TOKEN` in `~/.hermes/.env`
- Optional: `DISCORD_GUILD_ID` in `~/.hermes/.env` (otherwise falls back to `DISCORD_HOME_CHANNEL`)

## Install

```bash
# 1. Clone beside your hermes-agent checkout
git clone https://github.com/cherish333/hermes-discord-admin ~/hermes-discord-admin

# 2. Symlink into the plugins directory (update-safe: git pull on hermes-agent won't touch this)
ln -s ~/hermes-discord-admin ~/.hermes/hermes-agent/plugins/discord-admin

# 3. Restart your gateway / CLI — Hermes auto-discovers plugins at startup
```

To upgrade:
```bash
cd ~/hermes-discord-admin && git pull
```
No re-symlinking needed.

## Usage (from agent)

```
discord_admin(action="channel_list")
discord_admin(action="channel_create", name="notes", type="text", topic="daily notes")
discord_admin(action="channel_send", channel_id="123...", content="hello")
discord_admin(action="react", channel_id="123...", message_id="456...", emoji="👍")
discord_admin(action="channel_delete", channel_id="123...", confirm=true)
```

## Safety

- `channel_delete` refuses without `confirm=true`
- Every action returns `{ok: bool, ...}` — the agent can reason about failures
- No bot-instance coupling: the gateway adapter is untouched

## License

MIT
