# Flood Evacuation Route Planner

**Risk awareness and evacuation assistance system — Design Thinking Laboratory project**

> **Prototype**
> - The **flood level is simulated demo data**, not a sensor reading.
> - The **risk thresholds are prototype thresholds**, not official government thresholds.
> - The **shelters are fictional demonstration data**.



---

## 1. Problem statement

During floods, citizens may lose valuable evacuation time because they do not know their current risk level, the nearest emergency shelter, or how to reach it.

## 2. Proposed solution

A simple web dashboard where a citizen enters their location (or shares it from the browser) and immediately sees, in order of importance:

**RISK → RECOMMENDED ACTION → NEAREST SHELTER → EVACUATION ROUTE**

The system combines live weather (OpenWeather) with a demo flood level, calculates a transparent rule-based risk score, finds the nearest shelter, and opens a suggested driving route in Google Maps.

## 3. Target users

- Citizens living in flood-prone areas who need a quick "should I leave, and where do I go?" answer.
- Students, evaluators and local-awareness groups exploring how such a tool could work.

## 4. Features

| Feature | Description |
|---|---|
| Location input | Type a place name, or use the browser's location (with permission) |
| Live weather | Temperature, rainfall, wind speed, humidity and condition from OpenWeather |
| Demo flood level | Simulated value, clearly labelled **DEMO FLOOD DATA** |
| Risk assessment | Score 0–100, level (SAFE / EVACUATE / EVACUATE IMMEDIATELY), recommended action, reasons |
| Nearest shelter | Haversine distance to every demo shelter; the closest is shown |
| Evacuation route | "OPEN EVACUATION ROUTE" opens Google Maps driving directions in a new tab |
| Demo mode | Low / Moderate / High risk scenarios that work without internet APIs or location access |
| Error handling | Clear messages for permission denied, unknown place, API failures, invalid input, etc. |
| Responsive UI | Works on desktop, tablet and mobile |

## 5. Technology stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, vanilla JavaScript (`fetch()`, `navigator.geolocation`) |
| Backend | Python, Flask |
| HTTP client | `requests` |
| Configuration | `python-dotenv` (`.env` file for the API key) |
| Weather data | OpenWeather Current Weather + Geocoding APIs |
| Maps | Google Maps Directions **URL** (no SDK, no Maps API key) |
| Data | JSON files (no database) |

## 6. System architecture

```
┌────────────────────────── Browser ──────────────────────────┐
│  frontend/index.html + style.css + script.js                │
│  - location input / navigator.geolocation                   │
│  - displays results only (no calculations)                  │
└───────────────┬─────────────────────────────────────────────┘
                │ fetch() JSON
┌───────────────▼──────────── Flask (app.py) ─────────────────┐
│  /api/analyze      ── requests ──► OpenWeather API          │
│  /api/assess-risk  ──► risk_engine.py  (score, level)       │
│                    ──► distance.py     (nearest shelter)    │
│                    ──► Google Maps directions URL           │
│  /api/demo/<name>  ──► data/demo_scenarios.json             │
│                        data/shelters.json                   │
│  .env  (OPENWEATHER_API_KEY — never sent to the browser)    │
└─────────────────────────────────────────────────────────────┘
```

### Project structure

```
├── app.py                  Flask server + API endpoints + route URL
├── risk_engine.py          Rule-based risk score, level, reasons, DEMO_FLOOD_LEVEL
├── distance.py             Haversine formula + nearest shelter
├── test_project.py         Automated tests (unittest)
├── requirements.txt
├── .env                    OPENWEATHER_API_KEY (keep private)
├── data/
│   ├── shelters.json       8 fictional demo shelters (Kolkata area)
│   └── demo_scenarios.json Low / moderate / high demo scenarios
└── frontend/
    ├── index.html
    ├── style.css
    └── script.js
```

### API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | `{"status": "ok"}` |
| POST | `/api/location` | Validates and echoes `{latitude, longitude}` |
| POST | `/api/analyze` | `{latitude, longitude}` or `{query}` → location, weather, demo flood level |
| POST | `/api/assess-risk` | `{latitude, longitude, rainfall, wind_speed, flood_level}` → risk, shelter, distance, route |
| GET | `/api/demo/<low\|moderate\|high>` | Complete result from predefined demo data |
| GET | `/api/shelters` | The demo shelter list |

## 7. Data flow

```
User
 ↓  types a place / clicks "Use My Location"
Latitude + Longitude            (browser geolocation → POST /api/location, or geocoding)
 ↓
Weather API                      POST /api/analyze → OpenWeather
 ↓
Rainfall + Wind + Weather
 ↓
Demo Flood Level                 risk_engine.DEMO_FLOOD_LEVEL
 ↓
Risk Engine                      POST /api/assess-risk
 ↓
Risk Score → SAFE / EVACUATE / EVACUATE IMMEDIATELY
 ↓
Nearest Shelter + Distance       Haversine over data/shelters.json
 ↓
OPEN EVACUATION ROUTE  →  Google Maps (new tab)
```

