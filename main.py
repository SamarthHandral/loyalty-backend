from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import math
import time
import os
from firebase_config import db
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Loyalty Card API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Add your production domains here
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)

OWNER_TOKEN = os.getenv("OWNER_TOKEN", "changeme123")


# ── Auth helper ──────────────────────────────────────────────────────────────

def verify_owner(authorization: Optional[str] = Header(None)):
    if authorization != f"Bearer {OWNER_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# ── Pydantic models ───────────────────────────────────────────────────────────

class CheckinRequest(BaseModel):
    name: str
    phone: str
    latitude: float
    longitude: float

class LoginRequest(BaseModel):
    password: str

class ShopSettings(BaseModel):
    shop_name: str
    visits_for_reward: int
    shop_lat: float
    shop_lng: float
    max_distance_meters: int
    owner_password: Optional[str] = None


# ── Utility ───────────────────────────────────────────────────────────────────

def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_settings() -> dict:
    doc = db.collection("config").document("settings").get()
    if doc.exists:
        return doc.to_dict()
    # Default settings — Mysuru city center coordinates
    return {
        "shop_name": "My Shop",
        "visits_for_reward": 10,
        "shop_lat": 12.2958,
        "shop_lng": 76.6394,
        "max_distance_meters": 100,
        "owner_password": os.getenv("OWNER_PASSWORD", "shop123"),
    }

def compute_reward(visits: int, visits_for_reward: int) -> Optional[str]:
    vr = visits_for_reward
    if visits % vr != 0:
        return None
    if visits % (vr * 3) == 0:
        return "free_item"
    if visits % (vr * 2) == 0:
        return "25_percent"
    return "10_percent"

REWARD_MESSAGES = {
    "10_percent": "10% off your next purchase!",
    "25_percent": "25% off your next purchase!",
    "free_item":  "Free item! Show this screen to the cashier.",
}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Loyalty API is running"}


@app.get("/settings/public")
def public_settings():
    """Returns non-sensitive settings for the customer page."""
    s = get_settings()
    return {
        "shop_name": s["shop_name"],
        "visits_for_reward": s["visits_for_reward"],
    }


@app.get("/settings")
def owner_settings(_: bool = Depends(verify_owner)):
    """Returns full settings for the owner settings page."""
    return {"settings": get_settings()}


@app.post("/checkin")
def checkin(body: CheckinRequest):
    settings = get_settings()

    # 1. Validate inputs
    phone = "".join(filter(str.isdigit, body.phone))
    if len(phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    # 2. GPS check
    distance = haversine_meters(
        body.latitude, body.longitude,
        settings["shop_lat"], settings["shop_lng"]
    )
    distance_int = int(round(distance))
    if distance_int > settings["max_distance_meters"]:
        raise HTTPException(
            status_code=403,
            detail=f"You are {distance_int}m away from the shop. Must be within {settings['max_distance_meters']}m."
        )

    # 3. Load or create customer
    customer_ref = db.collection("customers").document(phone)
    customer_doc = customer_ref.get()
    now_ms = int(time.time() * 1000)
    cooldown_ms = 60 * 60 * 1000  # 1 hour

    if customer_doc.exists:
        customer = customer_doc.to_dict()
    else:
        customer = {
            "name": body.name,
            "phone": phone,
            "visits": 0,
            "last_visit": 0,
            "total_rewards": 0,
        }

    # 4. Cooldown check
    time_since_last = now_ms - customer.get("last_visit", 0)
    if time_since_last < cooldown_ms:
        mins_left = math.ceil((cooldown_ms - time_since_last) / 60000)
        raise HTTPException(
            status_code=429,
            detail=f"Already checked in. Try again in {mins_left} minute(s)."
        )

    # 5. Record visit
    customer["name"] = body.name.strip()
    customer["visits"] += 1
    customer["last_visit"] = now_ms

    vr = settings["visits_for_reward"]
    reward_key = compute_reward(customer["visits"], vr)
    if reward_key:
        customer["total_rewards"] = customer.get("total_rewards", 0) + 1

    customer_ref.set(customer)

    # 6. Log visit in sub-collection for history
    customer_ref.collection("visit_log").add({
        "timestamp": now_ms,
        "lat": body.latitude,
        "lng": body.longitude,
        "distance_meters": distance_int,
    })

    cycle_visits = customer["visits"] % vr or vr
    remaining = vr - cycle_visits if not reward_key else 0

    return {
        "success": True,
        "name": customer["name"],
        "total_visits": customer["visits"],
        "cycle_visits": cycle_visits,
        "visits_for_reward": vr,
        "distance_meters": distance_int,
        "reward": reward_key,
        "reward_message": REWARD_MESSAGES.get(reward_key),
        "remaining_visits": remaining,
    }


@app.get("/customer/{phone}")
def get_customer(phone: str):
    """Customer looks up their own card."""
    phone = "".join(filter(str.isdigit, phone))
    doc = db.collection("customers").document(phone).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Customer not found")
    c = doc.to_dict()
    vr = get_settings()["visits_for_reward"]
    cycle_visits = c["visits"] % vr or (vr if c["visits"] > 0 else 0)
    return {
        "name": c["name"],
        "phone": c["phone"],
        "total_visits": c["visits"],
        "cycle_visits": cycle_visits,
        "visits_for_reward": vr,
        "total_rewards": c.get("total_rewards", 0),
    }


@app.post("/owner/login")
def owner_login(body: LoginRequest):
    settings = get_settings()
    if body.password != settings.get("owner_password", os.getenv("OWNER_PASSWORD", "shop123")):
        raise HTTPException(status_code=401, detail="Incorrect password")
    return {"token": OWNER_TOKEN}


@app.get("/dashboard")
def dashboard(_: bool = Depends(verify_owner)):
    """Returns all customers for the owner dashboard."""
    docs = db.collection("customers").stream()
    customers = []
    vr = get_settings()["visits_for_reward"]
    for doc in docs:
        c = doc.to_dict()
        cycle_visits = c["visits"] % vr or (vr if c["visits"] > 0 else 0)
        customers.append({
            "name": c["name"],
            "phone": c["phone"],
            "total_visits": c["visits"],
            "cycle_visits": cycle_visits,
            "visits_for_reward": vr,
            "total_rewards": c.get("total_rewards", 0),
            "last_visit": c.get("last_visit", 0),
        })
    customers.sort(key=lambda x: x["total_visits"], reverse=True)
    return {"customers": customers, "total": len(customers)}


@app.put("/settings")
def update_settings(body: ShopSettings, _: bool = Depends(verify_owner)):
    settings = get_settings()
    updated = {
        "shop_name": body.shop_name,
        "visits_for_reward": body.visits_for_reward,
        "shop_lat": body.shop_lat,
        "shop_lng": body.shop_lng,
        "max_distance_meters": body.max_distance_meters,
        "owner_password": body.owner_password or settings.get("owner_password", "shop123"),
    }
    db.collection("config").document("settings").set(updated)
    return {"success": True, "settings": updated}
