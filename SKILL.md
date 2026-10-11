---
name: "oura"
description: "Read Oura Ring health data (sleep, readiness, activity, heart rate, SpO2, workouts, VO2 max) via the Oura API v2. Use when the user asks about Oura data, or as a health-data source alongside Apple HealthKit."
---

# Oura

## Purpose
Query the user's Oura Ring data through the Oura API v2: daily sleep/readiness/activity summaries, detailed sleep periods, heart-rate time series, SpO2, stress, resilience, workouts, and VO2 max estimates.

## Tooling
All logic lives in `bin/` (stdlib only, no dependencies):

- `bin/oura` — CLI. Run `./bin/oura --help` for the full command list.
- `bin/oura_lib.py` — importable client (`OuraClient`, `TokenStore`, OAuth helpers).

Data commands (all accept `--start YYYY-MM-DD --end YYYY-MM-DD`, default last 7 days, JSON output):

```
./bin/oura readiness [--start --end]     # daily readiness scores + contributors
./bin/oura sleep [--start --end]         # daily sleep summaries (score, stages)
/bin/oura sleep-periods                  # detailed sleep periods
./bin/oura activity                      # daily activity summaries
./bin/oura spo2                          # nightly SpO2 averages
./bin/oura stress | resilience | vo2max
./bin/oura workouts
./bin/oura heartrate --start-datetime ISO --end-datetime ISO
./bin/oura whoami                         # personal info (connection test)
./bin/oura --sandbox readiness            # fake data, no account needed
```

## Auth
OAuth2 authorization-code is the only supported flow (Oura deprecated personal
access tokens in Dec 2025). One-time setup:

1. Register an app at `https://cloud.ouraring.com/oauth/applications` (needs an
   Oura account) and whitelist the redirect URI `http://localhost:8888/callback`.
2. `./bin/oura auth login` — prints an authorize URL. The user opens it,
   approves, then pastes back the `?code=` URL. (Or `--local-server` when the
   CLI runs on the user's own machine with a browser.)
3. Tokens are stored in `~/.config/oura-muse/` (mode 0600) and never printed.

Credentials can also come from env: `OURA_CLIENT_ID`, `OURA_CLIENT_SECRET`,
`OURA_REDIRECT_URI`.

**Rotating refresh tokens:** Oura's refresh tokens are single-use and rotate on
every refresh. `TokenStore.ensure_fresh()` holds an exclusive file lock across
load -> refresh -> save and persists the new pair *before* it is used. Never
add a second refresh path that bypasses the store.

`./bin/oura auth status` shows auth state without secrets. `./bin/oura auth logout`
revokes and clears tokens.

## Operating Rules
1. The data API is read-only. Never attempt writes outside webhook management
   (not implemented).
2. Respect 429s: back off when Oura rate-limits (5000 req / 5 min).
3. A 403 usually means the token lacks a scope or (Gen3+) the account has no
   active Oura membership — report it plainly, don't retry.
4. Default scopes are `daily heartrate workout spo2 personal session`. If
   `/oauth/authorize` rejects `spo2`, the OpenAPI doc keys it `spo2Daily` —
   one of the two is a typo on Oura's side; retry with the other.
5. Keep secrets out of logs, chat, and the repo. `~/.config/oura-muse/` is
   git-ignored by design.
6. For the full endpoint/scope reference, read `references/api.md`.
