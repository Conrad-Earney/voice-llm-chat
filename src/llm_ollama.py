import requests
from config import OLLAMA_URL, OLLAMA_MODEL, CONNECT_TIMEOUT_SEC, READ_TIMEOUT_SEC
from src.logger import debug, error

TAG = "OLLAMA"


def generate_reply(prompt, history=None):
    if history is None:
        history = []

    messages = history + [{"role": "user", "content": prompt}]

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }

    url = f"{OLLAMA_URL.rstrip('/')}/api/chat"
    debug(TAG, f"POST {url} (model={OLLAMA_MODEL})")

    try:
        r = requests.post(
            url,
            json=payload,
            timeout=(CONNECT_TIMEOUT_SEC, READ_TIMEOUT_SEC),
        )
    except requests.Timeout:
        error(TAG, "Request timed out")
        return "(Ollama timed out — try again.)"
    except requests.ConnectionError as e:
        error(TAG, f"Could not reach Ollama: {e!r}")
        return "(Couldn't reach Ollama — is it running?)"
    except requests.RequestException as e:
        error(TAG, f"Request failed: {e!r}")
        return "(Ollama request failed — see terminal for details.)"

    # Raise for HTTP-level errors first (500, 404, etc.)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        error(TAG, "HTTP error from Ollama")
        error(TAG, f"Status: {r.status_code}")
        error(TAG, f"Body: {r.text}")
        raise

    # JSON decode can fail if Ollama returns a non-JSON error page
    try:
        data = r.json()
    except ValueError as e:
        error(TAG, f"Could not decode JSON: {e!r}")
        error(TAG, f"Raw body: {r.text}")
        return "(Ollama returned an unreadable response.)"

    # Debug output so we can see what’s going on
    if "message" not in data:
        error(TAG, f"Unexpected Ollama response JSON: {data}")

    # Normal success path
    if "message" in data and isinstance(data["message"], dict) and "content" in data["message"]:
        return data["message"]["content"]

    # Error path from Ollama (e.g., model missing)
    if "error" in data:
        raise RuntimeError(f"Ollama returned error: {data["error"]}")

    # Catch-all
    raise RuntimeError(f"Unexpected Ollama response structure: {data}")
