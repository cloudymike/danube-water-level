from flask import Flask, jsonify, render_template

from services.austria import fetch_austria_data
from services.germany import fetch_germany_data

app = Flask(__name__)

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

WILDUNGSMAUER_HIGH_WATER_CM = 600
PASSAU_HIGH_WATER_CM = 780
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
        closure for closure in austria_data.closures
        if _range_overlaps(km_min, km_max, closure.get("river_km_from"), closure.get("river_km_to"))
        and not closure.get("is_open", False)
    ]


def _austrian_segment_statuses(austria_data):
    results = {}
    if austria_data.error:
        for from_stop, config in AUSTRIAN_SEGMENT_RANGES.items():
            results[from_stop] = {
                "from": from_stop, "to": config["to"], "status": "unknown",
                "minimum_depth_m": None, "shallow_sections": [], "closures": [], "locks": [],
                "reasons": ["DoRIS data unavailable"],
            }
        return results

    wildungsmauer = _gauge_level(austria_data, "Wildungsmauer")
    for from_stop, config in AUSTRIAN_SEGMENT_RANGES.items():
        km_min, km_max = config["river_km_min"], config["river_km_max"]
        relevant_sections = [
            section for section in austria_data.shallow_sections
            if _section_midpoint_km(section) is not None
            and km_min <= _section_midpoint_km(section) <= km_max
        ]
        depths = [s.get("deep_channel_depth_m") for s in relevant_sections if s.get("deep_channel_depth_m") is not None]
        minimum_depth = min(depths) if depths else None
        depth_status = _status_for_depth(minimum_depth)
        closures = _closures_for_segment(austria_data, km_min, km_max)
        locks = _locks_for_segment(austria_data, km_min, km_max)
        status = depth_status
        reasons = ["Low-water depth from mapped DoRIS shallow sections" if relevant_sections else "No current DoRIS shallow section mapped to this route segment"]

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
        if from_stop == "Bratislava" and wildungsmauer is not None and wildungsmauer >= WILDUNGSMAUER_HIGH_WATER_CM:
            status = "red"
            high_water = True
            reasons.append(f"Wildungsmauer {wildungsmauer:.0f} cm is at/above the 600 cm high-water threshold")

        results[from_stop] = {
            "from": from_stop, "to": config["to"], "river_km_min": km_min, "river_km_max": km_max,
            "status": status, "depth_status": depth_status, "minimum_depth_m": minimum_depth,
            "shallow_sections": relevant_sections, "closures": closures, "locks": locks,
            "high_water_override": high_water,
            "wildungsmauer_level_cm": wildungsmauer if from_stop == "Bratislava" else None,
            "reasons": reasons,
        }
    return results


def _austria_navigation_status(austria_data):
    segment_statuses = _austrian_segment_statuses(austria_data)
    worst = max(segment_statuses.values(), key=lambda item: STATUS_RANK[item["status"]])
    depths = [item["minimum_depth_m"] for item in segment_statuses.values() if item["minimum_depth_m"] is not None]
    return worst["status"], min(depths) if depths else None


def _german_gauge(germany_data, name):
    for gauge in germany_data.gauges:
        if gauge.get("name", "").upper() == name.upper():
            return gauge
    return None


def _gauge_status(gauge):
    if not gauge or gauge.get("level_cm") is None:
        return "unknown", "Gauge data unavailable"
    level = float(gauge["level_cm"])
    hsw = gauge.get("hsw_cm")
    rnw = gauge.get("rnw_cm")
    shipping_state = str(gauge.get("shipping_state") or "").lower()
    if shipping_state == "high" or (hsw is not None and level >= hsw):
        return "red", f"{gauge['name']} at/above HSW ({level:.0f} cm)"
    if rnw is not None and level < rnw:
        return "yellow", f"{gauge['name']} below RNW ({level:.0f} cm < {rnw:.0f} cm)"
    return "green", f"{gauge['name']} within published RNW/HSW water-level range"


def _german_segment_statuses(germany_data):
    if germany_data.error:
        return {
            "Passau": {"from": "Passau", "to": "Vilshofen", "status": "unknown", "gauges": [], "reasons": ["PEGELONLINE data unavailable"]},
            "Vilshofen": {"from": "Vilshofen", "to": "Regensburg", "status": "unknown", "gauges": [], "reasons": ["PEGELONLINE data unavailable"]},
        }

    passau = _german_gauge(germany_data, "PASSAU DONAU")
    hofkirchen = _german_gauge(germany_data, "HOFKIRCHEN")
    pfelling = _german_gauge(germany_data, "PFELLING")
    regensburg = _german_gauge(germany_data, "REGENSBURG EISERNE BRÜCKE")

    p_status, p_reason = _gauge_status(hofkirchen or passau)
    v_status, v_reason = _gauge_status(pfelling or regensburg)

    # The Passau-Danube 780 cm HSW also governs the German/Austrian border section.
    if passau and passau.get("level_cm") is not None and float(passau["level_cm"]) >= PASSAU_HIGH_WATER_CM:
        p_status = "red"
        p_reason = f"Passau Donau {float(passau['level_cm']):.0f} cm is at/above the 780 cm shipping high-water limit"

    return {
        "Passau": {
            "from": "Passau", "to": "Vilshofen", "status": p_status,
            "gauges": [g for g in (passau, hofkirchen) if g],
            "reasons": [p_reason, "Low-water yellow indicates RNW caution, not a vessel-specific draft limit"],
        },
        "Vilshofen": {
            "from": "Vilshofen", "to": "Regensburg", "status": v_status,
            "gauges": [g for g in (pfelling, regensburg) if g],
            "reasons": [v_reason, "Low-water yellow indicates RNW caution, not a vessel-specific draft limit"],
        },
    }


