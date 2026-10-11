# Changelog

## Unreleased

- Webhook subscription management: `oura webhook {list,get,create,delete,renew}`
  (app-credential auth), plus `examples/webhook_receiver.py` starter receiver
- 429 responses now get one retry after a short backoff before raising
- README notes macOS/Linux-only (token locking uses `fcntl`)

## 0.1.0 — 2026-10-11

Initial public release.

- OAuth2 authorization-code flow (manual code paste + `--local-server` auto-capture)
- Single-use rotating refresh tokens with file-lock + persist-before-use discipline
- Read-only v2 client: sleep, readiness, activity, SpO2, stress, resilience, VO2 max, workouts, heart-rate time series, personal info
- `next_token` pagination on all list routes
- `--sandbox` mode against Oura's fake-data API (no account needed)
- Muse skill (`SKILL.md`) — drop the repo into `~/workspace/skills/oura/`
- Live sandbox test suite + GitHub Actions CI