## 8. Risk assessment methodology

The risk engine (`risk_engine.py`) is **rule-based and deterministic** — the same inputs always give the same result. No machine learning is used.

**Step 1 — each input is placed in a band with a fixed score (0–100):**

| Rainfall (mm, last hour) | Score | Wind speed (km/h) | Score | Demo flood level (m) | Score |
|---|---|---|---|---|---|
| 0 (none) | 0 | < 20 (low) | 10 | < 0.3 (low) | 10 |
| < 2.5 (light) | 20 | 20–40 (moderate) | 40 | 0.3–0.6 (moderate) | 40 |
| 2.5–7.6 (moderate) | 50 | 40–62 (strong) | 70 | 0.6–1.0 (high) | 70 |
| 7.6–50 (heavy) | 80 | ≥ 62 (high) | 100 | ≥ 1.0 (severe) | 100 |
| ≥ 50 (very heavy) | 100 | | | | |

A value exactly on a limit belongs to the higher band.

**Step 2 — weighted combination:**

```
Risk Score = 0.30 × Rainfall Score + 0.20 × Wind Score + 0.50 × Flood Score     (rounded)
```

- **Flood level 50%** — standing/moving water is the most direct danger to people.
- **Rainfall 30%** — rainfall is what makes water levels rise.
- **Wind 20%** — adds danger (debris, fallen trees) but does not flood roads by itself.

**Step 3 — classification (prototype thresholds, NOT official):**

| Score | Level | Recommended action |
|---|---|---|
| 0–30 | SAFE | No evacuation needed. Stay alert and monitor official updates. |
| 31–60 | EVACUATE | Prepare to leave. Head to the nearest shelter while roads are passable. |
| 61–100 | EVACUATE IMMEDIATELY | Move to the nearest designated emergency shelter now. |

**Reasons:** one human-readable reason is returned per factor, e.g. *"Heavy rainfall detected (20 mm)"*, *"Strong wind detected (50 km/h)"*, *"Elevated demo flood level (0.8 m)"*.

**Missing values:** missing rainfall or wind is treated as 0 and reported as *"… data unavailable"*; a missing flood level uses the demo value. Negative or non-numeric values are rejected.

**Worked example (High Risk demo):** rainfall 20 mm → 80, wind 50 km/h → 70, flood 0.8 m → 70
`0.30×80 + 0.20×70 + 0.50×70 = 24 + 14 + 35 = 73` → **EVACUATE IMMEDIATELY**

## 9. Haversine formula

The distance between the citizen and each shelter is the great-circle ("straight-line") distance on the Earth's surface:

```
a = sin²(Δφ/2) + cos φ1 · cos φ2 · sin²(Δλ/2)
d = 2R · asin(√a)          R = 6371 km
```

where φ is latitude and λ is longitude, both in radians. Implemented in `distance.py → haversine()`. Road distance will be longer than this value.

## 10. Weather API

- Endpoint: OpenWeather **Current Weather** (`/data/2.5/weather`, metric units). Typed place names are converted to coordinates with the OpenWeather **Geocoding** API.
- The API key is stored in `.env` and used **only by the Flask backend**; it never reaches the browser.
- The backend returns only what is needed:

| Field | Source | Unit |
|---|---|---|
| `temperature` | `main.temp` | °C |
| `rainfall` | `rain.1h` (fallback `rain.3h`) | mm |
| `wind_speed` | `wind.speed` × 3.6 | km/h |
| `humidity` | `main.humidity` | % |
| `condition` | `weather[0].description` | text |

**Rainfall behaviour:** OpenWeather only includes a `rain` object while it is raining, so when it is absent the backend returns `0`.

## 11. Demo flood-level data

There are no real flood sensors in this project. The flood level is a **simulated value** defined in one place:

```python
# risk_engine.py
DEMO_FLOOD_LEVEL = 1.2  # metres
```

It is labelled **DEMO FLOOD DATA** everywhere it appears (API responses and dashboard). Change this value to demonstrate different conditions.

> Note: 1.2 m is in the "severe" band, which alone adds 50 points. With real weather, the minimum score is therefore about 52 (EVACUATE), even on a dry day. Lower the value (e.g. `0.2`) if you want real-weather results to depend mainly on the weather.

### Demo mode

`data/demo_scenarios.json` defines three complete scenarios (location, weather, flood level). They run through the **same** risk engine, shelter search and route builder as real data, but need no weather API and no browser location — so the whole system can be demonstrated reliably offline from external services.

