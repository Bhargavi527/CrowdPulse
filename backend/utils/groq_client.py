"""
Optional Groq enrichment for place classification.
Uses Groq's OpenAI-compatible chat completions API when GROQ_API_KEY is set.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.request


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
ALLOWED_TYPES = {
    "heritage",
    "religious",
    "nature",
    "beach",
    "shopping",
    "market",
    "park",
    "transport",
    "landmark",
}


def _load_local_env():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_local_env()
DEFAULT_MODEL = os.getenv("GROQ_MODEL", DEFAULT_MODEL)


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_groq_place_context(location_name: str, lat: float, lng: float, fallback_type: str) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"used": False, "reason": "missing_api_key"}

    prompt = f"""
You are classifying a real-world place for a crowd prediction system.
Return only JSON with these keys:
- place_type: one of {sorted(ALLOWED_TYPES)}
- base_level: integer 10-90
- capacity: integer 300-6000
- demand_bias: integer -10 to 15
- special_multiplier: float 0.8 to 1.4
- reasoning: short string under 18 words

Place name: {location_name}
Latitude: {lat}
Longitude: {lng}
Fallback type: {fallback_type}
"""

    payload = {
        "model": DEFAULT_MODEL,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You produce compact JSON for geospatial classification. Never include markdown.",
            },
            {"role": "user", "content": prompt.strip()},
        ],
    }

    request = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            raw = json.loads(response.read().decode("utf-8"))
        content = raw["choices"][0]["message"]["content"]
        data = json.loads(content)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError, IndexError, TimeoutError):
        return {"used": False, "reason": "groq_unavailable"}

    place_type = str(data.get("place_type", fallback_type)).strip().lower()
    if place_type not in ALLOWED_TYPES:
        place_type = fallback_type

    return {
        "used": True,
        "model": DEFAULT_MODEL,
        "place_type": place_type,
        "base_level": _safe_int(data.get("base_level"), 0),
        "capacity": _safe_int(data.get("capacity"), 0),
        "demand_bias": _safe_float(data.get("demand_bias"), 0.0),
        "special_multiplier": _safe_float(data.get("special_multiplier"), 1.0),
        "reasoning": str(data.get("reasoning", "")).strip()[:120],
    }