def _germany_navigation_status(germany_data):
    segments = _german_segment_statuses(germany_data)
    return max(segments.values(), key=lambda item: STATUS_RANK[item["status"]])["status"]


def _combined_route(austria_data, germany_data):
    route = [stop.copy() for stop in ROUTE]
    austria_segments = _austrian_segment_statuses(austria_data)
    germany_segments = _german_segment_statuses(germany_data)

    for stop in route:
        segment = austria_segments.get(stop["name"])
        if segment:
            stop["status"] = segment["status"]
            stop["status_source"] = "DoRIS depth + closures + lock states + high-water rules"
            stop["minimum_depth_m"] = segment["minimum_depth_m"]
            stop["segment_to"] = segment["to"]
            stop["segment_reasons"] = segment["reasons"]
            stop["shallow_section_names"] = [s["name"] for s in segment["shallow_sections"]]
            stop["closure_names"] = [c["name"] for c in segment["closures"]]
            stop["lock_states"] = [f"{lock['name']}: left {lock['left_chamber']}, right {lock['right_chamber']}" for lock in segment["locks"]]

        segment = germany_segments.get(stop["name"])
        if segment:
            stop["status"] = segment["status"]
            stop["status_source"] = "PEGELONLINE / ELWIS shipping-relevant gauges"
            stop["segment_to"] = segment["to"]
            stop["segment_reasons"] = segment["reasons"]
            stop["gauge_states"] = [
                f"{g['name']}: {g.get('level_cm')} cm"
                + (f", RNW {g['rnw_cm']:.0f}" if g.get('rnw_cm') is not None else "")
                + (f", HSW {g['hsw_cm']:.0f}" if g.get('hsw_cm') is not None else "")
                for g in segment["gauges"]
            ]

    # Apply the Passau 780 cm limit to Linz->Passau as well, because it covers the border section.
    passau = _german_gauge(germany_data, "PASSAU DONAU")
    if passau and passau.get("level_cm") is not None and float(passau["level_cm"]) >= PASSAU_HIGH_WATER_CM:
        linz = next((s for s in route if s["name"] == "Linz"), None)
        if linz:
            linz["status"] = "red"
            linz.setdefault("segment_reasons", []).append(
                f"Passau Donau {float(passau['level_cm']):.0f} cm is at/above the 780 cm border-section high-water limit"
            )
    return route


@app.route("/")
def index():
    austria = fetch_austria_data()
    germany = fetch_germany_data()
    route = _combined_route(austria, germany)
    austria_segments = _austrian_segment_statuses(austria)
    germany_segments = _german_segment_statuses(germany)
    austria_status, minimum_depth = _austria_navigation_status(austria)
    return render_template(
        "index.html",
        route=route,
        austria=austria.to_dict(),
        austria_segments=list(austria_segments.values()),
        austria_status=austria_status,
        austria_minimum_depth=minimum_depth,
        germany=germany.to_dict(),
        germany_segments=list(germany_segments.values()),
        germany_status=_germany_navigation_status(germany),
        vessel_draft_m=VESSEL_DRAFT_M,
        safety_margin_m=SAFETY_MARGIN_M,
        high_water_threshold_cm=WILDUNGSMAUER_HIGH_WATER_CM,
        passau_high_water_cm=PASSAU_HIGH_WATER_CM,
    )


@app.route("/api/austria")
def api_austria():
    austria = fetch_austria_data()
    segment_statuses = _austrian_segment_statuses(austria)
    status, minimum_depth = _austria_navigation_status(austria)
    payload = austria.to_dict()
    payload.update({
        "navigation_status": status,
        "minimum_deep_channel_depth_m": minimum_depth,
        "segment_statuses": list(segment_statuses.values()),
        "assumed_vessel_draft_m": VESSEL_DRAFT_M,
        "safety_margin_m": SAFETY_MARGIN_M,
        "wildungsmauer_high_water_threshold_cm": WILDUNGSMAUER_HIGH_WATER_CM,
    })
    return jsonify(payload)


@app.route("/api/germany")
def api_germany():
    germany = fetch_germany_data()
    payload = germany.to_dict()
    payload.update({
        "navigation_status": _germany_navigation_status(germany),
        "segment_statuses": list(_german_segment_statuses(germany).values()),
        "passau_high_water_threshold_cm": PASSAU_HIGH_WATER_CM,
    })
    return jsonify(payload)


if __name__ == "__main__":
    app.run(debug=True)
