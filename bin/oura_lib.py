"""Oura Ring API v2 client + OAuth2 flow. Stdlib only, no dependencies.

Auth model (verified against Oura docs 2026-07):
- OAuth2 authorization-code is the ONLY supported flow (PATs deprecated Dec 2025).
- Refresh tokens are SINGLE-USE and rotate on every refresh (WHOOP-style):
  hold an exclusive lock for load -> refresh -> save, and persist the new
  pair BEFORE it is used anywhere else.
- Access-token TTL is inconsistent in Oura's docs; trust `expires_in` only.
- Authorization codes are valid 10 minutes, single-use.
- Token endpoint accepts client_id+client_secret as form params (or HTTP Basic).

Never log or print tokens, codes, or client secrets.
"""

import fcntl
import json
import os
import time
import urllib.parse
import urllib.request

AUTHORIZE_URL = "https://cloud.ouraring.com/oauth/authorize"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
REVOKE_URL = "https://api.ouraring.com/oauth/revoke"
API_BASE = "https://api.ouraring.com"
SANDBOX_BASE = "https://api.ouraring.com/v2/sandbox"

# Scopes per Oura's authentication page. NOTE: the OpenAPI doc keys the SpO2
# scope as `spo2Daily` while the auth page says `spo2` — one of them is a typo.
# `spo2` is the default here; if /oauth/authorize rejects it, try `spo2Daily`.
DEFAULT_SCOPES = "daily heartrate workout spo2 personal session"

CONFIG_DIR = os.path.expanduser("~/.config/oura-muse")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
TOKENS_PATH = os.path.join(CONFIG_DIR, "tokens.json")


class OuraError(Exception):
    pass


def _ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config():
    """client_id / client_secret / redirect_uri from env or config file."""
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
    return {
        "client_id": os.environ.get("OURA_CLIENT_ID") or cfg.get("client_id"),
        "client_secret": os.environ.get("OURA_CLIENT_SECRET") or cfg.get("client_secret"),
        "redirect_uri": os.environ.get("OURA_REDIRECT_URI")
        or cfg.get("redirect_uri", "http://localhost:8888/callback"),
    }


def save_config(client_id, client_secret, redirect_uri="http://localhost:8888/callback"):
    _ensure_dir()
    with open(CONFIG_PATH, "w") as f:
        json.dump(
            {"client_id": client_id, "client_secret": client_secret,
             "redirect_uri": redirect_uri},
            f,
        )
    os.chmod(CONFIG_PATH, 0o600)


def authorize_url(client_id, redirect_uri, scopes=DEFAULT_SCOPES, state=None):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
    }
    if state:
        params["state"] = state
    return AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)


def extract_code(pasted):
    """Accept a raw code or the full redirect URL the browser landed on."""
    pasted = pasted.strip()
    if pasted.startswith("http"):
        q = urllib.parse.urlparse(pasted).query
        params = urllib.parse.parse_qs(q)
        if "error" in params:
            raise OuraError("Authorization failed: %s" % params["error"][0])
        codes = params.get("code")
        if not codes:
            raise OuraError("No ?code= found in the pasted URL.")
        return codes[0]
    return pasted


def _post_token(data):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:500]
        raise OuraError("Token request failed (HTTP %s): %s" % (e.code, detail))


def exchange_code(client_id, client_secret, code, redirect_uri):
    """Trade a 10-minute single-use authorization code for a token pair."""
    tok = _post_token({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    })
    return _normalize_tokens(tok)


def refresh_tokens(client_id, client_secret, refresh_token):
    """Single-use refresh: returns a NEW pair; the old one is dead after this."""
    tok = _post_token({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    })
    return _normalize_tokens(tok)


def _normalize_tokens(tok):
    for k in ("access_token", "refresh_token"):
        if k not in tok:
            raise OuraError("Token response missing %r" % k)
    tok["expires_at"] = int(time.time()) + int(tok.get("expires_in", 86400))
    return tok


