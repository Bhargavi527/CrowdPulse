"""
Geocoding helper with lightweight caching.
Prefers known references, then tries Nominatim with India-first and global fallback.
"""

from __future__ import annotations

import json as _json
import urllib.parse
import urllib.request

from ml.predictor import PLACES


_CACHE: dict[str, dict] = {}


def _fetch(query: str) -> list[dict]:
    encoded = urllib.parse.quote(query)
    request = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=5&addressdetails=1",
        headers={"User-Agent": "CrowdPulse/3.0"},
    )
    with urllib.request.urlopen(request, timeout=4) as response:
        return _json.loads(response.read())


def geocode(name: str) -> dict | None:
    key = name.strip().lower()
    if not key:
        return None
    if key in _CACHE:
        return _CACHE[key]

    for place in PLACES:
        place_name = place["name"].lower()
        if key in place_name or place_name in key:
            result = {"lat": place["lat"], "lng": place["lng"], "name": place["name"]}
            _CACHE[key] = result
            return result

    queries = [name, f"{name}, India", f"{name}, Karnataka, India"]
    for query in queries:
        try:
            data = _fetch(query)
        except Exception:
            continue
        if not data:
            continue

        best = data[0]
        result = {
            "lat": float(best["lat"]),
            "lng": float(best["lon"]),
            "name": best.get("display_name", name),
        }
        _CACHE[key] = result
        return result

    return None
