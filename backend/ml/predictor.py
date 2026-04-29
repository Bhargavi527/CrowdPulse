"""
CrowdPulse inference engine.
Supports arbitrary place names, live signal blending, and optional Groq hints.
"""

from __future__ import annotations

import json
import math
import pickle
from datetime import datetime
from typing import Optional

import numpy as np

from utils.groq_client import get_groq_place_context


PLACES = [
    {"id": "kn01", "name": "Mysore Palace", "lat": 12.3051, "lng": 76.6551, "type": "heritage", "base": 72},
    {"id": "kn02", "name": "Chamundi Hills", "lat": 12.2722, "lng": 76.6752, "type": "religious", "base": 58},
    {"id": "kn03", "name": "Hampi Virupaksha", "lat": 15.3350, "lng": 76.4600, "type": "heritage", "base": 65},
    {"id": "kn04", "name": "Jog Falls", "lat": 14.2256, "lng": 74.7986, "type": "nature", "base": 48},
    {"id": "kn05", "name": "Gokarna Beach", "lat": 14.5500, "lng": 74.3167, "type": "beach", "base": 55},
    {"id": "kn06", "name": "Coorg Abbey Falls", "lat": 12.4244, "lng": 75.9160, "type": "nature", "base": 52},
    {"id": "kn07", "name": "Udupi Krishna Temple", "lat": 13.3409, "lng": 74.7421, "type": "religious", "base": 70},
    {"id": "kn08", "name": "Badami Cave Temples", "lat": 15.9170, "lng": 75.6836, "type": "heritage", "base": 44},
    {"id": "kn09", "name": "Cubbon Park", "lat": 12.9763, "lng": 77.5929, "type": "park", "base": 60},
    {"id": "kn10", "name": "MG Road Bengaluru", "lat": 12.9762, "lng": 77.6033, "type": "shopping", "base": 78},
    {"id": "kn11", "name": "KR Market Bengaluru", "lat": 12.9650, "lng": 77.5762, "type": "market", "base": 82},
    {"id": "kn12", "name": "Lalbagh Gardens", "lat": 12.9507, "lng": 77.5848, "type": "park", "base": 56},
    {"id": "kn13", "name": "Devaraja Market Mysore", "lat": 12.3044, "lng": 76.6546, "type": "market", "base": 74},
    {"id": "kn14", "name": "Mangaluru Fish Market", "lat": 12.8628, "lng": 74.8440, "type": "market", "base": 80},
    {"id": "kn15", "name": "Shravanabelagola", "lat": 12.8572, "lng": 76.4866, "type": "religious", "base": 42},
    {"id": "kn16", "name": "Murudeshwar Temple", "lat": 14.0943, "lng": 74.4834, "type": "religious", "base": 62},
    {"id": "kn17", "name": "Belur Chennakeshava", "lat": 13.1643, "lng": 75.8642, "type": "heritage", "base": 40},
    {"id": "kn18", "name": "Jayanagar 4th Block", "lat": 12.9344, "lng": 77.5838, "type": "shopping", "base": 68},
    {"id": "kn19", "name": "BR Hills", "lat": 11.9877, "lng": 77.1241, "type": "nature", "base": 35},
    {"id": "kn20", "name": "Hubballi KSRTC Stand", "lat": 15.3647, "lng": 75.1240, "type": "transport", "base": 72},
    {"id": "kn21", "name": "Dandeli Wildlife Sanctuary", "lat": 15.2545, "lng": 74.6166, "type": "nature", "base": 30},
    {"id": "kn22", "name": "Bangalore Palace", "lat": 12.9987, "lng": 77.5921, "type": "heritage", "base": 55},
    {"id": "kn23", "name": "Chikkamagaluru Hills", "lat": 13.3153, "lng": 75.7754, "type": "nature", "base": 38},
    {"id": "kn24", "name": "Vidhana Soudha", "lat": 12.9794, "lng": 77.5912, "type": "landmark", "base": 50},
]

FESTIVALS = {
    (1, 1): 1.20,
    (1, 14): 1.55,
    (4, 14): 1.30,
    (8, 15): 1.15,
    (10, 2): 1.35,
    (10, 24): 1.60,
    (10, 31): 1.75,
    (12, 25): 1.20,
    (12, 31): 1.30,
}

