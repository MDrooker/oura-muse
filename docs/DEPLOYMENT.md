# Deployment runbook — oura-muse

Three supported ways to deploy, from simplest to most integrated.
Pick one; the OAuth app registration (step 0) is common to all.

## Step 0 — Register an Oura app (all options, ~2 minutes)

1. Sign in at <https://cloud.ouraring.com/oauth/applications> (needs an Oura account).
2. Create an application. Whitelist this redirect URI (exact match):
   `http://localhost:8888/callback`
3. Copy the **client ID** and **client secret**.

Notes:
- Oura caps apps at 10 users before requiring approval (`api-support@ouraring.com`).
- A Gen3+ ring without an active Oura membership gets `403` on data routes.

---

## Option A — Local CLI (your own machine)

For developers who want Oura data in scripts, cron jobs, or a personal dashboard.

```bash
git clone <repo-url> oura-muse && cd oura-muse
./bin/oura auth login --local-server   # opens your browser, captures the code
./bin/oura readiness
```

`--local-server` spins up a throwaway listener on port 8888, opens the Oura
authorize page, and captures the redirect automatically. Without it, the CLI
prints the URL and you paste back the `?code=` address.

**Daily sync via cron** (example — appends JSONL per day-type):

```bash
# crontab: every morning at 07:30
30 7 * * * /path/to/oura-muse/bin/oura readiness --start $(date -d 'yesterday' +%F) >> ~/oura-data/readiness.jsonl
30 7 * * * /path/to/oura-muse/bin/oura sleep     --start $(date -d 'yesterday' +%F) >> ~/oura-data/sleep.jsonl
```

Tokens live in `~/.config/oura-muse/` (mode `0600`). The CLI refreshes them
automatically; never copy `tokens.json` between machines while both are active
— refresh tokens are single-use and the two copies will race.

---

## Option B — Muse workspace skill (recommended for Muse users)

This is how an AI agent (e.g. Muse) reads your Oura data inside its normal
workflow — morning health reviews, training-load analysis, weekly briefs.

**Install:**

```bash
cp -r oura-muse ~/workspace/skills/oura
```

Muse discovers `SKILL.md` automatically. The skill body tells the agent how to
call `bin/oura` and how auth works.

**Authorize (agent-assisted, one time):**

1. You register the app (step 0) and hand the agent the client ID + secret
   (via its secure credential flow — never paste secrets in chat).
2. The agent runs `./bin/oura auth login`, which prints an authorize URL.
3. You open the URL on your phone/laptop, approve, and paste back the
   `?code=` URL you land on.
4. The agent exchanges the code; tokens land in `~/.config/oura-muse/`.

**Day-to-day:** the agent calls e.g.
`./bin/oura readiness --start 2026-10-10 --end 2026-10-11` and gets JSON back.
A scheduled job (cron) can do this every morning and fold readiness, sleep
stages, HRV contributors, and SpO2 into a health brief — no Watch required.

**Token hygiene on a shared VM:** the token file is yours (`0600`). The
rotating-refresh discipline (exclusive lock across load → refresh → save,
persist-before-use) means even overlapping cron runs can't burn a refresh
token. Don't run the CLI concurrently from two machines against one token file.

---

## Option C — Muse platform connector (alternative, zero local state)

If you prefer the platform to own the OAuth dance entirely, Muse can connect
Oura as a managed connector instead of using this repo's token file:

- Provider: `oura` (registered as `custom.oura`)
- API hosts: `api.ouraring.com`
- Scheme: `oauth2_code`
- Authorize: `https://cloud.ouraring.com/oauth/authorize`
- Token: `https://api.ouraring.com/oauth/token`
- Issuer domain: `ouraring.com`
- Token endpoint auth: `client_secret_basic`
- Revoke: `https://api.ouraring.com/oauth/revoke`
- Scopes: `daily heartrate workout personal spo2 session`

The agent triggers this with its `request_api_access` flow: you get a secure
card, enter the client ID/secret from step 0, authorize Oura in your browser,
and the platform stores and refreshes the tokens. No local files, no CLI.

Trade-offs vs Option B:

| | Option B (this repo) | Option C (connector) |
|---|---|---|
| Token storage | `~/.config/oura-muse/` (yours) | platform vault |
| OAuth UX | paste-back code (one time) | guided card flow |
| Refresh handling | file-lock discipline in `oura_lib.py` | platform-managed |
| Works outside Muse | yes (plain CLI) | no |
| Auditable code | yes — it's this repo | no |

Both read the same API. Pick B if you want one codebase that works everywhere
(including outside Muse); pick C if you want the platform to own credentials.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `invalid_grant` on code exchange | code older than 10 min, or already used | re-run `auth login`, be quick |
| 401 on every call | refresh token spent (two clients racing) or revoked | `oura auth login` again |
| 403 on data routes | missing scope, or no active Oura membership (Gen3+) | check granted scopes; confirm membership |
| 429 | over 5000 req / 5 min | back off; the CLI makes one request per page |
| `/oauth/authorize` rejects scope | `spo2` vs `spo2Daily` naming discrepancy on Oura's side | retry with `--scopes` swapping the two |
| `auth login` hangs on `--local-server` | port 8888 busy or browser didn't open | use the manual paste flow instead |

## Security notes

- `~/.config/oura-muse/` is `0600` and lives outside the repo. Never commit it;
  `.gitignore` excludes it by pattern anyway.
- Tokens and codes are never printed — not by the CLI, not in logs.
- Before pushing the repo public (or accepting PRs), run:
  `git log -p | grep -iE 'client_secret|refresh_token|access_token|code='`
  and expect zero hits.
- The API is read-only; the only write surface is token revocation.

## Going-public checklist

- [ ] `LICENSE` (MIT) at root
- [ ] README quickstart tested end-to-end by a second person
- [ ] No secrets in git history (`git log -p` grep, above)
- [ ] CI green (`.github/workflows/test.yml` runs sandbox tests)
- [ ] `SKILL.md` description triggers on "oura" naturally
- [ ] CHANGELOG entry for the release
