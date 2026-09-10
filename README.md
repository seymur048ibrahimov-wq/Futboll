# FootballAI V3 — Independent / 7-Country

Bookmaker odds are completely excluded from the prediction engine.

## 7 əsas ölkə

Canlı skaner football-data.org-un pulsuz planı üzərində qurulub və bu 7 ölkənin **top-flight liqalarını** əhatə edir (Türkiyə pulsuz planda olmadığı üçün çıxarılıb):

- 🇬🇧 England — Premier League
- 🇪🇸 Spain — La Liga
- 🇮🇹 Italy — Serie A
- 🇩🇪 Germany — Bundesliga
- 🇫🇷 France — Ligue 1
- 🇳🇱 Netherlands — Eredivisie
- 🇵🇹 Portugal — Primeira Liga

Bu siyahı `config.py` faylındakı `FOOTBALL_DATA_COMPETITIONS`-də sabit təyin olunub — football-data.org-un pulsuz planı yalnız bu liqaları dəstəklədiyi üçün avtomatik "kəşf" addımı artıq yoxdur.

Women, youth, reserve and development competitions are filtered out so they do not contaminate the main model.

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

Create a `.env` from `.env.example` and set `FOOTBALL_DATA_API_KEY` (get a free
key at https://www.football-data.org/client/register). Never put the key
directly in source code or send it in chat.

## Telegram bot — daily predictions + on-demand team lookup

- `data/stats_provider.py` — builds full match features (form, xG-proxy, injuries,
  Elo) from live football-data.org data for the predictor.
- `data/elo_store.py` — football-data.org has no Elo endpoint, so V3 maintains
  its own Elo table in SQLite, updated from finished fixtures it scans.
- `bot/scanner.py` — runs one full daily scan across the 7 core countries and
  returns formatted, signal-filtered match cards (NO SIGNAL matches are dropped).
- `bot/telegram_bot.py` — posts the daily scan to a Telegram channel/group on a
  schedule, plus:
  - `/scan` — manual on-demand scan.
  - `/komanda <ad>` — type a team name and the bot replies in Telegram with
    that team's live form, Elo rating, goal averages and recent results
    (e.g. `/komanda Arsenal`).
  - `/komanda TeamA-TeamB` — if the two teams have a scheduled match, replies
    with the full prediction card for it; otherwise sends both teams'
    individual reports.
  - Typos are tolerated (fuzzy match), and any lookup/API/network failure
    replies with a clear error message in the chat instead of failing silently.

**Known limitation:** football-data.org's free plan doesn't expose true
shot-based xG. `stats_provider.py` uses each team's recent average
goals-for/against as a proxy — documented in that file.

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env: FOOTBALL_DATA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
python run_bot.py
```

`TELEGRAM_CHAT_ID` is the channel/group the bot posts to — add the bot as an
admin there first. `DAILY_SCAN_HOUR_UTC` (default 7, i.e. 07:00 UTC / 11:00
Baku time) sets the daily post time. Use `/scan` or `/komanda <ad>` in a chat
with the bot to trigger an immediate test.
