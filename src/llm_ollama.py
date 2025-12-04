import requests
from src.config import OLLAMA_URL, OLLAMA_MODEL


def generate_reply(prompt, history=None):
    if history is None:
        history = []

    messages = history + [{"role": "user", "content": prompt}]

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }

    url = f"{OLLAMA_URL}/api/chat"
    r = requests.post(url, json=payload)

    # Raise for HTTP-level errors first (500, 404, etc.)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        print("HTTP error from Ollama:")
        print("Status:", r.status_code)
        print("Body:", r.text)
        raise

    data = r.json()

    # Debug print so we can see what’s going on
    if "message" not in data:
        print("Unexpected Ollama response JSON:")
        print(data)

    # Normal success path
    if "message" in data and "content" in data["message"]:
        return data["message"]["content"]

    # Error path from Ollama (e.g., model missing)
    if "error" in data:
        raise RuntimeError("Ollama returned error: {}".format(data["error"]))

    # Catch-all
    raise RuntimeError("Unexpected Ollama response structure: {}".format(data))
