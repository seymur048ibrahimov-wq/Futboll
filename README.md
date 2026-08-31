# FootballAI V3 — Independent / 8-Country Expanded

Bookmaker odds are completely excluded from the prediction engine.

## 8 əsas ölkə + daxili yarışlar

V3 artıq yalnız 8 əsas liqanı deyil, həmin 8 ölkənin API-Football-da olan **senior kişi yarışlarını** da skan etmək üçün qurulub:

- 🇬🇧 England
- 🇪🇸 Spain
- 🇮🇹 Italy
- 🇩🇪 Germany
- 🇫🇷 France
- 🇳🇱 Netherlands
- 🇵🇹 Portugal
- 🇹🇷 Turkey

Primary competitions receive the highest priority. Major domestic leagues/cups are included below them. Additional senior domestic competitions can be discovered automatically.

Women, youth, reserve and development competitions are filtered out so they do not contaminate the main model.

API-Football coverage is season-dependent, so the live adapter discovers the currently available competitions rather than hard-coding every lower-division league ID. The provider currently lists 1,242 leagues/cups and notes that detailed coverage can vary by season/fixtures. (API-Football coverage)

## Prediction targets

- Primary: **1X2**
- Secondary: **Alt/Üst 0.5 → 6.5**
- BTTS
- Model agreement
- Data-quality / uncertainty checks
- Trap / NO SIGNAL filter
- Walk-forward backtest
- Probability calibration

## Data independence

No bookmaker odds are accepted as model input. The adapter only retrieves football data (fixtures/teams and, in the full data pipeline, form, standings, injuries, lineups and statistics).

## Files

- `config.py` — 8-country competition policy and thresholds
- `data/competition_filter.py` — senior competition filtering/priorities
- `data/api_adapter.py` — API-Football discovery + fixture adapter
- `models/` — prediction components
- `analysis/` — ranking, calibration, uncertainty and backtest

## Live API key

Create a `.env` from `.env.example` and set `API_FOOTBALL_KEY`. Never put the key directly in source code or send it in chat.

## Telegram bot — daily predictions

- `data/stats_provider.py` — builds full match features (form, xG-proxy, injuries,
  Elo) from live API-Football data for the predictor.
- `data/elo_store.py` — API-Football has no Elo endpoint, so V3 maintains its own
  Elo table in SQLite, updated from finished fixtures it scans.
- `bot/scanner.py` — runs one full daily scan across the 8 core countries and
  returns formatted, signal-filtered match cards (NO SIGNAL matches are dropped).
- `bot/telegram_bot.py` — posts the daily scan to a Telegram channel/group on a
  schedule, plus a manual `/scan` command for on-demand testing.

**Known limitation:** API-Football's standard plans don't expose true shot-based
xG. `stats_provider.py` uses each team's season average goals-for/against as a
proxy — documented in that file. Swap it for a real xG source later if you get
access to one; nothing else in the pipeline needs to change.

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env: API_FOOTBALL_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
python run_bot.py
```

`TELEGRAM_CHAT_ID` is the channel/group the bot posts to — add the bot as an
admin there first. `DAILY_SCAN_HOUR_UTC` (default 8) sets the daily post time.
Use `/scan` in a chat with the bot to trigger an immediate test run.
