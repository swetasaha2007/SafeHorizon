DEMO_FLOOD_LEVEL = 1.2  # metres
DEMO_FLOOD_LABEL = "DEMO FLOOD DATA"

WEIGHTS = {"rainfall": 0.30, "wind_speed": 0.20, "flood_level": 0.50}

RAINFALL_BANDS = [
    (0.0001, 0, "No rainfall detected"),
    (2.5, 20, "Light rainfall detected"),
    (7.6, 50, "Moderate rainfall detected"),
    (50, 80, "Heavy rainfall detected"),
    (None, 100, "Very heavy rainfall detected"),
]
WIND_BANDS = [
    (20, 10, "Low wind speed"),
    (40, 40, "Moderate wind speed detected"),
    (62, 70, "Strong wind detected"),
    (None, 100, "High wind speed detected"),
]
FLOOD_BANDS = [
    (0.3, 10, "Low demo flood level"),
    (0.6, 40, "Moderate demo flood level"),
    (1.0, 70, "Elevated demo flood level"),
    (None, 100, "Severe demo flood level"),
]

ACTIONS = {
    "SAFE": "No evacuation needed. Stay alert and monitor official updates.",
    "EVACUATE": "Prepare to leave. Head to the nearest shelter while roads are passable.",
    "EVACUATE IMMEDIATELY": "Move to the nearest designated emergency shelter now.",
}


def band_score(value, bands):
    for limit, score, reason in bands:
        if limit is None or value < limit:
            return score, reason
    raise AssertionError("bands must end with an open-ended band")


def classify_score(score):
    if score <= 30:
        return "SAFE"
    if score <= 60:
        return "EVACUATE"
    return "EVACUATE IMMEDIATELY"


def _clean(name, value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number.")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number.")
    if value < 0:
        raise ValueError(f"{name} cannot be negative.")
    return value


def assess_risk(rainfall, wind_speed, flood_level=None):
    rainfall = _clean("rainfall", rainfall)
    wind_speed = _clean("wind_speed", wind_speed)
    flood_level = _clean("flood_level", flood_level)

    if flood_level is None:
        flood_level = DEMO_FLOOD_LEVEL

    rain_score, rain_reason = band_score(rainfall or 0, RAINFALL_BANDS)
    wind_score, wind_reason = band_score(wind_speed or 0, WIND_BANDS)
    flood_score, flood_reason = band_score(flood_level, FLOOD_BANDS)

    reasons = [
        "Rainfall data unavailable (treated as 0 mm)" if rainfall is None
        else f"{rain_reason} ({rainfall:g} mm)",
        "Wind speed data unavailable (treated as 0 km/h)" if wind_speed is None
        else f"{wind_reason} ({wind_speed:g} km/h)",
        f"{flood_reason} ({flood_level:g} m)",
    ]

    score = round(
        WEIGHTS["rainfall"] * rain_score
        + WEIGHTS["wind_speed"] * wind_score
        + WEIGHTS["flood_level"] * flood_score
    )
    level = classify_score(score)

    return {
        "score": score,
        "level": level,
        "action": ACTIONS[level],
        "reasons": reasons,
        "components": {
            "rainfall": {"value": rainfall, "score": rain_score, "weight": WEIGHTS["rainfall"]},
            "wind_speed": {"value": wind_speed, "score": wind_score, "weight": WEIGHTS["wind_speed"]},
            "flood_level": {"value": flood_level, "score": flood_score, "weight": WEIGHTS["flood_level"],
                            "label": DEMO_FLOOD_LABEL},
        },
    }


if __name__ == "__main__":
    import json
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "demo_scenarios.json")
    with open(path, encoding="utf-8") as f:
        scenarios = json.load(f)["scenarios"]
    for name, s in scenarios.items():
        w = s["weather"]
        r = assess_risk(w["rainfall"], w["wind_speed"], s["flood_level"])
        print(f"{name:9} rain={w['rainfall']} mm  wind={w['wind_speed']} km/h  "
              f"flood={s['flood_level']} m  ->  {r['score']:3}  {r['level']}")