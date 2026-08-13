"""Refine German route statuses with current ELWIS fairway restrictions."""

from __future__ import annotations

from copy import deepcopy

from services.navigation import STATUS_RANK, german_segments as base_german_segments

# Display-route river-km ranges. German Danube kilometres increase upstream.
GERMAN_SEGMENT_RANGES = {
    "Passau": (2201.8, 2250.0),
    "Vilshofen": (2250.0, 2322.0),
    "Straubing": (2322.0, 2381.0),
}


def _overlaps(a_min, a_max, b_from, b_to):
    if b_from is None or b_to is None:
        return False
    b_min, b_max = sorted((float(b_from), float(b_to)))
    return max(a_min, b_min) <= min(a_max, b_max)


def restrictions_for_segment(restrictions_data, from_stop):
    km_range = GERMAN_SEGMENT_RANGES.get(from_stop)
    if not km_range or not restrictions_data or restrictions_data.error:
        return []
    lo, hi = km_range
    return [
        item for item in restrictions_data.restrictions
        if _overlaps(lo, hi, item.get("river_km_from"), item.get("river_km_to"))
    ]


def _restriction_status(items):
    """Return the authoritative impact of active ELWIS fairway restrictions.

    A full/explicit closure is red. Other active fairway restrictions downgrade a
    green result to yellow because the notice establishes that the published RNW
    reference geometry is temporarily constrained, but may not prove that our
    configured vessel cannot pass.
    """
    if not items:
        return None
    text = " ".join(str(item.get("restriction", "")) for item in items).casefold()
    if "sperre" in text or "gesperrt" in text:
        return "red"
    return "yellow"


def german_segments(data, restrictions_data=None):
    segments = deepcopy(base_german_segments(data))
    for from_stop, segment in segments.items():
        items = restrictions_for_segment(restrictions_data, from_stop)
        segment["fairway_restrictions"] = items
        if restrictions_data and restrictions_data.error:
            segment.setdefault("reasons", []).append(
                "ELWIS fairway-restriction feed unavailable; RNW/depth result is not independently checked for temporary restrictions"
            )
            # Do not claim authoritative green if the live restriction layer failed.
            if segment.get("status") == "green":
                segment["status"] = "yellow"
        impact = _restriction_status(items)
        if impact == "red":
            segment["status"] = "red"
            segment.setdefault("reasons", []).append("Active ELWIS fairway restriction/closure affects this river-km range")
        elif impact == "yellow" and STATUS_RANK.get(segment.get("status"), 0) < STATUS_RANK["yellow"]:
            segment["status"] = "yellow"
            segment.setdefault("reasons", []).append("Active ELWIS fairway restriction affects this river-km range")
    return segments


def germany_overall(data, restrictions_data=None):
    segments = german_segments(data, restrictions_data)
    return max(segments.values(), key=lambda item: STATUS_RANK[item["status"]])["status"]


def apply_german_restrictions_to_route(route, germany_data, restrictions_data):
    """Replace German route segment statuses/details with the refined results."""
    segments = german_segments(germany_data, restrictions_data)
    result = [stop.copy() for stop in route]
    for stop in result:
        segment = segments.get(stop.get("name"))
        if not segment:
            continue
        stop["status"] = segment["status"]
        stop["authoritative_status"] = segment["status"]
        stop["segment_reasons"] = segment.get("reasons", [])
        stop["fairway_restrictions"] = segment.get("fairway_restrictions", [])
        if stop.get("display_status") in (None, "green", "yellow", "red"):
            stop["display_status"] = segment["status"]
    return result
