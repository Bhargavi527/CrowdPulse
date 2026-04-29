"""CrowdPulse — /location router (GPS data ingestion)"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()
_buffer = []  # In-memory buffer (replace with DB in production)

class LocationPing(BaseModel):
    lat: float
    lng: float
    accuracy_m: Optional[float] = None
    timestamp: Optional[str] = None
    session_id: str  # Anonymous session, no personal data

@router.post("/ping")
def ingest_location(ping: LocationPing):
    """
    Privacy-safe ingestion: only aggregate counts stored, no personal data.
    Karnataka bounding box filter applied.
    """
    KA_LAT = (11.5, 18.5); KA_LNG = (74.0, 78.6)
    if not (KA_LAT[0] <= ping.lat <= KA_LAT[1] and KA_LNG[0] <= ping.lng <= KA_LNG[1]):
        return {"status": "outside_karnataka", "stored": False}
    # Store only anonymized grid cell, never raw coordinates
    grid_lat = round(ping.lat * 100) / 100  # ~1km resolution
    grid_lng = round(ping.lng * 100) / 100
    _buffer.append({"grid_lat": grid_lat, "grid_lng": grid_lng,
                    "ts": ping.timestamp or datetime.now().isoformat()})
    if len(_buffer) > 10000:
        _buffer.pop(0)
    return {"status": "ok", "stored": True}

@router.get("/heatmap-raw")
def get_raw_heatmap():
    """Aggregated heatmap from ingested pings"""
    from collections import Counter
    counts = Counter((r["grid_lat"], r["grid_lng"]) for r in _buffer)
    return {"points": [{"lat":k[0],"lng":k[1],"count":v} for k,v in counts.most_common(200)]}


def get_live_density(lat: float, lng: float) -> dict:
    """
    Returns a small weighted density score around a place based on recent pings.
    Newer and closer points matter more.
    """
    if not _buffer:
        return {"weighted_density": 0.0, "sample_count": 0}

    from datetime import datetime

    now = datetime.now()
    weighted = 0.0
    samples = 0

    for row in reversed(_buffer[-500:]):
        dlat = abs(row["grid_lat"] - lat)
        dlng = abs(row["grid_lng"] - lng)
        if dlat > 0.05 or dlng > 0.05:
            continue

        try:
            ts = datetime.fromisoformat(row["ts"])
            age_minutes = max((now - ts).total_seconds() / 60.0, 0.0)
        except Exception:
            age_minutes = 60.0

        distance_factor = max(0.0, 1.0 - ((dlat + dlng) / 0.1))
        freshness_factor = max(0.15, 1.0 - (age_minutes / 180.0))
        weighted += distance_factor * freshness_factor
        samples += 1

    return {"weighted_density": round(weighted, 3), "sample_count": samples}
