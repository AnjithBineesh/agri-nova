import math

EARTH_RADIUS_M = 6_371_008.8


def polygon_area_ha(geom: dict) -> float:
    """Geodesic area of a GeoJSON polygon (outer ring minus holes) in hectares.

    Uses the spherical-excess line integral (Chamberlain & Duquette, 2007),
    accurate to well under 1% for field-sized polygons.
    """

    def ring_area(coords: list) -> float:
        total = 0.0
        n = len(coords)
        if n < 3:
            return 0.0
        for i in range(n - 1):
            lon1, lat1 = map(math.radians, coords[i][:2])
            lon2, lat2 = map(math.radians, coords[i + 1][:2])
            total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
        return abs(total * EARTH_RADIUS_M ** 2 / 2.0)

    rings = geom["coordinates"]
    area = ring_area(rings[0]) - sum(ring_area(r) for r in rings[1:])
    return area / 10_000.0


def point_geojson(lat: float, lon: float) -> dict:
    return {"type": "Point", "coordinates": [lon, lat]}


def polygon_centroid(geom: dict) -> tuple[float, float]:
    ring = geom["coordinates"][0][:-1]
    lat = sum(p[1] for p in ring) / len(ring)
    lon = sum(p[0] for p in ring) / len(ring)
    return lat, lon


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))