HOUR_FN = {
    "heritage": lambda h: math.exp(-0.5 * ((h - 11) / 3.5) ** 2),
    "religious": lambda h: 0.9 * math.exp(-0.5 * ((h - 7) / 2) ** 2) + 0.8 * math.exp(-0.5 * ((h - 18) / 2) ** 2),
    "nature": lambda h: math.exp(-0.5 * ((h - 10) / 4) ** 2),
    "beach": lambda h: 0.25 + 0.8 * math.exp(-0.5 * ((h - 16) / 4.5) ** 2),
    "shopping": lambda h: (math.exp(-0.5 * ((h - 12) / 3) ** 2) + math.exp(-0.5 * ((h - 18) / 2.2) ** 2)) / 1.35,
    "market": lambda h: 0.8 * math.exp(-0.5 * ((h - 9) / 2.4) ** 2) + 0.75 * math.exp(-0.5 * ((h - 17) / 2.0) ** 2),
    "park": lambda h: 0.65 * math.exp(-0.5 * ((h - 8) / 2) ** 2) + 0.9 * math.exp(-0.5 * ((h - 18) / 2) ** 2),
    "transport": lambda h: 0.7 * math.exp(-0.5 * ((h - 9) / 2.2) ** 2) + 0.9 * math.exp(-0.5 * ((h - 19) / 2.8) ** 2),
    "landmark": lambda h: math.exp(-0.5 * ((h - 12) / 3.2) ** 2),
}

TYPE_ENC = list(HOUR_FN.keys())
TYPE_CAPACITY = {
    "heritage": 1800,
    "religious": 2200,
    "nature": 900,
    "beach": 1600,
    "shopping": 2600,
    "market": 3000,
    "park": 1400,
    "transport": 4200,
    "landmark": 1300,
}

TYPE_KEYWORDS = {
    "religious": ["temple", "church", "mosque", "dargah", "ashram", "matha", "gurudwara"],
    "park": ["park", "garden", "zoo", "lake"],
    "shopping": ["mall", "shopping", "road", "street", "plaza", "avenue"],
    "market": ["market", "bazaar", "mandi"],
    "transport": ["station", "airport", "bus stand", "metro", "terminal", "junction"],
    "heritage": ["fort", "palace", "museum", "monument", "cave", "ruins"],
    "nature": ["falls", "hill", "peak", "sanctuary", "forest", "valley", "dam", "wildlife"],
    "beach": ["beach", "coast", "shore"],
    "landmark": ["soudha", "circle", "tower", "square"],
}


def _pseudo(seed: int) -> float:
    return ((seed * 9301 + 49297) % 233280) / 233280


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _crowd_level(pct: float) -> str:
    if pct < 35:
        return "low"
    if pct < 68:
        return "medium"
    return "high"


def _recommendation(pct: float) -> str:
    if pct < 25:
        return "Very comfortable right now."
    if pct < 45:
        return "Good time to visit."
    if pct < 65:
        return "Manageable crowd with some waiting."
    if pct < 80:
        return "Busy period. Expect slow movement."
    return "Heavy crowd. Visit later if you can."


def _estimate_weather(month: int, lat: float, lng: float) -> tuple[float, float]:
    coastal_bias = 0.18 if lng < 75.2 else 0.0
    hill_bias = -2.5 if lat > 13.0 and lng < 76.2 else 0.0
    if month in [6, 7, 8, 9]:
        return _clamp(0.58 + coastal_bias, 0.1, 0.95), 25.0 + hill_bias
    if month in [3, 4, 5]:
        return 0.08, 31.5 + (1.2 if lat < 13.0 else 0.0) + hill_bias
    return 0.16, 27.0 + hill_bias


def _keyword_type(name: str) -> tuple[Optional[str], float]:
    lower = name.lower()
    for place_type, keywords in TYPE_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            return place_type, 0.72
    return None, 0.0


