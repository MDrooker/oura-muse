# oura-muse

Oura Ring API v2 client + CLI, built to be dropped into a
[Muse](https://muse.ai) workspace as a skill — and usable anywhere else as a
plain Python CLI. Stdlib only, zero dependencies.

## What it does

Reads your Oura Ring data through the official Oura API v2:

- Daily sleep summaries + detailed sleep periods (stages, efficiency, HRV)
- Readiness scores with contributors
- Activity, workouts, heart-rate time series, nightly SpO2, stress, resilience
- VO2 max estimates, personal info

All output is JSON, so it pipes cleanly into scripts, dashboards, and AI agents.

## Quickstart

**1. Register an Oura app** (one time, ~2 minutes)

Go to <https://cloud.ouraring.com/oauth/applications> (needs an Oura account),
create an application, and whitelist this redirect URI:

```
http://localhost:8888/callback
```

Copy the **client ID** and **client secret**.

**2. Authorize**

```bash
./bin/oura auth login
```

This prints an authorize URL. Open it, approve access, and paste back the URL
your browser lands on (it contains `?code=...`). If you're running on your own
machine with a browser, `./bin/oura auth login --local-server` captures the
code automatically — no pasting.

Tokens are stored in `~/.config/oura-muse/` (mode `0600`) and never printed.

**3. Query**

```bash
./bin/oura readiness                        # last 7 days
./bin/oura sleep --start 2026-10-01 --end 2026-10-07
./bin/oura heartrate --start-datetime 2026-10-10T00:00:00-06:00 \
                     --end-datetime   2026-10-11T00:00:00-06:00
./bin/oura whoami                            # connection test
```

Run `./bin/oura --help` for every command.

No account handy? `./bin/oura --sandbox readiness` hits Oura's fake-data
sandbox — no credentials needed.

## Using it with Muse

**As a workspace skill** (recommended): copy this repo to
`~/workspace/skills/oura/` and Muse picks up `SKILL.md` automatically. The
agent then calls `bin/oura` directly — readiness, sleep, and HRV land in
morning health reviews and weekly briefs with no Apple Watch required.

**As a platform connector** (alternative): connect Oura through Muse's managed
OAuth instead of the CLI's token file. Same API, platform-owned credentials —
see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for both paths and the trade-offs.

Full deployment playbook (local CLI, cron syncs, skill install, connector
setup, troubleshooting, going-public checklist):
**[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**

## Configuration

| Source | Values |
|---|---|
| Env vars | `OURA_CLIENT_ID`, `OURA_CLIENT_SECRET`, `OURA_REDIRECT_URI` |
| File | `~/.config/oura-muse/config.json` |

`oura auth login` writes the config file for you (mode `0600`).

## Auth notes (the sharp edges, documented)

- **OAuth2 only.** Oura deprecated personal access tokens in December 2025.
- **Refresh tokens rotate.** Each refresh invalidates the previous token, so the
  client holds an exclusive lock across load → refresh → save and persists the
  new pair *before* using it. Don't run two refreshers against one token file.
- **Access-token lifetime** is inconsistent in Oura's docs — the client trusts
  `expires_in` from the token response.
- **Scope quirk:** Oura's auth page calls the SpO2 scope `spo2`, the OpenAPI doc
  calls it `spo2Daily`. The default requests `spo2`; if authorization rejects
  it, pass `--scopes "daily heartrate workout spo2Daily personal session"`.
- **Membership gating:** a Gen3+ ring without an active Oura membership gets
  `403` on data routes.
- **App user cap:** Oura limits apps to 10 users before requiring approval
  (`api-support@ouraring.com`).

## Layout

```
├── SKILL.md            # Muse skill definition
├── bin/
│   ├── oura            # CLI
│   └── oura_lib.py     # OAuth2 + v2 client (single file, stdlib only)
├── docs/
│   └── DEPLOYMENT.md   # deployment runbook: CLI, skill, connector, cron, troubleshooting
├── references/
│   └── api.md          # endpoint / scope / token reference
├── tests/
│   └── test_sandbox.py # live tests against Oura's fake-data sandbox
└── .github/workflows/
    └── test.yml        # CI: compile check + sandbox tests on every push
```

## License

MIT. Not affiliated with Oura Health Oy.