| Scenario | Location | Rain | Wind | Flood | Score | Level | Nearest shelter |
|---|---|---|---|---|---|---|---|
| Low | Demo: New Town, Kolkata | 1 mm | 10 km/h | 0.1 m | 13 | SAFE | Shelter 2, Salt Lake (4.41 km) |
| Moderate | Demo: Kasba, Kolkata | 5 mm | 30 km/h | 0.4 m | 43 | EVACUATE | Shelter 5, Jadavpur (2.41 km) |
| High | Demo: Kidderpore, Kolkata | 20 mm | 50 km/h | 0.8 m | 73 | EVACUATE IMMEDIATELY | Shelter 1, Park Street (3.41 km) |

The dashboard opens in the High Risk demo scenario, and shows **DEMO DATA** labels whenever demo mode is active.

## 12. Nearest shelter calculation

`distance.py → nearest_shelter()` computes the Haversine distance from the citizen to **every** shelter in `data/shelters.json` and returns the one with the smallest distance (rounded to 0.01 km). The 8 shelters are **fictional demonstration shelters** around Kolkata — Park Street, Salt Lake, Howrah, Behala, Jadavpur, Dum Dum, Garia and Shyambazar (each has `"demo": true`). For locations outside Kolkata the "nearest" shelter can be very far away.

## 13. Google Maps integration

No Maps SDK or API key is used. The backend builds a standard Google Maps Directions URL:

```
https://www.google.com/maps/dir/?api=1
    &origin=<citizen latitude>,<citizen longitude>
    &destination=<shelter latitude>,<shelter longitude>
    &travelmode=driving
```

Clicking **OPEN EVACUATION ROUTE** opens it in a new tab. The dashboard calls it a **"Suggested Evacuation Route"** — Google Maps does not know which roads are flooded, so the route is **not guaranteed to be safe**. If no route can be created, the button is disabled and a message is shown. The map on the dashboard is an illustration only.

## 14. Installation

Requirements: **Python 3.9+** and an internet connection (for live weather).

```bash
pip install -r requirements.txt
```

Get a free API key from <https://openweathermap.org/api> and put it in `.env`:

```
OPENWEATHER_API_KEY=your_real_key_here
```

(New OpenWeather keys can take a while to activate. Demo mode works without a key.)

## 15. How to run

```bash
python app.py
```

Open **http://127.0.0.1:5000** in a browser.

- **Analyze Location** — type a place (e.g. `Kolkata` or `Salt Lake, Kolkata`).
- **Use My Location** — allow location access when the browser asks (works on `localhost`/`127.0.0.1`).
- **Demo mode** — click *Low risk*, *Moderate risk* or *High risk*.

Run the automated tests (24 tests: scenarios, boundaries, missing/invalid values, Haversine, nearest shelter, route URL, demo mode, API errors):

```bash
python -m unittest test_project -v
```

Print the three demo scenarios from the risk engine:

```bash
python risk_engine.py
```

### Error messages

| Situation | What the user sees |
|---|---|
| Location permission denied | "Unable to access your location: permission was denied…" |
| Place not found | "Location "…" was not found. Try a nearby city name." |
| Empty input | "Please enter a location to analyze." |
| Invalid coordinates | "Invalid latitude/longitude…" |
| API key missing / rejected | "Weather service is not configured…" / "…rejected the API key…" |
| Weather API down / timeout / offline | "The weather service returned an error / took too long / could not be reached…" |
| Incomplete weather data | "Weather data for this location is incomplete…" |
| No shelter available | "No emergency shelter was found in the shelter data." |
| Route could not be built | Route button disabled + message |
| Flask not running | "Cannot reach the server. Make sure Flask is running (python app.py)." |

Every failure also suggests using Demo mode.

## 16. Limitations

- **Not an official warning system**; for demonstration and learning only.
- **Flood level is simulated** — there is no sensor or river-gauge data.
- **Thresholds and weights are prototype choices**, not validated by hydrologists or authorities.
- **Shelters are fictional**, and their capacity/availability is not tracked.
- **Straight-line distance** is used to choose the shelter; the nearest shelter by road may differ.
- **Google Maps routes do not consider flooding**; roads on the route may be unsafe.
- Weather is current conditions only (no forecast), and rainfall is only reported while it is raining.
- Requires an internet connection and an OpenWeather key for live data.

## 17. Future improvements

- Real flood-level data from river gauges or government open-data feeds.
- Weather forecasts and official alerts (e.g. IMD) as additional risk factors.
- Terrain elevation and historical flood zones in the risk score.
- Real, verified shelter data with live capacity.
- Routing that avoids reported flooded roads.
- Multi-language support, SMS/offline access, and accessibility testing with real users.
- Validation of thresholds with domain experts.

---

*Design Thinking Laboratory — university working prototype.*
