# pollama

Fetch and print your [Ollama Cloud](https://ollama.com) usage from the `/settings` page.

## Requirements

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/) (recommended)
- An Ollama Cloud account with an active session cookie

## Setup

Create a `.env` file in the project root with your `__Secure-session` cookie value:

```sh
SECURE_SESSION=<your cookie value here>
```

To get it: sign in at <https://ollama.com/signin>, then in your browser open
DevTools → Storage → Cookies → `https://ollama.com` and copy the value of the
`__Secure-session` cookie.

> The cookie is sent as `cookie: __Secure-session=<value>` to `https://ollama.com/settings`. `.env` is gitignored.
>
> Note: ollama.com sign-in moved to WorkOS AuthKit. The cookie is still named
> `__Secure-session`, but values minted before the migration were invalidated,
> and the value changes again whenever the session is re-issued. If the script
> reports a rejected session, sign in again and re-copy the cookie.
>
> When copying, include the full value, including any trailing `==` — that is
> base64 padding and part of the cookie. Extracting it in the browser console
> with `split('=')` strips the padding, and the server rejects the result.

## Usage

```sh
uv run main.py
```

### Example output

```
Session usage 7% used
  Resets in 4 hours.
  Resets at Thu Jun 25 2026 19:00 UTC
  glm-5.2: 40 requests (99.9%)
  gemini-3-flash-preview: 1 request (0.1%)

Weekly usage 54.4% used
  Resets in 3 days.
  Resets at Mon Jun 29 2026 00:00 UTC
  glm-5.2: 1253 requests (97.6%)
  ministral-3:3b: 407 requests (0.6%)
  web search: 88 requests (1.7%)
  ...
```

## License

MIT — see [LICENSE](LICENSE).