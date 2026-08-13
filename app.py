from flask import Flask, jsonify, render_template

from services.austria import fetch_austria_data

app = Flask(__name__)

# Conservative placeholder vessel assumptions for the first navigation-status
# prototype. These are deliberately configurable and are NOT yet Scenic-specific.
VESSEL_DRAFT_M = 1.50
SAFETY_MARGIN_M = 0.30

ROUTE = [
    {"name": "Budapest", "lat": 47.4979, "lon": 19.0402, "status": "unknown"},
    {"name": "Bratislava", "lat": 48.1486, "lon": 17.1077, "status": "unknown"},
    {"name": "Vienna", "lat": 48.2082, "lon": 16.3738, "status": "unknown"},
    {"name": "Wachau", "lat": 48.3892, "lon": 15.4690, "status": "unknown"},
    {"name": "Linz", "lat": 48.3069, "lon": 14.2858, "status": "unknown"},
    {"name": "Passau", "lat": 48.5667, "lon": 13.4319, "status": "unknown"},
    {"name": "Vilshofen", "lat": 48.6268, "lon": 13.1877, "status": "unknown"},
    {"name": "Regensburg", "lat": 49.0134, "lon": 12.1016, "status": "unknown"},
]

AUSTRIAN_SEGMENT_RANGES = {
    "Bratislava": {"to": "Vienna", "river_km_min": 1872.7, "river_km_max": 1921.0},
    "Vienna": {"to": "Wachau", "river_km_min": 1921.0, "river_km_max": 2010.0},
    "Wachau": {"to": "Linz", "river_km_min": 2010.0, "river_km_max": 2135.5},
    "Linz": {"to": "Passau", "river_km_min": 2135.5, "river_km_max": 2223.2},
}

# River-km locations of Austrian Danube locks, from the DoRIS closure overview.
LOCK_RIVER_KM = {
    "Aschach": 2162.0,
    "Ottensheim": 2147.0,
    "Abwinden": 2119.0,
    "Wallsee": 2095.0,
    "Ybbs": 2060.0,
    "Melk": 2038.0,
    "Altenwörth": 1980.0,
    "Greifenstein": 1949.0,
    "Freudenau": 1921.0,
}

# DoRIS states that navigation between Freudenau and the Slovak border can be
# prohibited when Wildungsmauer exceeds 600 cm. We conservatively mark our whole
# Bratislava->Vienna display segment red when that threshold is reached.
WILDUNGSMAUER_HIGH_WATER_CM = 600

STATUS_RANK = {"unknown": 0, "green": 1, "yellow": 2, "red": 3}


def _status_for_depth(minimum_depth):
    if minimum_depth is None:
        return "green"
    if minimum_depth < VESSEL_DRAFT_M:
        return "red"
    if minimum_depth < VESSEL_DRAFT_M + SAFETY_MARGIN_M:
        return "yellow"
    return "green"


def _section_midpoint_km(section):
    start = section.get("river_km_from")
    end = section.get("river_km_to")
    if start is None or end is None:
        return None
    return (start + end) / 2


def _range_overlaps(a_min, a_max, b_from, b_to):
    if b_from is None or b_to is None:
        return False
    b_min, b_max = sorted((b_from, b_to))
    return max(a_min, b_min) <= min(a_max, b_max)


def _gauge_level(austria_data, name):
    for gauge in austria_data.gauges:
        if gauge.get("name", "").lower() == name.lower():
            return gauge.get("level_cm")
    return None


def _locks_for_segment(austria_data, km_min, km_max):
    relevant = []
    for lock in austria_data.locks:
        km = LOCK_RIVER_KM.get(lock.get("name"))
        if km is not None and km_min <= km <= km_max:
            item = lock.copy()
            item["river_km"] = km
            relevant.append(item)
    return relevant


def _closures_for_segment(austria_data, km_min, km_max):
    return [
        closure
        for closure in austria_data.closures
        if _range_overlaps(
            km_min,
            km_max,
            closure.get("river_km_from"),
            closure.get("river_km_to"),
        )
        and not closure.get("is_open", False)
    ]


