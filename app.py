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

# Route segments are keyed by the stop at the downstream/eastern end because
# map.js colors a GeoJSON feature using its `from` stop. Danube river-km values
# increase upstream. The boundaries below separate the portions of our displayed
# route that are relevant to Austrian DoRIS shallow-section information.
#
# DoRIS identifies the two free-flowing low-water areas as:
#   east of Vienna: km 1872.7-1921.0
#   Wachau:         km 1998.0-2038.0
#
# The 2010.0 split corresponds approximately to our Wachau/Dürnstein waypoint,
# allowing shallow sections on either side to affect different map segments.
AUSTRIAN_SEGMENT_RANGES = {
    "Bratislava": {
        "to": "Vienna",
        "river_km_min": 1872.7,
        "river_km_max": 1921.0,
    },
    "Vienna": {
        "to": "Wachau",
        "river_km_min": 1921.0,
        "river_km_max": 2010.0,
    },
    "Wachau": {
        "to": "Linz",
        "river_km_min": 2010.0,
        "river_km_max": 2135.5,
    },
    "Linz": {
        "to": "Passau",
        "river_km_min": 2135.5,
        "river_km_max": 2223.2,
    },
}


def _status_for_depth(minimum_depth):
    """Convert a deep-channel depth into the prototype navigation status."""
    if minimum_depth is None:
        return "green"
    if minimum_depth < VESSEL_DRAFT_M:
        return "red"
    if minimum_depth < VESSEL_DRAFT_M + SAFETY_MARGIN_M:
        return "yellow"
    return "green"


def _section_midpoint_km(section):
    """Return the river-km midpoint of a DoRIS shallow section."""
    start = section.get("river_km_from")
    end = section.get("river_km_to")
    if start is None or end is None:
        return None
    return (start + end) / 2


def _austrian_segment_statuses(austria_data):
    """Map current DoRIS shallow sections to the route segments they affect."""
    results = {}

    if austria_data.error:
        for from_stop, config in AUSTRIAN_SEGMENT_RANGES.items():
            results[from_stop] = {
                "from": from_stop,
                "to": config["to"],
                "status": "unknown",
                "minimum_depth_m": None,
                "shallow_sections": [],
                "reason": "DoRIS data unavailable",
            }
        return results

    for from_stop, config in AUSTRIAN_SEGMENT_RANGES.items():
        relevant_sections = []
        for section in austria_data.shallow_sections:
            midpoint = _section_midpoint_km(section)
            if midpoint is None:
                continue
            if config["river_km_min"] <= midpoint <= config["river_km_max"]:
                relevant_sections.append(section)

        depths = [
            section.get("deep_channel_depth_m")
            for section in relevant_sections
            if section.get("deep_channel_depth_m") is not None
        ]
        minimum_depth = min(depths) if depths else None
        status = _status_for_depth(minimum_depth)

        if relevant_sections:
            reason = "Minimum DoRIS deep-channel depth in this route segment"
        else:
            reason = "No current DoRIS shallow section mapped to this route segment"

        results[from_stop] = {
            "from": from_stop,
            "to": config["to"],
            "river_km_min": config["river_km_min"],
            "river_km_max": config["river_km_max"],
            "status": status,
            "minimum_depth_m": minimum_depth,
            "shallow_sections": relevant_sections,
            "reason": reason,
        }

    return results


def _austria_navigation_status(austria_data):
    """Return the worst current status across the Austrian displayed segments."""
    segment_statuses = _austrian_segment_statuses(austria_data)
    rank = {"unknown": 0, "green": 1, "yellow": 2, "red": 3}
    worst = max(segment_statuses.values(), key=lambda item: rank[item["status"]])

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
        stop["status_source"] = "DoRIS shallow-section depth by river-km"
        stop["minimum_depth_m"] = segment["minimum_depth_m"]
        stop["segment_to"] = segment["to"]
        stop["segment_reason"] = segment["reason"]
        stop["shallow_section_names"] = [
            section["name"] for section in segment["shallow_sections"]
        ]

    return route


@app.route("/")
def index():
    """Display the Danube cruise navigation status page."""
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
    )


@app.route("/api/austria")
def api_austria():
    """Return normalized current Austrian DoRIS data and route statuses as JSON."""
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
        }
    )
    return jsonify(payload)


if __name__ == "__main__":
    app.run(debug=True)
