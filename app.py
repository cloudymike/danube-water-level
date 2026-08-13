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

AUSTRIAN_SEGMENTS = {
    "Bratislava": "Austria",
    "Vienna": "Austria",
    "Wachau": "Austria",
    "Linz": "Austria",
}


def _austria_navigation_status(austria_data):
    """Derive an indicative Austrian status from current shallow-section depths."""
    if austria_data.error or not austria_data.shallow_sections:
        return "unknown", None

    depths = [
        section["deep_channel_depth_m"]
        for section in austria_data.shallow_sections
        if section.get("deep_channel_depth_m") is not None
    ]
    if not depths:
        return "unknown", None

    minimum_depth = min(depths)
    if minimum_depth < VESSEL_DRAFT_M:
        status = "red"
    elif minimum_depth < VESSEL_DRAFT_M + SAFETY_MARGIN_M:
        status = "yellow"
    else:
        status = "green"

    return status, minimum_depth


def _route_with_austria_status(austria_data):
    route = [stop.copy() for stop in ROUTE]
    status, minimum_depth = _austria_navigation_status(austria_data)

    for stop in route:
        if stop["name"] in AUSTRIAN_SEGMENTS:
            stop["status"] = status
            stop["status_source"] = "DoRIS shallow-section depth"
            stop["minimum_depth_m"] = minimum_depth

    return route


@app.route("/")
def index():
    """Display the Danube cruise navigation status page."""
    austria = fetch_austria_data()
    route = _route_with_austria_status(austria)
    status, minimum_depth = _austria_navigation_status(austria)
    return render_template(
        "index.html",
        route=route,
        austria=austria.to_dict(),
        austria_status=status,
        austria_minimum_depth=minimum_depth,
        vessel_draft_m=VESSEL_DRAFT_M,
        safety_margin_m=SAFETY_MARGIN_M,
    )


@app.route("/api/austria")
def api_austria():
    """Return normalized current Austrian DoRIS data as JSON."""
    austria = fetch_austria_data()
    status, minimum_depth = _austria_navigation_status(austria)
    payload = austria.to_dict()
    payload.update(
        {
            "navigation_status": status,
            "minimum_deep_channel_depth_m": minimum_depth,
            "assumed_vessel_draft_m": VESSEL_DRAFT_M,
            "safety_margin_m": SAFETY_MARGIN_M,
        }
    )
    return jsonify(payload)


if __name__ == "__main__":
    app.run(debug=True)
