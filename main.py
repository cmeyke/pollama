import os
import urllib.request


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


def main():
    env = load_env()
    session = env.get("SECURE_SESSION", os.environ.get("SECURE_SESSION", ""))
    if not session:
        print("No SECURE_SESSION found in .env")
        return
    print(fetch_cloud_usage(session))


if __name__ == "__main__":
    main()