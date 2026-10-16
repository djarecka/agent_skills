"""Sign in to an institutional EZproxy in a browser and remember the session.

Users should not have to know what an EZproxy host, a rewrite mode or a
cookies.txt export is. This module replaces the three ``EZPROXY_*`` variables
with one browser sign-in:

1. **Which proxy.** Worked out, in order, from: an explicit ``--proxy-host``;
   a link the user copied from their library (``--library-link``); an
   institution name or email domain (``--institution``); the saved login; the
   ``EZPROXY_HOST`` variable; the domain of the user's email
   (``SYNTHSCHOLAR_EMAIL`` / ``NCBI_EMAIL`` / ``git config user.email``). A
   domain is mapped through ``KNOWN_PROXIES``, then by probing the usual
   EZproxy hostnames for that domain — a candidate is used only if the server
   answers as EZproxy.
2. **Sign-in.** A real browser window opens at the proxy's login page; the user
   signs in with their library account (SSO, MFA — whatever their institution
   uses; nothing here sees the password). The window closes by itself once the
   proxy lets them through.
3. **Remembered.** The proxy host, the rewrite mode (detected from where the
   login landed) and the proxy's own session cookies are saved under
   ``~/.config/synthscholar/`` (owner-only permissions). Later runs reuse them,
   and the browser only opens again when the session has expired.

Only cookies for the proxy's own domain are saved — not the identity
provider's — so the file grants exactly what a logged-in proxy tab would, until
the proxy expires the session. ``--logout`` deletes all of it.

Needs ``playwright`` for the browser step (``pip install playwright``). It drives
the installed Chrome or Edge when there is one; otherwise it needs
``playwright install chromium`` once.
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ezproxy_client import _load_cookie_file  # noqa: E402  (one cookies.txt parser)

MODE_HOSTNAME_SUFFIX = "hostname-suffix"
MODE_LOGIN_URL = "login-url"

# Sign-in and the session check both start at the proxy's bare /login: once
# authenticated, EZproxy moves on to its own menu, so neither depends on the
# institution licensing (or a publisher not blocking) any particular site.
LOGIN_TIMEOUT = 300  # seconds the user has to finish signing in

# Email / institution domain → EZproxy host, for institutions confirmed to use
# this form. Anything missing is found by probing (below) or from a library link.
KNOWN_PROXIES = {
    "mit.edu": "libproxy.mit.edu",
}
# Hostnames institutions commonly give their EZproxy, in order of preference.
PROBE_PATTERNS = ("ezproxy.{d}", "libproxy.{d}", "ezproxy.lib.{d}", "proxy.lib.{d}",
                  "login.ezproxy.{d}", "{stem}.idm.oclc.org", "proxy.{d}", "ezp.lib.{d}",
                  "ezproxy.library.{d}", "login.proxy.lib.{d}")
ROR = "https://api.ror.org/v2/organizations"
# Personal-mail domains have no library proxy; don't probe them.
WEBMAIL = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
           "yahoo.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com",
           "gmx.com", "gmx.de", "qq.com", "163.com", "users.noreply.github.com"}
# Last dash-segment of a rewritten publisher host ("www-nature-com"): a TLD.
_REWRITTEN_LABEL = re.compile(
    r"^[a-z0-9]+(?:-{1,2}[a-z0-9]+)*-(?:com|org|net|edu|gov|int|io|info|ac|co|uk|de|fr|"
    r"jp|ca|au|nl|ch|se|it|es|cn|in|br|ru|kr|eu|us)$")

# Exit codes the CLI uses so a caller (the agent) knows what to ask the user.
EXIT_NEEDS_INSTITUTION = 4
EXIT_NEEDS_BROWSER = 3


class LoginError(RuntimeError):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


# ─────────────────────────── saved state ────────────────────────────

def state_dir() -> Path:
    base = os.environ.get("SYNTHSCHOLAR_CONFIG_DIR") or (
        Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "synthscholar")
    d = Path(base).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    try:
        d.chmod(0o700)
    except OSError:
        pass
    return d


def _state_file() -> Path:
    return state_dir() / "ezproxy.json"


def cookie_path() -> Path:
    return state_dir() / "ezproxy-cookies.txt"


def load_saved() -> Optional[dict]:
    """The saved login, or None. Ignored when its cookie file is gone."""
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not data.get("host") or not Path(data.get("cookie_file", "")).is_file():
        return None
    return data


def _write_private(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(path, 0o600)


def save(host: str, mode: str, cookies: list[dict], source: str) -> dict:
    lines = ["# Netscape HTTP Cookie File — EZproxy session saved by synthscholar"]
    for c in cookies:
        domain = c.get("domain", "")
        lines.append("\t".join([
            domain, "TRUE" if domain.startswith(".") else "FALSE", c.get("path") or "/",
            "TRUE" if c.get("secure") else "FALSE",
            str(int(c.get("expires") or 0)) if (c.get("expires") or 0) > 0 else "0",
            c["name"], c.get("value", "")]))
    _write_private(cookie_path(), "\n".join(lines) + "\n")
    state = {"host": host, "mode": mode, "cookie_file": str(cookie_path()),
             "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "host_source": source}
    _write_private(_state_file(), json.dumps(state, indent=2) + "\n")
    return state


def logout() -> list[str]:
    """Delete the saved login, cookies and browser profile; return what was removed."""
    removed = []
    for p in (_state_file(), cookie_path()):
        if p.exists():
            p.unlink()
            removed.append(str(p))
    profile = state_dir() / "browser-profile"
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
        removed.append(str(profile))
    return removed


# ─────────────────────────── which proxy ────────────────────────────

def _strip_login_prefix(host: str) -> str:
    """``login.ezproxy.uni.edu`` → ``ezproxy.uni.edu`` (EZproxy's login sub-host)."""
    return host[len("login."):] if host.startswith("login.") else host


def host_from_link(link: str) -> Optional[str]:
    """Proxy host from a link the user's library gave them, or None.

    ``https://www-nature-com.libproxy.mit.edu/articles/…`` → ``libproxy.mit.edu``;
    ``https://ezproxy.uni.edu/login?url=…`` → ``ezproxy.uni.edu``;
    ``https://login.ezproxy.uni.edu/login?qurl=…`` → ``ezproxy.uni.edu``.
    The candidate must answer as EZproxy, so a plain publisher link
    (``https://www.nature.com/…``) is rejected rather than taken for a proxy.
    """
    p = urlparse(link.strip())
    netloc = (p.hostname or "").lower()
    if not netloc:
        return None
    first, _, rest = netloc.partition(".")
    if _REWRITTEN_LABEL.match(first) and rest.count(".") >= 1:
        cand = rest                       # a rewritten publisher host
    else:
        cand = _strip_login_prefix(netloc)
    return cand if is_ezproxy(cand) or is_ezproxy("login." + cand) else None


def _email_domains() -> list[str]:
    emails = [os.environ.get("SYNTHSCHOLAR_EMAIL", ""), os.environ.get("NCBI_EMAIL", "")]
    if shutil.which("git"):
        try:
            emails.append(subprocess.run(["git", "config", "user.email"], capture_output=True,
                                         text=True, timeout=5).stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
    return [e.split("@", 1)[1].lower() for e in emails if "@" in e]


def _registrable(domain: str) -> str:
    """``eecs.mit.edu`` → ``mit.edu``; ``cam.ac.uk`` stays (two-part public suffix)."""
    parts = domain.lower().strip(".").split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in ("ac", "edu", "co", "org", "gov"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def is_ezproxy(host: str, timeout: float = 5.0) -> bool:
    """Does ``host`` answer as an EZproxy server?"""
    try:
        r = httpx.get(f"https://{host}/login", timeout=timeout, follow_redirects=False)
    except httpx.HTTPError:
        return False
    server = (r.headers.get("server") or "").lower()
    loc = (r.headers.get("location") or "").lower()
    return "ezproxy" in server or "ezproxy" in r.text[:4000].lower() or "ezproxy" in loc


def host_for_domain(domain: str) -> Optional[str]:
    """The domain's EZproxy host: the known table, else the first probe that answers."""
    d = _registrable(domain)
    if d in KNOWN_PROXIES:
        return KNOWN_PROXIES[d]
    if d in WEBMAIL or domain.lower() in WEBMAIL:
        return None
    stem = d.split(".")[0]
    cands = [pat.format(d=d, stem=stem) for pat in PROBE_PATTERNS]
    with ThreadPoolExecutor(max_workers=len(cands)) as pool:   # one timeout, not six
        hits = list(pool.map(is_ezproxy, cands))
    return next((_strip_login_prefix(c) for c, ok in zip(cands, hits) if ok), None)


def institution_domains(name: str) -> list[tuple[str, str]]:
    """``[(official name, domain)]`` for ONE institution, from ROR (worldwide, no key).

    ROR's affiliation matcher marks a single confident match as ``chosen``:
    "University of Oxford" → ox.ac.uk, "Technical University of Munich" → tum.de.
    Only that match is used, never the runners-up: falling through to the next
    candidate would sign the user in to someone else's library. No chosen
    match (an ambiguous word such as "toronto") returns nothing.
    """
    try:
        r = httpx.get(ROR, params={"affiliation": name}, timeout=15)
        items = r.json().get("items") or [] if r.status_code == 200 else []
    except (httpx.HTTPError, ValueError):
        return []
    hit = next((it for it in items if it.get("chosen")), None)
    org = (hit or {}).get("organization") or {}
    if not org:
        return []
    display = next((n.get("value") for n in org.get("names") or []
                    if "ror_display" in (n.get("types") or [])), name)
    doms = list(org.get("domains") or [])
    doms += [urlparse(l.get("value", "")).hostname or "" for l in org.get("links") or []
             if l.get("type") == "website"]
    out: list[tuple[str, str]] = []
    for d in doms:
        d = _registrable(d.removeprefix("www."))
        if d and d not in {x for _, x in out}:
            out.append((display, d))
    return out


def resolve_host(proxy_host: str = "", library_link: str = "", institution: str = "") -> tuple[str, str]:
    """(host, how it was found). Raises LoginError(EXIT_NEEDS_INSTITUTION)."""
    if proxy_host:
        return proxy_host.strip().lower(), "given"
    if library_link:
        h = host_from_link(library_link)
        if h:
            return h, "library link"
    if institution:
        dom = institution.strip().lower()
        dom = dom.split("@", 1)[1] if "@" in dom else dom
        if "." in dom and " " not in dom:          # a domain: mit.edu, ox.ac.uk
            candidates = [(institution, dom)]
        elif " " not in dom:                       # an acronym: "mit" → mit.edu only;
            candidates = [(institution, f"{dom}.edu")]   # ROR matches acronyms worldwide
        else:                                      # a full name: ROR's single chosen match
            candidates = institution_domains(institution)
        for display, d in candidates:
            h = host_for_domain(d)
            if h:
                return h, f"institution {display} ({d})"
        # asked for a specific institution: never fall back to someone else's proxy
        tried = ", ".join(d for _, d in candidates) or "no matching institution"
        raise LoginError(
            f"Couldn't find an EZproxy for '{institution}' (tried {tried}). Ask the user for "
            "their institution's full name or email domain, or for a link they get when "
            "opening an article through their library, and pass it as --library-link. "
            "Libraries that use OpenAthens or Shibboleth instead of EZproxy are not supported.",
            EXIT_NEEDS_INSTITUTION)
    if library_link:
        raise LoginError(f"'{library_link}' doesn't look like a library proxy link.",
                         EXIT_NEEDS_INSTITUTION)
    saved = load_saved()
    if saved:
        return saved["host"], "saved login"
    if os.environ.get("EZPROXY_HOST"):
        return os.environ["EZPROXY_HOST"].strip().lower(), "EZPROXY_HOST"
    for dom in _email_domains():
        h = host_for_domain(dom)
        if h:
            return h, f"email domain {dom}"
    raise LoginError(
        "Couldn't tell which library proxy to use. Ask the user for their university or "
        "library (e.g. 'MIT'), or a link they get when opening an article through their "
        "library, and pass it as --institution or --library-link.", EXIT_NEEDS_INSTITUTION)


# ─────────────────────────── session ────────────────────────────

def login_url(host: str, target: str = "") -> str:
    """The proxy's sign-in URL, optionally continuing to ``target``.

    ``qurl=`` carries the target percent-encoded; ``url=`` must be raw, and an
    encoded value there matches no configured database, so EZproxy shows its
    menu page instead of the article.
    """
    return f"https://{host}/login" + (f"?qurl={quote(target, safe='')}" if target else "")


def through_proxy(url: str, host: str) -> Optional[str]:
    """The rewrite mode if ``url`` is a page past the proxy's sign-in, else None.

    Past sign-in means: on a rewritten publisher host (``*.host`` →
    ``hostname-suffix``), or on the proxy itself, including ``login.host`` and a
    proxy-by-port ``host:2048``, anywhere but its login pages (its menu).
    ``login-url`` is returned when the form can't be told from the URL. It is the
    universal one: every EZproxy accepts ``/login?qurl=`` and redirects onwards.
    """
    u = urlparse(url)
    h = (u.hostname or "").lower()
    on_login = u.path.lower().startswith(("/login", "/connect", "/logout"))
    if h.endswith("." + host) and not h.startswith("login."):
        return MODE_HOSTNAME_SUFFIX
    if h == "login." + host and not on_login:
        return MODE_HOSTNAME_SUFFIX     # login.* sub-host = proxy by hostname
    if h == host and not on_login:
        return MODE_LOGIN_URL
    return None


def session_valid(host: str, cookie_file: str, timeout: float = 20.0) -> Optional[bool]:
    """True = the proxy lets this session through; False = expired; None = can't tell.

    Asks the proxy alone: an authenticated /login moves on to the proxy's menu,
    an expired one bounces to the login form or the identity provider.
    """
    jar = httpx.Cookies()
    for c in _saved_cookies(cookie_file):
        jar.set(c["name"], c["value"], domain=c["domain"])
    try:
        r = httpx.get(login_url(host), cookies=jar, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if r.status_code >= 500:
        return None
    return through_proxy(str(r.url), host) is not None


def _saved_cookies(cookie_file: str) -> list[dict]:
    """(name, value, domain) of the saved cookies, domains kept for the jar."""
    out = []
    names = _load_cookie_file(cookie_file)
    try:
        lines = Path(cookie_file).expanduser().read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        parts = line.removeprefix("#HttpOnly_").split("\t")
        if len(parts) >= 7 and not line.startswith("# ") and parts[5] in names:
            out.append({"name": parts[5], "value": parts[6], "domain": parts[0]})
    return out


def _proxy_cookies(cookies: list[dict], host: str) -> list[dict]:
    """The proxy's own session cookies: domain ``host`` or ``login.host`` only.

    Not publisher or sibling-host cookies, which would collide by name when the
    client flattens the jar; the ``host`` one wins a name clash.
    """
    keep = {}
    for c in cookies:
        d = (c.get("domain") or "").lstrip(".").lower()
        if d in (host, "login." + host) and (c["name"] not in keep or d == host):
            keep[c["name"]] = c
    return list(keep.values())


def browser_login(host: str, source: str, timeout: int = LOGIN_TIMEOUT) -> dict:
    """Open a browser at the proxy's login, wait for the user, save the session."""
    try:
        from playwright.sync_api import Error as PwError
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise LoginError("Signing in needs Playwright: ask the user, then "
                         "`pip install playwright` (and `playwright install chromium` "
                         "if they have neither Chrome nor Edge).", EXIT_NEEDS_BROWSER)

    profile = state_dir() / "browser-profile"   # keeps the IdP's "remember me"
    start = login_url(host)
    print(f"Opening a browser window — sign in with your library account ({host}).\n"
          f"It closes by itself once you're through (waiting up to {timeout // 60} min).")
    with sync_playwright() as p:
        ctx = None
        errors = []
        for channel in ("chrome", "msedge", None):
            try:
                ctx = p.chromium.launch_persistent_context(
                    str(profile), headless=False, channel=channel, chromium_sandbox=True,
                    viewport={"width": 1100, "height": 800})
                break
            except PwError as e:
                errors.append(f"{channel or 'chromium'}: {str(e).splitlines()[0]}")
        if ctx is None:
            raise LoginError("No browser Playwright can drive (" + "; ".join(errors) + "). "
                             "Ask the user, then run `playwright install chromium`.",
                             EXIT_NEEDS_BROWSER)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(start, wait_until="domcontentloaded", timeout=30000)
            except PwError as e:
                raise LoginError(f"Couldn't open {start}: {str(e).splitlines()[0]}. Is {host} "
                                 "your library's proxy? Pass --library-link or --institution.")
            deadline = time.monotonic() + timeout
            mode = None
            try:
                while time.monotonic() < deadline and not mode:
                    if not ctx.pages:
                        raise LoginError("The browser window was closed before sign-in finished.")
                    mode = next((m for m in (through_proxy(pg.url, host) for pg in ctx.pages) if m), None)
                    if not mode:
                        # not time.sleep: the sync API only processes browser events
                        # inside its own calls, so pg.url would never change
                        ctx.pages[0].wait_for_timeout(1000)
                cookies = _proxy_cookies(ctx.cookies(), host) if mode else []
            except PwError as e:
                raise LoginError("The browser closed before sign-in finished "
                                 f"({str(e).splitlines()[0]}).")
            if not mode:
                raise LoginError(f"Sign-in didn't finish within {timeout // 60} minutes.")
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    if not cookies:
        raise LoginError("Signed in, but the proxy set no session cookie to save.")
    return save(host, mode, cookies, source)


def ensure_session(*, proxy_host: str = "", library_link: str = "", institution: str = "",
                   force: bool = False, timeout: int = LOGIN_TIMEOUT) -> dict:
    """A working saved session: reuse it if still valid, otherwise sign in."""
    saved = load_saved()
    host, source = resolve_host(proxy_host, library_link, institution)
    if saved and saved["host"] == host and not force:
        ok = session_valid(host, saved["cookie_file"])
        if ok is not False:   # valid, or unknown (offline) — don't reopen a browser blindly
            return saved
        print(f"Your {host} session has expired — signing in again.")
    return browser_login(host, source, timeout=timeout)
