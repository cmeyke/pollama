import os
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser


_WIDTH_RE = re.compile(r"width:\s*([\d.]+)%")


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
    url = "https://ollama.com/settings"
    req = urllib.request.Request(url)
    req.add_header("cookie", f"__Secure-session={session}")
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


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
        for seg in sorted(meter["segments"], key=lambda s: s["requests"], reverse=True):
            req = seg["requests"]
            print(f"  {seg['model']}: {req} request{'s' if req != 1 else ''} ({seg['pct']:.1f}%)")
        print()


def main():
    env = load_env()
    session = env.get("SECURE_SESSION", os.environ.get("SECURE_SESSION", ""))
    if not session:
        print("No SECURE_SESSION found in .env")
        return
    html = fetch_cloud_usage(session)
    print_summary(parse_usage(html))


if __name__ == "__main__":
    main()