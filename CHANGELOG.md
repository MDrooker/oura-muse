# Changelog

## 0.1.0 — 2026-10-11

Initial public release.

- OAuth2 authorization-code flow (manual code paste + `--local-server` auto-capture)
- Single-use rotating refresh tokens with file-lock + persist-before-use discipline
- Read-only v2 client: sleep, readiness, activity, SpO2, stress, resilience, VO2 max, workouts, heart-rate time series, personal info
- `next_token` pagination on all list routes
- `--sandbox` mode against Oura's fake-data API (no account needed)
- Muse skill (`SKILL.md`) — drop the repo into `~/workspace/skills/oura/`
- Live sandbox test suite + GitHub Actions CI