class CrowdPredictor:
    def __init__(self, model_dir: str = "models"):
        self.models_loaded = False
        self._try_load_models(model_dir)

    def _try_load_models(self, model_dir: str):
        try:
            with open(f"{model_dir}/rf.pkl", "rb") as f:
                self.rf = pickle.load(f)
            with open(f"{model_dir}/xgb.pkl", "rb") as f:
                self.xgb = pickle.load(f)
            with open(f"{model_dir}/ridge.pkl", "rb") as f:
                self.ridge = pickle.load(f)
            with open(f"{model_dir}/scaler.pkl", "rb") as f:
                self.scaler = pickle.load(f)
            with open(f"{model_dir}/weights.json", "r", encoding="utf-8") as f:
                self.weights = json.load(f)
            self.models_loaded = True
            print("Loaded production ML models")
        except FileNotFoundError:
            print("Models not found, using calibrated heuristic predictor")

    def _build_features(
        self,
        lat: float,
        lng: float,
        hour: int,
        dow: int,
        is_weekend: bool,
        month: int,
        rain_prob: float,
        temperature: float,
        festival_mult: float,
        place_type: str,
    ) -> np.ndarray:
        ptype_enc = TYPE_ENC.index(place_type) if place_type in TYPE_ENC else 0
        return np.array(
            [[
                math.sin(2 * math.pi * hour / 24),
                math.cos(2 * math.pi * hour / 24),
                math.sin(2 * math.pi * dow / 7),
                math.cos(2 * math.pi * dow / 7),
                math.sin(2 * math.pi * month / 12),
                math.cos(2 * math.pi * month / 12),
                int(is_weekend),
                int(month in [6, 7, 8, 9]),
                int(month in [4, 5, 6] and place_type in ["nature", "beach", "heritage"]),
                rain_prob,
                temperature,
                festival_mult,
                ptype_enc,
                lat,
                lng,
            ]],
            dtype=np.float32,
        )

    def _nearest_reference(self, lat: float, lng: float) -> tuple[dict, float]:
        nearest = min(PLACES, key=lambda p: _haversine_km(lat, lng, p["lat"], p["lng"]))
        return nearest, _haversine_km(lat, lng, nearest["lat"], nearest["lng"])

    def _build_place_profile(self, location_name: str, lat: float, lng: float) -> dict:
        nearest, distance_km = self._nearest_reference(lat, lng)
        keyword_type, keyword_conf = _keyword_type(location_name)
        place_type = keyword_type or nearest["type"]

        if distance_km < 2:
            base = nearest["base"]
            proximity_conf = 0.9
        elif distance_km < 10:
            blend = 1 - (distance_km - 2) / 8
            base = nearest["base"] * (0.75 + 0.25 * blend)
            proximity_conf = 0.76
        else:
            proximity_conf = 0.42
            type_bases = {
                "religious": 52,
                "park": 44,
                "shopping": 70,
                "market": 74,
                "transport": 82,
                "heritage": 48,
                "nature": 34,
                "beach": 46,
                "landmark": 40,
            }
            base = type_bases.get(place_type, 48)

        urban_boost = 8 if 12.85 <= lat <= 13.15 and 77.45 <= lng <= 77.75 else 0
        coastal_weekend_bias = 5 if lng < 75.1 and place_type in {"beach", "nature"} else 0
        pilgrimage_bias = 6 if place_type == "religious" else 0
        base = _clamp(base + urban_boost + coastal_weekend_bias + pilgrimage_bias, 18, 88)

        return {
            "place_type": place_type,
            "base": round(base, 1),
            "capacity": TYPE_CAPACITY.get(place_type, 1500),
            "reference_name": nearest["name"],
            "reference_distance_km": round(distance_km, 2),
            "heuristic_confidence": round(max(proximity_conf, keyword_conf), 2),
        }

    def _live_density_score(self, lat: float, lng: float) -> tuple[float, int]:
        try:
            from routers.location import get_live_density

            signal = get_live_density(lat, lng)
        except Exception:
            signal = {"weighted_density": 0.0, "sample_count": 0}

        weighted_density = float(signal.get("weighted_density", 0.0))
        sample_count = int(signal.get("sample_count", 0))
        live_boost = _clamp(weighted_density * 8.0, 0.0, 18.0)
        return live_boost, sample_count

    def predict_pct(
        self,
        lat: float,
        lng: float,
        hour: int,
        dow: int,
        is_weekend: bool,
        month: Optional[int] = None,
        rain_prob: float = 0.1,
        temperature: float = 28.0,
        festival_mult: float = 1.0,
        place_type: str = "heritage",
        base_level: float = 50.0,
        demand_bias: float = 0.0,
        live_boost: float = 0.0,
        special_multiplier: float = 1.0,
    ) -> tuple[float, float]:
        if month is None:
            month = datetime.now().month

        if self.models_loaded:
            X = self._build_features(lat, lng, hour, dow, is_weekend, month, rain_prob, temperature, festival_mult, place_type)
            Xs = self.scaler.transform(X)
            w = self.weights
            model_pct = (
                w["ridge"] * float(self.ridge.predict(Xs)[0])
                + w["rf"] * float(self.rf.predict(Xs)[0])
                + w["xgb"] * float(self.xgb.predict(Xs)[0])
            )
            pct = model_pct * 0.72 + base_level * 0.28
            conf = 0.91
        else:
            hfn = HOUR_FN.get(place_type, HOUR_FN["heritage"])
            hour_curve = hfn(hour)
            weekend_mult = 1.22 if is_weekend and place_type not in {"transport", "market"} else 1.0
            if is_weekend and place_type in {"beach", "nature", "shopping"}:
                weekend_mult += 0.18
            if is_weekend and place_type == "religious":
                weekend_mult += 0.10

            rain_mult = max(0.38, 1.0 - rain_prob * (0.85 if place_type in {"nature", "beach", "park"} else 0.45))
            temp_mult = 0.88 if temperature > 36 and place_type in {"heritage", "nature", "beach"} else 1.0
            seed = int(abs(lat * 100 + lng * 100 + hour * 17 + dow * 31))
            noise = (_pseudo(seed) - 0.5) * 6.5
            pct = (base_level * (0.44 + 0.82 * hour_curve) * weekend_mult * rain_mult * temp_mult * festival_mult * special_multiplier) + demand_bias + live_boost + noise
            conf = 0.84

        pct = _clamp(pct, 0.0, 100.0)
        return round(pct, 1), conf

    def predict_full(
        self,
        lat: float,
        lng: float,
        location_name: str,
        hour: Optional[int] = None,
        day_of_week: Optional[int] = None,
        target_date: Optional[str] = None,
    ) -> dict:
        now = datetime.now()
        target_dt = now
        if target_date:
            try:
                target_dt = datetime.fromisoformat(target_date)
            except ValueError:
                target_dt = now

        hour = target_dt.hour if hour is None else hour
        dow = target_dt.weekday() if day_of_week is None else day_of_week
        is_weekend = dow >= 5
        month = target_dt.month

        profile = self._build_place_profile(location_name, lat, lng)
        rain_prob, temperature = _estimate_weather(month, lat, lng)
        festival_mult = FESTIVALS.get((month, target_dt.day), 1.0)
        live_boost, live_samples = self._live_density_score(lat, lng)
        groq_context = get_groq_place_context(location_name, lat, lng, profile["place_type"])

        place_type = groq_context.get("place_type") or profile["place_type"]
        capacity = int(groq_context.get("capacity") or profile["capacity"])
        demand_bias = float(groq_context.get("demand_bias") or 0.0)
        special_multiplier = float(groq_context.get("special_multiplier") or 1.0)
        base_level = float(groq_context.get("base_level") or profile["base"])

        pct, model_conf = self.predict_pct(
            lat=lat,
            lng=lng,
            hour=hour,
            dow=dow,
            is_weekend=is_weekend,
            month=month,
            rain_prob=rain_prob,
            temperature=temperature,
            festival_mult=festival_mult,
            place_type=place_type,
            base_level=base_level,
            demand_bias=demand_bias,
            live_boost=live_boost,
            special_multiplier=special_multiplier,
        )

        forecast_24h = self._forecast_24h(
            lat=lat,
            lng=lng,
            dow=dow,
            month=month,
            place_type=place_type,
            base_level=base_level,
            rain_prob=rain_prob,
            temperature=temperature,
            festival_mult=festival_mult,
            live_boost=live_boost,
            demand_bias=demand_bias,
            special_multiplier=special_multiplier,
        )

        best = min(forecast_24h, key=lambda item: item["pct"])
        worst = max(forecast_24h, key=lambda item: item["pct"])
        confidence = _clamp(
            model_conf
            - (0.12 if profile["reference_distance_km"] > 15 else 0.0)
            + (0.05 if groq_context.get("used") else 0.0)
            + min(0.08, live_samples * 0.01),
            0.55,
            0.98,
        )
        current_count = round(capacity * pct / 100)
        level = _crowd_level(pct)
        recommendation = _recommendation(pct)
        best_time_advice = f"Best window around {best['hour']:02d}:00 with about {best['pct']:.0f}% crowd."

        response = {
            "location_name": location_name,
            "locationName": location_name,
            "lat": lat,
            "lng": lng,
            "place_type": place_type,
            "placeType": place_type,
            "crowd_pct": pct,
            "crowdPercentage": pct,
            "level": level,
            "crowdLevel": level.upper(),
            "confidence": round(confidence, 2),
            "capacity": capacity,
            "current_count": current_count,
            "currentCount": current_count,
            "recommendation": recommendation,
            "best_hour": best["hour"],
            "bestHour": best["hour"],
            "worst_hour": worst["hour"],
            "worstHour": worst["hour"],
            "best_pct": best["pct"],
            "worst_pct": worst["pct"],
            "bestTimeAdvice": best_time_advice,
            "go_now": pct < 38,
            "avoid_now": pct > 72,
            "forecast_24h": forecast_24h,
            "hourlyBreakdown": [{"hour": item["hour"], "label": item["clock_label"], "crowdPct": item["pct"]} for item in forecast_24h],
            "model": "ensemble-v3" if self.models_loaded else "heuristic-v3",
            "predicted_at": now.isoformat(),
            "lastUpdated": now.isoformat(),
            "target_date": target_dt.isoformat(),
            "live_signals": {
                "live_boost": round(live_boost, 2),
                "gps_samples": live_samples,
                "festival_multiplier": festival_mult,
                "rain_probability": round(rain_prob, 2),
                "temperature_c": round(temperature, 1),
            },
            "reference_match": {
                "name": profile["reference_name"],
                "distance_km": profile["reference_distance_km"],
                "heuristic_confidence": profile["heuristic_confidence"],
            },
            "groq": groq_context,
        }
        return response

    def _forecast_24h(
        self,
        lat: float,
        lng: float,
        dow: int,
        month: int,
        place_type: str,
        base_level: float,
        rain_prob: float,
        temperature: float,
        festival_mult: float,
        live_boost: float,
        demand_bias: float,
        special_multiplier: float,
    ) -> list:
        result = []
        for hour in range(24):
            hour_dow = dow
            is_weekend = hour_dow >= 5
            pct, _ = self.predict_pct(
                lat=lat,
                lng=lng,
                hour=hour,
                dow=hour_dow,
                is_weekend=is_weekend,
                month=month,
                rain_prob=rain_prob,
                temperature=temperature,
                festival_mult=festival_mult,
                place_type=place_type,
                base_level=base_level,
                demand_bias=demand_bias,
                live_boost=live_boost * 0.55,
                special_multiplier=special_multiplier,
            )
            result.append(
                {
                    "hour": hour,
                    "pct": pct,
                    "level": _crowd_level(pct),
                    "label": "best" if pct < 30 else "quiet" if pct < 50 else "busy" if pct < 68 else "peak",
                    "clock_label": f"{hour % 12 or 12}:00 {'AM' if hour < 12 else 'PM'}",
                }
            )
        return result

    def get_all_live(self) -> list:
        now = datetime.now()
        locations = []
        for place in PLACES:
            prediction = self.predict_full(place["lat"], place["lng"], place["name"], hour=now.hour, day_of_week=now.weekday())
            locations.append(
                {
                    "id": place["id"],
                    "name": place["name"],
                    "lat": place["lat"],
                    "lng": place["lng"],
                    "type": prediction["place_type"],
                    "crowd_pct": prediction["crowd_pct"],
                    "level": prediction["level"],
                    "confidence": prediction["confidence"],
                }
            )
        return locations

    def weekday_vs_weekend(self, lat: float, lng: float, place_type: str = "heritage") -> dict:
        hours = list(range(8, 22))
        now = datetime.now()
        weekday = [
            self.predict_pct(lat, lng, h, 2, False, now.month, place_type=place_type, base_level=TYPE_CAPACITY.get(place_type, 1500) / 35)[0]
            for h in hours
        ]
        weekend = [
            self.predict_pct(lat, lng, h, 6, True, now.month, place_type=place_type, base_level=TYPE_CAPACITY.get(place_type, 1500) / 35)[0]
            for h in hours
        ]
        return {
            "weekday_avg": round(sum(weekday) / len(weekday), 1),
            "weekend_avg": round(sum(weekend) / len(weekend), 1),
            "better_day": "weekday" if sum(weekday) < sum(weekend) else "weekend",
            "weekday_hourly": [{"hour": hour, "pct": pct} for hour, pct in zip(hours, weekday)],
            "weekend_hourly": [{"hour": hour, "pct": pct} for hour, pct in zip(hours, weekend)],
        }


_predictor: Optional[CrowdPredictor] = None


def get_predictor() -> CrowdPredictor:
    global _predictor
    if _predictor is None:
        _predictor = CrowdPredictor()
    return _predictor
