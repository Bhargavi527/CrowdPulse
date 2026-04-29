"""CrowdPulse — /hotels router"""
from fastapi import APIRouter, Query
import math, random

router = APIRouter()

NAMES = [
    "The Palace View Inn","Heritage Grand","Jungle Retreat","Coastal Comfort",
    "City Centre Suites","The Spice Garden","Backwater Lodge","Summit View Resort",
"Old Quarter Homestay","Sunrise Boutique"
]

def haversine(la1,lo1,la2,lo2):
    R=6371; a=math.sin(math.radians(la2-la1)/2)**2+math.cos(math.radians(la1))*math.cos(math.radians(la2))*math.sin(math.radians(lo2-lo1)/2)**2
    return R*2*math.atan2(math.sqrt(a),math.sqrt(1-a))

@router.get("/nearby")
def nearby(lat:float=Query(...),lng:float=Query(...),limit:int=Query(6,le=10)):
    seed=int(abs(lat*1000+lng*1000))%9999
    rng=random.Random(seed)
    hotels=[]
    for i in range(limit):
        hlat=lat+rng.uniform(-0.06,0.06); hlng=lng+rng.uniform(-0.06,0.06)
        hotels.append({
            "id":f"h{seed}{i}","name":rng.choice(NAMES),
            "lat":round(hlat,4),"lng":round(hlng,4),
            "distance_km":round(haversine(lat,lng,hlat,hlng),2),
            "rating":round(rng.uniform(3.0,4.9),1),
            "price_inr":rng.choice([700,1200,1800,2500,3500,5000,7000]),
            "availability":rng.choice(["Available","Available","Limited","Full"]),
            "amenities":rng.sample(["WiFi","AC","Parking","Pool","Restaurant","Gym","Spa"],rng.randint(2,5)),
        })
    return {"hotels":sorted(hotels,key=lambda h:h["distance_km"])}
