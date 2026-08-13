from flask import Flask, jsonify, render_template

from services.austria import fetch_austria_data
from services.germany import fetch_germany_data
from services.hungary import fetch_hungary_data
from services.slovakia import fetch_slovakia_data
from services.operational import apply_operational_evidence, current_operational_evidence
from services.navigation import (
    PASSAU_HIGH_WATER_CM,
    PFELLING_RNW_CM,
    SAFETY_MARGIN_M,
    SAND_VILSHOFEN_FAIRWAY_DEPTH_AT_RNW_M,
    STRAUBING_REGENSBURG_FAIRWAY_DEPTH_AT_RNW_M,
    STRAUBING_SAND_FAIRWAY_DEPTH_AT_RNW_M,
    VESSEL_DRAFT_M,
    VILSHOFEN_PASSAU_FAIRWAY_DEPTH_AT_RNW_M,
    WILDUNGSMAUER_HIGH_WATER_CM,
    austria_overall,
    austrian_segments,
    combined_route,
    east_overall,
    eastern_segments,
    german_segments,
    germany_overall,
)

app = Flask(__name__)


@app.route("/")
def index():
    austria = fetch_austria_data()
    germany = fetch_germany_data()
    hungary = fetch_hungary_data()
    slovakia = fetch_slovakia_data()

    operational = current_operational_evidence()
    route = apply_operational_evidence(combined_route(austria, germany, hungary, slovakia), operational)
    austria_status, minimum_depth = austria_overall(austria)
    east_segments = eastern_segments(hungary, slovakia)

    return render_template(
        "index.html",
        route=route,
        operational_evidence=list(operational.values()),
        austria=austria.to_dict(),
        austria_segments=list(austrian_segments(austria).values()),
        austria_status=austria_status,
        austria_minimum_depth=minimum_depth,
        germany=germany.to_dict(),
        germany_segments=list(german_segments(germany).values()),
        germany_status=germany_overall(germany),
        hungary=hungary.to_dict(),
        slovakia=slovakia.to_dict(),
        eastern_segments=list(east_segments.values()),
        east_status=east_overall(hungary, slovakia),
        vessel_draft_m=VESSEL_DRAFT_M,
        safety_margin_m=SAFETY_MARGIN_M,
        high_water_threshold_cm=WILDUNGSMAUER_HIGH_WATER_CM,
        passau_high_water_cm=PASSAU_HIGH_WATER_CM,
        pfelling_rnw_cm=PFELLING_RNW_CM,
        straubing_sand_depth_m=STRAUBING_SAND_FAIRWAY_DEPTH_AT_RNW_M,
    )


@app.route("/api/austria")
def api_austria():
    data = fetch_austria_data()
    status, minimum_depth = austria_overall(data)
    payload = data.to_dict()
    payload.update({
        "navigation_status": status,
        "minimum_deep_channel_depth_m": minimum_depth,
        "segment_statuses": list(austrian_segments(data).values()),
        "assumed_vessel_draft_m": VESSEL_DRAFT_M,
        "safety_margin_m": SAFETY_MARGIN_M,
    })
    return jsonify(payload)


@app.route("/api/germany")
def api_germany():
    data = fetch_germany_data()
    payload = data.to_dict()
    payload.update({
        "navigation_status": germany_overall(data),
        "segment_statuses": list(german_segments(data).values()),
        "passau_high_water_threshold_cm": PASSAU_HIGH_WATER_CM,
        "pfelling_rnw_cm": PFELLING_RNW_CM,
        "official_fairway_depths_at_rnw_m": {
            "Passau-Vilshofen": VILSHOFEN_PASSAU_FAIRWAY_DEPTH_AT_RNW_M,
            "Vilshofen-Straubing_controlling": SAND_VILSHOFEN_FAIRWAY_DEPTH_AT_RNW_M,
            "Straubing-Sand": STRAUBING_SAND_FAIRWAY_DEPTH_AT_RNW_M,
            "Straubing-Regensburg": STRAUBING_REGENSBURG_FAIRWAY_DEPTH_AT_RNW_M,
        },
        "assumed_vessel_draft_m": VESSEL_DRAFT_M,
        "safety_margin_m": SAFETY_MARGIN_M,
    })
    return jsonify(payload)


@app.route("/api/hungary")
def api_hungary():
    hungary = fetch_hungary_data()
    slovakia = fetch_slovakia_data()
    payload = hungary.to_dict()
    payload.update({
        "navigation_status": east_overall(hungary, slovakia),
        "segment_statuses": list(eastern_segments(hungary, slovakia).values()),
    })
    return jsonify(payload)


@app.route("/api/slovakia")
def api_slovakia():
    hungary = fetch_hungary_data()
    slovakia = fetch_slovakia_data()
    payload = slovakia.to_dict()
    payload.update({
        "navigation_status": east_overall(hungary, slovakia),
        "segment_statuses": list(eastern_segments(hungary, slovakia).values()),
    })
    return jsonify(payload)


@app.route("/api/operations")
def api_operations():
    return jsonify({"operational_evidence": list(current_operational_evidence().values())})


if __name__ == "__main__":
    app.run(debug=True)
