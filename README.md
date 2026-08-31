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