class TokenStore:
    """File-backed token storage with the rotating-refresh discipline.

    The entire load -> refresh -> save sequence runs under an exclusive
    lock, and the new pair is written to disk BEFORE it is returned/used,
    so a crash or concurrent caller can never reuse a spent refresh token.
    """

    def __init__(self, path=TOKENS_PATH):
        self.path = path

    def load(self):
        if not os.path.exists(self.path):
            return None
        with open(self.path) as f:
            return json.load(f)

    def _save_locked(self, tokens):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(tokens, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def ensure_fresh(self, client_id, client_secret, leeway=120):
        """Return a valid access token, refreshing (once, under lock) if needed."""
        _ensure_dir()
        with open(self.path, "a+") as lockf:
            fcntl.flock(lockf, fcntl.LOCK_EX)
            try:
                tokens = self.load()
                if not tokens:
                    raise OuraError(
                        "No tokens stored. Run `oura auth login` first.")
                if tokens.get("expires_at", 0) > time.time() + leeway:
                    return tokens["access_token"]
                new_tokens = refresh_tokens(
                    client_id, client_secret, tokens["refresh_token"])
                self._save_locked(new_tokens)  # persist BEFORE use
                return new_tokens["access_token"]
            finally:
                fcntl.flock(lockf, fcntl.LOCK_UN)

    def save(self, tokens):
        _ensure_dir()
        with open(self.path, "a+") as lockf:
            fcntl.flock(lockf, fcntl.LOCK_EX)
            try:
                self._save_locked(tokens)
            finally:
                fcntl.flock(lockf, fcntl.LOCK_UN)

    def clear(self):
        if os.path.exists(self.path):
            os.remove(self.path)


class OuraClient:
    """Read-only v2 API client with auto-refresh and pagination."""

    def __init__(self, client_id, client_secret, store=None, sandbox=False,
                 base_url=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.store = store or TokenStore()
        self.base = base_url or API_BASE
        self.sandbox = sandbox
        # Sandbox mirrors every data route under /v2/sandbox/usercollection/.
        self.route_prefix = ("/v2/sandbox/usercollection/" if sandbox
                             else "/v2/usercollection/")

    def _request(self, method, path, params=None, _retried=False):
        if self.sandbox:
            access_token = "sandbox"  # any string works against the sandbox
        else:
            access_token = self.store.ensure_fresh(
                self.client_id, self.client_secret)
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, method=method,
            headers={"Authorization": "Bearer " + access_token},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 401 and not _retried and not self.sandbox:
                # Token may have been revoked server-side; force one refresh.
                with open(self.store.path, "a+") as lockf:
                    fcntl.flock(lockf, fcntl.LOCK_EX)
                    try:
                        tokens = self.store.load() or {}
                        new_tokens = refresh_tokens(
                            self.client_id, self.client_secret,
                            tokens.get("refresh_token", ""))
                        self.store._save_locked(new_tokens)
                    finally:
                        fcntl.flock(lockf, fcntl.LOCK_UN)
                return self._request(method, path, params, _retried=True)
            if e.code == 403:
                raise OuraError(
                    "403 from Oura: this usually means the token lacks the "
                    "needed scope, or (Gen3+) there is no active Oura "
                    "membership on the account.")
            if e.code == 429:
                raise OuraError(
                    "Rate limited by Oura (5000 req / 5 min). Back off and retry.")
            detail = e.read().decode("utf-8", "ignore")[:500]
            raise OuraError("Oura API error (HTTP %s): %s" % (e.code, detail))

    def list_all(self, route, start_date=None, end_date=None, params=None):
        """GET a /v2/usercollection/ route, following next_token pages."""
        out = []
        page_params = dict(params or {})
        if start_date:
            page_params["start_date"] = start_date
        if end_date:
            page_params["end_date"] = end_date
        while True:
            resp = self._request("GET", self.route_prefix + route,
                                 page_params or None)
            if isinstance(resp, dict) and "data" in resp:
                out.extend(resp["data"])
                nxt = resp.get("next_token")
                if not nxt:
                    break
                page_params = {"next_token": nxt}
            else:
                return resp
        return out

    # ---- convenience wrappers (scope in parentheses) ----

    def personal_info(self):                       # personal
        return self._request("GET", self.route_prefix + "personal_info")

    def daily_sleep(self, start_date=None, end_date=None):      # daily
        return self.list_all("daily_sleep", start_date, end_date)

    def sleep_periods(self, start_date=None, end_date=None):    # daily
        return self.list_all("sleep", start_date, end_date)

    def daily_readiness(self, start_date=None, end_date=None):  # daily
        return self.list_all("daily_readiness", start_date, end_date)

    def daily_activity(self, start_date=None, end_date=None):   # daily
        return self.list_all("daily_activity", start_date, end_date)

    def daily_spo2(self, start_date=None, end_date=None):       # spo2
        return self.list_all("daily_spo2", start_date, end_date)

    def daily_stress(self, start_date=None, end_date=None):     # daily
        return self.list_all("daily_stress", start_date, end_date)

    def daily_resilience(self, start_date=None, end_date=None):  # daily
        return self.list_all("daily_resilience", start_date, end_date)

    def vo2_max(self, start_date=None, end_date=None):          # daily
        return self.list_all("vO2_max", start_date, end_date)

    def workouts(self, start_date=None, end_date=None):         # workout
        return self.list_all("workout", start_date, end_date)

    def heartrate(self, start_datetime, end_datetime):          # heartrate
        # heartrate uses datetimes, not dates, and its own pagination keys.
        out, next_token = [], None
        while True:
            params = {"start_datetime": start_datetime,
                      "end_datetime": end_datetime}
            if next_token:
                params["next_token"] = next_token
            resp = self._request("GET", self.route_prefix + "heartrate", params)
            out.extend(resp.get("data", []))
            next_token = resp.get("next_token")
            if not next_token:
                break
        return out

    def revoke(self):
        tokens = self.store.load() or {}
        for t in (tokens.get("access_token"), tokens.get("refresh_token")):
            if not t:
                continue
            body = urllib.parse.urlencode({"token": t}).encode()
            req = urllib.request.Request(REVOKE_URL, data=body)
            try:
                urllib.request.urlopen(req, timeout=15).read()
            except Exception:
                pass
        self.store.clear()
