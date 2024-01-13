# vbot

Port of [vbot](https://github.com/vlang/discord-bot/blob/14fc41c4f3d626856fbe7e18c450bfea23d8047b/vbot.v) using https://github.com/DarpHome/discord.v

## Setup (V version)

1. Run `v install --git https://github.com/DarpHome/discord.v`
2. Create `config.json` with following:
```json
{
  "token": "MTA... (bot token)",
  "allowed_roles": []
}
```
3. Build the bot with `v .`
4. To create application commands, run `./vbot sync`
5. Run bot: `./vbot`

## Setup (Python version)

1. Run `python3 -m pip install hikari hikari-tanjun`
2. Create `config.json` with following:
```json
{
  "token": "MTA... (bot token)",
  "allowed_roles": []
}
```
3. Run bot: `python3 bot.py`