import requests
from config import OLLAMA_URL, OLLAMA_MODEL, CONNECT_TIMEOUT_SEC, READ_TIMEOUT_SEC


def generate_reply(prompt, history=None):
    if history is None:
        history = []

    messages = history + [{"role": "user", "content": prompt}]

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }

    url = "{}/api/chat".format(OLLAMA_URL.rstrip("/"))

    try:
        r = requests.post(
            url,
            json=payload,
            timeout=(CONNECT_TIMEOUT_SEC, READ_TIMEOUT_SEC),
        )
    except requests.Timeout:
        # Covers both connect timeout and read timeout
        print("[OLLAMA TIMEOUT] Request timed out")
        return "(Ollama timed out — try again.)"
    except requests.ConnectionError as e:
        print("[OLLAMA CONNECTION ERROR] Could not reach Ollama:", repr(e))
        return "(Couldn’t reach Ollama — is it running?)"
    except requests.RequestException as e:
        # Catch-all for other request-layer issues
        print("[OLLAMA REQUEST ERROR]", repr(e))
        return "(Ollama request failed — see terminal for details.)"

    # Raise for HTTP-level errors first (500, 404, etc.)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        print("HTTP error from Ollama:")
        print("Status:", r.status_code)
        print("Body:", r.text)
        # This is a "real" failure; bubble up so your worker prints [WORKER ERROR]
        raise

    # JSON decode can fail if Ollama returns a non-JSON error page
    try:
        data = r.json()
    except ValueError as e:
        print("[OLLAMA JSON ERROR] Could not decode JSON:", repr(e))
        print("[OLLAMA RAW BODY]", r.text)
        return "(Ollama returned an unreadable response.)"

    # Debug print so we can see what’s going on
    if "message" not in data:
        print("Unexpected Ollama response JSON:")
        print(data)

    # Normal success path
    if "message" in data and isinstance(data["message"], dict) and "content" in data["message"]:
        return data["message"]["content"]

    # Error path from Ollama (e.g., model missing)
    if "error" in data:
        # You can choose to return a friendly string instead of raising if you prefer:
        # return "(Ollama error: {})".format(data["error"])
        raise RuntimeError("Ollama returned error: {}".format(data["error"]))

    # Catch-all
    raise RuntimeError("Unexpected Ollama response structure: {}".format(data))