def _austrian_segment_statuses(austria_data):
    """Combine low-water depth, official closures, locks, and high water."""
    results = {}

    if austria_data.error:
        for from_stop, config in AUSTRIAN_SEGMENT_RANGES.items():
            results[from_stop] = {
                "from": from_stop,
                "to": config["to"],
                "status": "unknown",
                "minimum_depth_m": None,
                "shallow_sections": [],
                "closures": [],
                "locks": [],
                "reasons": ["DoRIS data unavailable"],
            }
        return results

    wildungsmauer = _gauge_level(austria_data, "Wildungsmauer")

    for from_stop, config in AUSTRIAN_SEGMENT_RANGES.items():
        km_min = config["river_km_min"]
        km_max = config["river_km_max"]

        relevant_sections = []
        for section in austria_data.shallow_sections:
            midpoint = _section_midpoint_km(section)
            if midpoint is not None and km_min <= midpoint <= km_max:
                relevant_sections.append(section)

        depths = [
            section.get("deep_channel_depth_m")
            for section in relevant_sections
            if section.get("deep_channel_depth_m") is not None
        ]
        minimum_depth = min(depths) if depths else None
        depth_status = _status_for_depth(minimum_depth)

        closures = _closures_for_segment(austria_data, km_min, km_max)
        locks = _locks_for_segment(austria_data, km_min, km_max)

        status = depth_status
        reasons = []
        if relevant_sections:
            reasons.append("Low-water depth from mapped DoRIS shallow sections")
        else:
            reasons.append("No current DoRIS shallow section mapped to this route segment")

        if closures:
            status = "red"
            reasons.append("Official DoRIS navigation closure affects this segment")

        if any(lock.get("both_closed") for lock in locks):
            status = "red"
            reasons.append("Both chambers unavailable at a lock in this segment")
        elif any(lock.get("one_closed") for lock in locks) and STATUS_RANK[status] < STATUS_RANK["yellow"]:
            status = "yellow"
            reasons.append("One lock chamber unavailable in this segment")

        high_water = False
        if (
            from_stop == "Bratislava"
            and wildungsmauer is not None
            and wildungsmauer >= WILDUNGSMAUER_HIGH_WATER_CM
        ):
            status = "red"
            high_water = True
            reasons.append(
                f"Wildungsmauer {wildungsmauer:.0f} cm is at/above the 600 cm DoRIS high-water threshold"
            )

        results[from_stop] = {
            "from": from_stop,
            "to": config["to"],
            "river_km_min": km_min,
            "river_km_max": km_max,
            "status": status,
            "depth_status": depth_status,
            "minimum_depth_m": minimum_depth,
            "shallow_sections": relevant_sections,
            "closures": closures,
            "locks": locks,
            "high_water_override": high_water,
            "wildungsmauer_level_cm": wildungsmauer if from_stop == "Bratislava" else None,
            "reasons": reasons,
        }

    return results


def _austria_navigation_status(austria_data):
    segment_statuses = _austrian_segment_statuses(austria_data)
    worst = max(segment_statuses.values(), key=lambda item: STATUS_RANK[item["status"]])
    depths = [
        item["minimum_depth_m"]
        for item in segment_statuses.values()
        if item["minimum_depth_m"] is not None
    ]
    return worst["status"], min(depths) if depths else None


def _route_with_austria_status(austria_data):
    route = [stop.copy() for stop in ROUTE]
    segment_statuses = _austrian_segment_statuses(austria_data)

    for stop in route:
        segment = segment_statuses.get(stop["name"])
        if not segment:
            continue
        stop["status"] = segment["status"]
        stop["status_source"] = "DoRIS depth + closures + lock states + high-water rules"
        stop["minimum_depth_m"] = segment["minimum_depth_m"]
        stop["segment_to"] = segment["to"]
        stop["segment_reasons"] = segment["reasons"]
        stop["shallow_section_names"] = [s["name"] for s in segment["shallow_sections"]]
        stop["closure_names"] = [c["name"] for c in segment["closures"]]
        stop["lock_states"] = [
            f"{lock['name']}: left {lock['left_chamber']}, right {lock['right_chamber']}"
            for lock in segment["locks"]
        ]
        stop["high_water_override"] = segment["high_water_override"]

    return route


@app.route("/")
def index():
    austria = fetch_austria_data()
    route = _route_with_austria_status(austria)
    segment_statuses = _austrian_segment_statuses(austria)
    status, minimum_depth = _austria_navigation_status(austria)
    return render_template(
        "index.html",
        route=route,
        austria=austria.to_dict(),
        austria_segments=list(segment_statuses.values()),
        austria_status=status,
        austria_minimum_depth=minimum_depth,
        vessel_draft_m=VESSEL_DRAFT_M,
        safety_margin_m=SAFETY_MARGIN_M,
        high_water_threshold_cm=WILDUNGSMAUER_HIGH_WATER_CM,
    )


@app.route("/api/austria")
def api_austria():
    austria = fetch_austria_data()
    segment_statuses = _austrian_segment_statuses(austria)
    status, minimum_depth = _austria_navigation_status(austria)
    payload = austria.to_dict()
    payload.update(
        {
            "navigation_status": status,
            "minimum_deep_channel_depth_m": minimum_depth,
            "segment_statuses": list(segment_statuses.values()),
            "assumed_vessel_draft_m": VESSEL_DRAFT_M,
            "safety_margin_m": SAFETY_MARGIN_M,
            "wildungsmauer_high_water_threshold_cm": WILDUNGSMAUER_HIGH_WATER_CM,
        }
    )
    return jsonify(payload)


if __name__ == "__main__":
    app.run(debug=True)
