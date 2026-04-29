"""Prediction routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ml.predictor import PLACES, get_predictor
from utils.geocode import geocode

router = APIRouter()


class PredictReq(BaseModel):
    location_name: str
    lat: float
    lng: float
    hour: Optional[int] = None
    day_of_week: Optional[int] = None
    target_date: Optional[str] = None


@router.post("/")
def predict(req: PredictReq):
    return get_predictor().predict_full(
        req.lat,
        req.lng,
        req.location_name,
        req.hour,
        req.day_of_week,
        req.target_date,
    )


@router.get("/place")
def predict_place(
    name: str = Query(..., description="Place name"),
    hour: Optional[int] = Query(default=None, ge=0, le=23),
    day_of_week: Optional[int] = Query(default=None, ge=0, le=6),
    date: Optional[str] = Query(default=None, description="ISO date or datetime"),
):
    coords = geocode(name)
    if not coords:
        raise HTTPException(404, f"'{name}' not found")
    return get_predictor().predict_full(
        coords["lat"],
        coords["lng"],
        coords["name"],
        hour,
        day_of_week,
        date,
    )


@router.get("/realtime")
def predict_realtime(
    name: str = Query(..., description="Place name"),
    hour: Optional[int] = Query(default=None, ge=0, le=23),
    day_of_week: Optional[int] = Query(default=None, ge=0, le=6),
    date: Optional[str] = Query(default=None, description="ISO date or datetime"),
):
    return predict_place(name=name, hour=hour, day_of_week=day_of_week, date=date)


@router.get("/heatmap")
def heatmap():
    return {"locations": get_predictor().get_all_live()}


@router.get("/all-places")
def all_places():
    return {"places": PLACES}
