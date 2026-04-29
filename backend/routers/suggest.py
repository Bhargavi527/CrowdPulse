"""CrowdPulse — /suggest router"""
from fastapi import APIRouter
from pydantic import BaseModel
from ml.predictor import get_predictor

router = APIRouter()

class SuggestReq(BaseModel):
    lat: float
    lng: float
    location_name: str
    place_type: str = "heritage"

@router.post("/")
def suggest(req: SuggestReq):
    pred = get_predictor()
    comparison = pred.weekday_vs_weekend(req.lat, req.lng, req.place_type)
    full = pred.predict_full(req.lat, req.lng, req.location_name)
    fc = full["forecast_24h"]
    best  = min(fc, key=lambda x: x["pct"])
    worst = max(fc, key=lambda x: x["pct"])
    return {
        "location_name":  req.location_name,
        "best_hour":      best["hour"],
        "worst_hour":     worst["hour"],
        "best_pct":       best["pct"],
        "worst_pct":      worst["pct"],
        "comparison":     comparison,
        "tip": (f"Visit on a {comparison['better_day']} for less crowd. "
                f"Best time: {best['hour']:02d}:00 ({best['pct']:.0f}% crowd)."),
    }
