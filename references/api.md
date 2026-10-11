# Oura API v2 — endpoint & scope reference

Base URL: `https://api.ouraring.com`. All data routes are `GET` under
`/v2/usercollection/`. Sandbox (fake data, any `Authorization` header works):
same routes under `/v2/sandbox/usercollection/`.

## Routes

| Route | Contents | Likely scope |
|---|---|---|
| `daily_sleep` | Sleep score, duration, efficiency, stages | `daily` |
| `sleep` | Detailed sleep periods (HR, HRV, movement) | `daily` |
| `daily_readiness` | Readiness score + contributors | `daily` |
| `daily_activity` | Steps, calories, MET minutes | `daily` |
| `daily_spo2` | Nightly SpO2 average (Gen3+) | `spo2` |
| `daily_stress` | Daytime stress | `daily` |
| `daily_resilience` | Resilience | `daily` |
| `vO2_max` | VO2 max estimates (note odd capitalization) | `daily` |
| `workout` | Auto-detected + manual workouts | `workout` |
| `heartrate` | HR time series, 5-min increments | `heartrate` |
| `personal_info` | Age, weight, height, sex, id (+email) | `personal` / `email` |
| `session` | Guided/unguided app sessions | `session` |
| `daily_cardiovascular_age` | Cardiovascular age | `daily` |
| `sleep_time` | Bedtime-window recommendations | `daily` |
| `ring_configuration` | Ring model/size/color | — |
| `ring_battery_level` | Battery (list only) | — |
| `enhanced_tag` | Tags (replaces deprecated `tag`) | `tag` |

Oura publishes no official endpoint→scope matrix; a 403 names the missing scope.

## Pagination

- Standard routes: `start_date` / `end_date` (date or datetime) + `next_token`.
- `heartrate`: `start_datetime` / `end_datetime` (datetime) + `next_token`.
- Envelope: `{"data": [...], "next_token": "..." | null}`.

## Scopes

`email`, `personal`, `daily`, `heartrate`, `workout`, `tag`, `session`, `spo2`.
Leaving `scope` blank on `/oauth/authorize` requests **all** scopes; users can
partially consent, and the redirect carries the actually-granted list.

**`spo2` vs `spo2Daily`:** the auth page says `spo2`, the OpenAPI doc says
`spo2Daily`. Untested which one `/oauth/authorize` accepts — try `spo2` first.

## Token semantics (verified 2026-07 against Oura docs)

- OAuth2 authorization-code only. PATs deprecated Dec 2025.
- Authorize: `https://cloud.ouraring.com/oauth/authorize`
- Token: `https://api.ouraring.com/oauth/token` (form-encoded; client_id +
  client_secret as form params or HTTP Basic)
- Revoke: `https://api.ouraring.com/oauth/revoke`
- Refresh tokens are **single-use** and rotate on every use — serialize refresh
  per account and persist the new pair before using it.
- No special scope needed for refresh tokens; they come with the code flow.
- Access-token TTL: docs contradict themselves (24h vs 30d) — trust `expires_in`.
- Authorization codes: valid 10 minutes, single-use.
- Redirect URIs: exact-match whitelist, multiple allowed per app.

## Limits & gating

- 5000 requests / 5 min, plus per-token and per-application buckets (429 +
  `Retry-After`). The client retries once after a short backoff, then raises.
- Apps are capped at 10 users before Oura approval is required
  (contact `api-support@ouraring.com`).
- Gen3+ ring **without an active Oura membership** gets 403 on data routes.

## Webhooks

App-level subscriptions (authenticate with `x-client-id` / `x-client-secret`
headers, **not** a user access token). One subscription per
(event_type, data_type) pair.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v2/webhook/subscription` | create |
| `GET` | `/v2/webhook/subscription` | list |
| `GET` | `/v2/webhook/subscription/{id}` | fetch one |
| `PUT` | `/v2/webhook/subscription/renew/{id}` | renew (~90-day TTL) |
| `DELETE` | `/v2/webhook/subscription/{id}` | delete |

Create body: `callback_url` (public HTTPS, required), `event_type`
(`create`/`update`/`delete`), `data_type` (e.g. `daily_sleep`, `workout`,
`session`, `daily_spo2`, `heartrate`), `verification_token` (your secret,
echoed on events).

Lifecycle notes:
- Oura sends a GET verification challenge to the callback URL at creation;
  answer 200 or the subscription won't activate.
- Subscriptions expire after ~90 days — renew them.
- Event POSTs carry a reference (data_type + object id + user id), not the
  full record; fetch it via the data routes.
