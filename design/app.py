import json
import os
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

import risk_engine
from distance import nearest_shelter

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
SHELTERS_FILE = os.path.join(BASE_DIR, "data", "shelters.json")
DEMO_FILE = os.path.join(BASE_DIR, "data", "demo_scenarios.json")

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "44e196b38716de97704554b56890f956").strip()

WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"
REQUEST_TIMEOUT = 8  # seconds

app = Flask(__name__, static_folder=None)


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@app.errorhandler(ApiError)
def handle_api_error(err):
    return jsonify({"error": err.message}), err.status


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def parse_coordinates(payload):
    if not isinstance(payload, dict):
        raise ApiError("Request body must be JSON.")

    try:
        lat = float(payload.get("latitude"))
        lng = float(payload.get("longitude"))
    except (TypeError, ValueError):
        raise ApiError("Invalid coordinates. Latitude and longitude must be numbers.")

    if not -90 <= lat <= 90:
        raise ApiError("Invalid latitude. It must be between -90 and 90.")
    if not -180 <= lng <= 180:
        raise ApiError("Invalid longitude. It must be between -180 and 180.")

    return round(lat, 6), round(lng, 6)


def call_openweather(url, params):
    if not OPENWEATHER_API_KEY or OPENWEATHER_API_KEY == "your_api_key_here":
        raise ApiError("Weather service is not configured. Add OPENWEATHER_API_KEY to the .env file.", 500)

    try:
        res = requests.get(url, params={**params, "appid": OPENWEATHER_API_KEY}, timeout=REQUEST_TIMEOUT)
    except requests.Timeout:
        raise ApiError("The weather service took too long to respond. Please try again.", 504)
    except requests.RequestException:
        raise ApiError("Could not reach the weather service. Check your internet connection.", 503)

    if res.status_code == 401:
        raise ApiError("The weather service rejected the API key. Check OPENWEATHER_API_KEY in .env.", 502)
    if res.status_code == 429:
        raise ApiError("Weather service request limit reached. Please wait a moment and try again.", 503)
    if res.status_code != 200:
        raise ApiError("The weather service returned an error. Please try again later.", 502)

    try:
        return res.json()
    except ValueError:
        raise ApiError("The weather service returned an unreadable response.", 502)


def get_weather(lat, lng):
    data = call_openweather(WEATHER_URL, {"lat": lat, "lon": lng, "units": "metric"})

    try:
        main = data["main"]
        temperature = main["temp"]
        humidity = main["humidity"]
        wind_ms = data.get("wind", {}).get("speed", 0)
        condition = data["weather"][0]["description"]
    except (KeyError, IndexError, TypeError):
        raise ApiError("Weather data for this location is incomplete. Please try again later.", 502)

    rain = data.get("rain") or {}
    rainfall = rain.get("1h", rain.get("3h", 0))

    return {
        "temperature": round(temperature, 1),
        "rainfall": round(rainfall, 1),
        "wind_speed": round(wind_ms * 3.6, 1),   # m/s -> km/h
        "humidity": humidity,
        "condition": condition.title(),
    }, data.get("name") or None


def geocode(query):
    results = call_openweather(GEOCODE_URL, {"q": query, "limit": 5})
    if not results:
        raise ApiError(f'Location "{query}" was not found. Try a nearby city name.', 404)
    place = next((p for p in results if p.get("country") == "IN"), results[0])
    return place["lat"], place["lon"], place.get("name", query)


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------
@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/location")
def location():
    lat, lng = parse_coordinates(request.get_json(silent=True))
    return jsonify({"latitude": lat, "longitude": lng})


@app.post("/api/analyze")
def analyze():
    payload = request.get_json(silent=True)
    name = None

    if isinstance(payload, dict) and str(payload.get("query", "")).strip():
        lat, lng, name = geocode(str(payload["query"]).strip())
        lat, lng = round(lat, 6), round(lng, 6)
    else:
        lat, lng = parse_coordinates(payload)

    weather, weather_place = get_weather(lat, lng)

    return jsonify({
        "location": {
            "latitude": lat,
            "longitude": lng,
            "name": name or weather_place or "Your current location",
        },
        "weather": weather,
        "flood_level": {
            "value": risk_engine.DEMO_FLOOD_LEVEL,
            "unit": "m",
            "label": risk_engine.DEMO_FLOOD_LABEL,   # simulated, NOT a live measurement
        },
    })


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_shelters():
    try:
        return load_json(SHELTERS_FILE)["shelters"]
    except (OSError, ValueError, KeyError):
        raise ApiError("Shelter data could not be loaded (data/shelters.json).", 500)


def google_maps_route_url(origin_lat, origin_lng, dest_lat, dest_lng):
    return "https://www.google.com/maps/dir/?" + urlencode({
        "api": 1,
        "origin": f"{origin_lat},{origin_lng}",
        "destination": f"{dest_lat},{dest_lng}",
        "travelmode": "driving",
    }, safe=",")


def build_assessment(lat, lng, rainfall, wind_speed, flood_level):
    try:
        risk = risk_engine.assess_risk(rainfall, wind_speed, flood_level)
    except ValueError as err:
        raise ApiError(f"Invalid input: {err}")

    shelter, distance_km = nearest_shelter(lat, lng, load_shelters())
    if shelter is None:
        raise ApiError("No emergency shelter was found in the shelter data.", 500)

    return {
        "risk": risk,
        "flood_level": {
            "value": risk["components"]["flood_level"]["value"],
            "unit": "m",
            "label": risk_engine.DEMO_FLOOD_LABEL,
        },
        "shelter": {k: shelter[k] for k in ("name", "address", "latitude", "longitude", "capacity")},
        "distance_km": round(distance_km, 2),
        "route": {
            "label": "Suggested Evacuation Route",
            "travelmode": "driving",
            "url": google_maps_route_url(lat, lng, shelter["latitude"], shelter["longitude"]),
        },
    }


@app.post("/api/assess-risk")
def assess_risk():
    payload = request.get_json(silent=True)
    lat, lng = parse_coordinates(payload)
    return jsonify(build_assessment(
        lat, lng, payload.get("rainfall"), payload.get("wind_speed"), payload.get("flood_level")))


@app.get("/api/demo/<name>")
def demo(name):
    scenarios = load_json(DEMO_FILE)["scenarios"]
    if name not in scenarios:
        raise ApiError("Unknown demo scenario. Use low, moderate or high.", 404)

    s = scenarios[name]
    loc, weather = s["location"], s["weather"]
    result = build_assessment(loc["latitude"], loc["longitude"],
                              weather["rainfall"], weather["wind_speed"], s["flood_level"])
    return jsonify({"demo": True, "scenario": name, "title": s["title"],
                    "location": loc, "weather": weather, **result})


@app.get("/api/shelters")
def shelters():
    return jsonify(load_json(SHELTERS_FILE))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
