from math import radians, sin, cos, sqrt, asin

EARTH_RADIUS_KM = 6371.0

def haversine(latitude1, longitude1, latitude2, longitude2):
    lat1, lon1, lat2, lon2 = map(radians, (latitude1, longitude1, latitude2, longitude2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def nearest_shelter(latitude, longitude, shelters):
    best, best_distance = None, None
    for shelter in shelters:
        d = haversine(latitude, longitude, shelter["latitude"], shelter["longitude"])
        if best_distance is None or d < best_distance:
            best, best_distance = shelter, d
    return best, best_distance