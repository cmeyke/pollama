import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser


_WIDTH_RE = re.compile(r"width:\s*([\d.]+)%")

_SETTINGS_URL = "https://ollama.com/settings"

# Endpoints of the sign-in flow ollama.com redirects unauthenticated requests to.
# ollama.com sign-in moved to WorkOS AuthKit; the migration invalidated
# pre-migration "__Secure-session" values.
_SIGNIN_URL_RE = re.compile(
    r"^https://(signin\.ollama\.com|api\.workos\.com/user_management/authorize|ollama\.com/signin)"
)


class SessionError(Exception):
    """ollama.com rejected the session cookie and redirected to the sign-in flow."""


def load_env(path: str = ".env") -> dict[str, str]:
    env: dict[str, str] = {}
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def fetch_cloud_usage(session: str) -> str:
    req = urllib.request.Request(_SETTINGS_URL)
    req.add_header("cookie", f"__Secure-session={session}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        final_url = resp.geturl()
        html = resp.read().decode("utf-8")
    if _SIGNIN_URL_RE.match(final_url):
        raise SessionError(f"redirected to {final_url}")
    return html


class UsageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meters: list[dict] = []
        self._meter_depth: int | None = None
        self._depth = 0
        self._capture_reset = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._depth += 1
        a = dict(attrs)
        if "data-usage-meter" in a:
            self._meter_depth = self._depth
            self.meters.append({"label": None, "reset": None, "reset_at": None, "segments": []})
        if self._meter_depth is not None:
            if "data-usage-track" in a:
                self.meters[-1]["label"] = a.get("aria-label", "")
            if tag == "button" and "data-usage-segment" in a:
                style = a.get("style", "") or ""
                m = _WIDTH_RE.search(style)
                pct = float(m.group(1)) if m else 0.0
                self.meters[-1]["segments"].append(
                    {
                        "model": a.get("data-model", ""),
                        "requests": int(a.get("data-requests", "0") or "0"),
                        "pct": pct,
                    }
                )
        if "local-time" in (a.get("class", "") or ""):
            self._capture_reset = True
            if a.get("data-time") and self.meters:
                self.meters[-1]["reset_at"] = a["data-time"]

    def handle_endtag(self, tag: str) -> None:
        if self._capture_reset and tag == "div":
            self._capture_reset = False
        if self._meter_depth is not None and self._depth == self._meter_depth:
            self._meter_depth = None
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_reset:
            text = data.strip()
            if text:
                for m in reversed(self.meters):
                    if m["reset"] is None:
                        m["reset"] = text
                        break


def parse_usage(html: str) -> list[dict]:
    parser = UsageParser()
    parser.feed(html)
    return parser.meters


def print_summary(meters: list[dict]) -> None:
    for meter in meters:
        label = meter["label"] or "Usage"
        print(label)
        if meter["reset"]:
            print(f"  {meter['reset']}")
        if meter["reset_at"]:
            dt = datetime.fromisoformat(meter["reset_at"].replace("Z", "+00:00"))
            pretty = dt.astimezone(timezone.utc).strftime("%a %b %d %Y %H:%M UTC")
            print(f"  Resets at {pretty}")
        for seg in sorted(meter["segments"], key=lambda s: s["pct"], reverse=True):
            req = seg["requests"]
            print(f"  {seg['model']}: {req} request{'s' if req != 1 else ''} ({seg['pct']:.1f}%)")
        print()


def report_error(*lines: str) -> None:
    """Print a failure explanation to stderr, keeping stdout clean for the summary."""
    for line in lines:
        print(line, file=sys.stderr)


def main() -> int:
    env = load_env()
    session = env.get("SECURE_SESSION", os.environ.get("SECURE_SESSION", "")).strip()
    if not session:
        report_error(
            "No SECURE_SESSION found in .env",
            "Sign in at https://ollama.com/signin, then copy the value of the",
            "__Secure-session cookie into .env as SECURE_SESSION=<value>",
            "(DevTools -> Storage -> Cookies -> https://ollama.com).",
        )
        return 1
    try:
        html = fetch_cloud_usage(session)
    except SessionError as exc:
        report_error(
            f"Session rejected ({exc}).",
            "ollama.com sign-in moved to WorkOS AuthKit; the cookie value in .env",
            "is stale or expired. Sign in at https://ollama.com/signin in your",
            "browser (this can be a seamless redirect), then re-copy the value of",
            "the __Secure-session cookie into .env as SECURE_SESSION=<value>",
            "(DevTools -> Storage -> Cookies -> https://ollama.com).",
        )
        return 1
    except urllib.error.HTTPError as exc:
        report_error(f"HTTP {exc.code} while fetching {exc.geturl()}")
        return 1
    except urllib.error.URLError as exc:
        report_error(f"Could not reach ollama.com: {exc.reason}")
        return 1
    meters = parse_usage(html)
    if not meters:
        report_error("Settings page fetched but no usage meters found; page markup may have changed.")
        return 1
    print_summary(meters)
    return 0


if __name__ == "__main__":
    sys.exit(main())
