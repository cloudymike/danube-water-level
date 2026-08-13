"""Combine country data into route-level navigation statuses."""

VESSEL_DRAFT_M = 1.50
SAFETY_MARGIN_M = 0.30
WILDUNGSMAUER_HIGH_WATER_CM = 600
PASSAU_HIGH_WATER_CM = 780
PFELLING_RNW_CM = 290
STRAUBING_SAND_FAIRWAY_DEPTH_AT_RNW_M = 2.65
STRAUBING_SAND_KM_FROM = 2322.0
STRAUBING_SAND_KM_TO = 2311.5
SAND_VILSHOFEN_FAIRWAY_DEPTH_AT_RNW_M = 2.00
VILSHOFEN_PASSAU_FAIRWAY_DEPTH_AT_RNW_M = 2.70
STRAUBING_REGENSBURG_FAIRWAY_DEPTH_AT_RNW_M = 2.90
PASSAU_REFERENCE_RNW_CM = 415
HOFKIRCHEN_RNW_CM = 207
SCHWABELWEIS_RNW_CM = 292
PFATTER_RNW_CM = 310
OBERNDORF_RNW_CM = 170
STATUS_RANK = {"unknown": 0, "green": 1, "yellow": 2, "red": 3}

ROUTE = [
    {"name": "Budapest", "lat": 47.4979, "lon": 19.0402, "status": "unknown"},
    {"name": "Esztergom", "lat": 47.7856, "lon": 18.7403, "status": "unknown"},
    {"name": "Komárno", "lat": 47.7636, "lon": 18.1298, "status": "unknown"},
    {"name": "Bratislava", "lat": 48.1486, "lon": 17.1077, "status": "unknown"},
    {"name": "Vienna", "lat": 48.2082, "lon": 16.3738, "status": "unknown"},
    {"name": "Wachau", "lat": 48.3892, "lon": 15.4690, "status": "unknown"},
    {"name": "Linz", "lat": 48.3069, "lon": 14.2858, "status": "unknown"},
    {"name": "Passau", "lat": 48.5667, "lon": 13.4319, "status": "unknown"},
    {"name": "Vilshofen", "lat": 48.6268, "lon": 13.1877, "status": "unknown"},
    {"name": "Straubing", "lat": 48.8810, "lon": 12.5730, "status": "unknown"},
    {"name": "Regensburg", "lat": 49.0134, "lon": 12.1016, "status": "unknown"},
]

AUSTRIAN_SEGMENT_RANGES = {
    "Bratislava": {"to": "Vienna", "river_km_min": 1872.7, "river_km_max": 1921.0},
    "Vienna": {"to": "Wachau", "river_km_min": 1921.0, "river_km_max": 2010.0},
    "Wachau": {"to": "Linz", "river_km_min": 2010.0, "river_km_max": 2135.5},
    "Linz": {"to": "Passau", "river_km_min": 2135.5, "river_km_max": 2223.2},
}

LOCK_RIVER_KM = {
    "Aschach": 2162.0, "Ottensheim": 2147.0, "Abwinden": 2119.0,
    "Wallsee": 2095.0, "Ybbs": 2060.0, "Melk": 2038.0,
    "Altenwörth": 1980.0, "Greifenstein": 1949.0, "Freudenau": 1921.0,
}


def _status_for_depth(depth):
    if depth is None:
        return "green"
    if depth < VESSEL_DRAFT_M:
        return "red"
    if depth < VESSEL_DRAFT_M + SAFETY_MARGIN_M:
        return "yellow"
    return "green"


def _midpoint(section):
    a, b = section.get("river_km_from"), section.get("river_km_to")
    return None if a is None or b is None else (a + b) / 2


def _overlaps(a_min, a_max, b_from, b_to):
    if b_from is None or b_to is None:
        return False
    b_min, b_max = sorted((b_from, b_to))
    return max(a_min, b_min) <= min(a_max, b_max)


def _find_gauge(data, name):
    for gauge in getattr(data, "gauges", []):
        if gauge.get("name", "").casefold() == name.casefold():
            return gauge
    return None


def austrian_segments(data):
    results = {}
    if data.error:
        return {k: {"from": k, "to": v["to"], "status": "unknown", "minimum_depth_m": None,
                    "shallow_sections": [], "closures": [], "locks": [], "reasons": ["DoRIS data unavailable"]}
                for k, v in AUSTRIAN_SEGMENT_RANGES.items()}

    wild = _find_gauge(data, "Wildungsmauer")
    wild_level = wild.get("level_cm") if wild else None
    for start, cfg in AUSTRIAN_SEGMENT_RANGES.items():
        lo, hi = cfg["river_km_min"], cfg["river_km_max"]
        shallow = [s for s in data.shallow_sections if _midpoint(s) is not None and lo <= _midpoint(s) <= hi]
        depths = [s["deep_channel_depth_m"] for s in shallow if s.get("deep_channel_depth_m") is not None]
        min_depth = min(depths) if depths else None
        status = _status_for_depth(min_depth)
        closures = [c for c in data.closures if _overlaps(lo, hi, c.get("river_km_from"), c.get("river_km_to")) and not c.get("is_open", False)]
        locks = []
        for lock in data.locks:
            km = LOCK_RIVER_KM.get(lock.get("name"))
            if km is not None and lo <= km <= hi:
                item = lock.copy(); item["river_km"] = km; locks.append(item)
        reasons = ["Low-water depth from mapped DoRIS shallow sections" if shallow else "No current DoRIS shallow section mapped to this route segment"]
        if closures:
            status = "red"; reasons.append("Official DoRIS navigation closure affects this segment")
        if any(x.get("both_closed") for x in locks):
            status = "red"; reasons.append("Both chambers unavailable at a lock in this segment")
        elif any(x.get("one_closed") for x in locks) and STATUS_RANK[status] < STATUS_RANK["yellow"]:
            status = "yellow"; reasons.append("One lock chamber unavailable in this segment")
        if start == "Bratislava" and wild_level is not None and wild_level >= WILDUNGSMAUER_HIGH_WATER_CM:
            status = "red"; reasons.append(f"Wildungsmauer {wild_level:.0f} cm is at/above the 600 cm high-water threshold")
        results[start] = {"from": start, "to": cfg["to"], "status": status, "minimum_depth_m": min_depth,
                          "shallow_sections": shallow, "closures": closures, "locks": locks, "reasons": reasons}
    return results


def austria_overall(data):
    segs = austrian_segments(data)
    worst = max(segs.values(), key=lambda x: STATUS_RANK[x["status"]])["status"]
    depths = [x["minimum_depth_m"] for x in segs.values() if x["minimum_depth_m"] is not None]
    return worst, min(depths) if depths else None


def _german_gauge_status(gauge):
    if not gauge or gauge.get("level_cm") is None:
        return "unknown", "Gauge data unavailable"
    level = float(gauge["level_cm"]); hsw = gauge.get("hsw_cm"); rnw = gauge.get("rnw_cm")
    if str(gauge.get("shipping_state") or "").lower() == "high" or (hsw is not None and level >= hsw):
        return "red", f"{gauge['name']} at/above HSW ({level:.0f} cm)"
    if rnw is not None and level < rnw:
        return "yellow", f"{gauge['name']} below RNW ({level:.0f} cm < {rnw:.0f} cm)"
    return "green", f"{gauge['name']} within published RNW/HSW water-level range"


def _all_at_or_above_rnw(gauges):
    return all(
        gauge is not None
        and gauge.get("level_cm") is not None
        and gauge.get("rnw_cm") is not None
        and float(gauge["level_cm"]) >= float(gauge["rnw_cm"])
        for gauge in gauges
    )


def _any_high_water(gauges):
    for gauge in gauges:
        if not gauge or gauge.get("level_cm") is None:
            continue
        level = float(gauge["level_cm"])
        hsw = gauge.get("hsw_cm")
        if str(gauge.get("shipping_state") or "").lower() == "high" or (hsw is not None and level >= float(hsw)):
            return gauge
    return None


def german_segments(data):
    if data.error:
        return {k: {"from": k, "to": to, "status": "unknown", "gauges": [], "reasons": ["PEGELONLINE data unavailable"]}
                for k, to in (("Passau", "Vilshofen"), ("Vilshofen", "Straubing"), ("Straubing", "Regensburg"))}

    passau = _find_gauge(data, "PASSAU DONAU")
    hof = _find_gauge(data, "HOFKIRCHEN")
    pf = _find_gauge(data, "PFELLING")
    pfatter = _find_gauge(data, "PFATTER")
    schwabelweis = _find_gauge(data, "SCHWABELWEIS")
    oberndorf = _find_gauge(data, "OBERNDORF")

    # Passau -> Vilshofen: WSV publishes 2.70 m at RNW for both subreaches.
    passau_gauges = [g for g in (passau, hof) if g]
    high = _any_high_water(passau_gauges)
    if high:
        passau_status = "red"
        passau_reasons = [f"{high['name']} is at/above its published HSW"]
    elif passau and hof and passau.get("level_cm") is not None and hof.get("level_cm") is not None:
        passau_ok = float(passau["level_cm"]) >= PASSAU_REFERENCE_RNW_CM
        hof_ok = float(hof["level_cm"]) >= HOFKIRCHEN_RNW_CM
        if passau_ok and hof_ok:
            passau_status = _status_for_depth(VILSHOFEN_PASSAU_FAIRWAY_DEPTH_AT_RNW_M)
            passau_reasons = [
                f"Official WSV fairway depth is {VILSHOFEN_PASSAU_FAIRWAY_DEPTH_AT_RNW_M:.2f} m at RNW for Vilshofen→Passau",
                f"Passau Donau is at/above the 415 cm reference level and Hofkirchen is at/above RNW 207 cm",
            ]
        else:
            passau_status = "yellow"
            passau_reasons = ["One or more WSV reference gauges are below the RNW level used for the published 2.70 m fairway depth; no below-RNW depth is extrapolated"]
    else:
        passau_status = "unknown"
        passau_reasons = ["Required Passau/Hofkirchen reference-gauge data unavailable"]

    # Vilshofen -> Straubing: the controlling published depth is 2.00 m from Sand to Vilshofen.
    critical_gauges = [g for g in (hof, pf) if g]
    high = _any_high_water(critical_gauges)
    if high:
        critical_status = "red"
        critical_reasons = [f"{high['name']} is at/above its published HSW"]
    elif pf and hof and pf.get("level_cm") is not None and hof.get("level_cm") is not None:
        pf_ok = float(pf["level_cm"]) >= PFELLING_RNW_CM
        hof_ok = float(hof["level_cm"]) >= HOFKIRCHEN_RNW_CM
        if pf_ok and hof_ok:
            critical_status = _status_for_depth(SAND_VILSHOFEN_FAIRWAY_DEPTH_AT_RNW_M)
            critical_reasons = [
                f"Official WSV fairway depth is {SAND_VILSHOFEN_FAIRWAY_DEPTH_AT_RNW_M:.2f} m for Sand→Vilshofen at Pfelling RNW 290 cm / Hofkirchen RNW 207 cm",
                f"Straubing→Sand has the larger official depth of {STRAUBING_SAND_FAIRWAY_DEPTH_AT_RNW_M:.2f} m at Pfelling RNW",
                f"The controlling 2.00 m depth exceeds the configured {VESSEL_DRAFT_M + SAFETY_MARGIN_M:.2f} m draft-plus-margin requirement",
            ]
        else:
            critical_status = "yellow"
            critical_reasons = ["Pfelling and/or Hofkirchen are below the RNW reference conditions; WSV does not provide a simple below-RNW gauge-to-depth conversion, so passage remains undetermined"]
    else:
        critical_status = "unknown"
        critical_reasons = ["Required Pfelling/Hofkirchen reference-gauge data unavailable"]

    # Straubing -> Regensburg: WSV publishes 2.90 m at the applicable RNW gauges.
    upstream_gauges = [g for g in (oberndorf, schwabelweis, pfatter) if g]
    high = _any_high_water(upstream_gauges)
    if high:
        upstream_status = "red"
        upstream_reasons = [f"{high['name']} is at/above its published HSW"]
    elif len(upstream_gauges) == 3 and _all_at_or_above_rnw(upstream_gauges):
        upstream_status = _status_for_depth(STRAUBING_REGENSBURG_FAIRWAY_DEPTH_AT_RNW_M)
        upstream_reasons = [
            f"Official WSV fairway depth is {STRAUBING_REGENSBURG_FAIRWAY_DEPTH_AT_RNW_M:.2f} m from the Main-Danube Canal mouth to Straubing at the applicable RNW gauges",
            "Oberndorf, Schwabelweis, and Pfatter are all at/above their RNW reference levels",
        ]
    elif len(upstream_gauges) == 3:
        upstream_status = "yellow"
        upstream_reasons = ["At least one applicable RNW reference gauge is below RNW; no below-RNW fairway depth is extrapolated"]
    else:
        upstream_status = "unknown"
        upstream_reasons = ["Required Oberndorf/Schwabelweis/Pfatter reference-gauge data unavailable"]

    return {
        "Passau": {
            "from": "Passau", "to": "Vilshofen", "status": passau_status,
            "gauges": passau_gauges, "reasons": passau_reasons,
            "official_fairway_depth_m": VILSHOFEN_PASSAU_FAIRWAY_DEPTH_AT_RNW_M,
            "official_depth_scope": "Vilshofen→Passau at WSV RNW reference conditions",
        },
        "Vilshofen": {
            "from": "Vilshofen", "to": "Straubing", "status": critical_status,
            "gauges": critical_gauges, "reasons": critical_reasons,
            "official_fairway_depth_m": SAND_VILSHOFEN_FAIRWAY_DEPTH_AT_RNW_M,
            "official_depth_scope": "controlling Sand→Vilshofen subreach at RNW",
        },
        "Straubing": {
            "from": "Straubing", "to": "Regensburg", "status": upstream_status,
            "gauges": upstream_gauges, "reasons": upstream_reasons,
            "official_fairway_depth_m": STRAUBING_REGENSBURG_FAIRWAY_DEPTH_AT_RNW_M,
            "official_depth_scope": "main waterway Regensburg/Straubing reach at applicable RNW gauges",
        },
    }


def germany_overall(data):
    return max(german_segments(data).values(), key=lambda x: STATUS_RANK[x["status"]])["status"]


def eastern_segments(hungary, slovakia):
    """Return conservative Hungary/Slovakia route statuses.

    National hydrology feeds establish current levels and flood thresholds, but the
    sources currently used do not establish vessel-specific fairway depth. Therefore
    normal conditions remain yellow; an official flood threshold can make a segment red.
    """
    hu_bud = _find_gauge(hungary, "Budapest"); hu_esz = _find_gauge(hungary, "Esztergom")
    sk_kom = _find_gauge(slovakia, "Komárno"); sk_bra = _find_gauge(slovakia, "Bratislava")

    def sk_flood_red(gauge):
        if not gauge or gauge.get("level_cm") is None:
            return False
        threshold = gauge.get("flood_stage_1_cm")
        return threshold is not None and float(gauge["level_cm"]) >= float(threshold)

    result = {
        "Budapest": {"from": "Budapest", "to": "Esztergom", "status": "yellow", "gauges": [g for g in (hu_bud, hu_esz) if g],
                     "reasons": ["Official Hungarian Hydroinfo water levels available", "No vessel-specific fairway-depth guarantee is derived from gauge height alone"]},
        "Esztergom": {"from": "Esztergom", "to": "Komárno", "status": "yellow", "gauges": [g for g in (hu_esz, sk_kom) if g],
                      "reasons": ["Shared Hungary/Slovakia Danube reach", "Official gauge levels available, but whole-reach vessel clearance is not proven"]},
        "Komárno": {"from": "Komárno", "to": "Bratislava", "status": "yellow", "gauges": [g for g in (sk_kom, sk_bra) if g],
                    "reasons": ["Official SHMÚ water levels available", "Gauge height alone does not prove cruise-vessel fairway depth"]},
    }
    if hungary.error:
        result["Budapest"]["reasons"].append("Hungarian Hydroinfo feed unavailable")
        result["Esztergom"]["reasons"].append("Hungarian Hydroinfo feed unavailable")
    if slovakia.error:
        result["Esztergom"]["reasons"].append("Slovak SHMÚ feed unavailable")
        result["Komárno"]["reasons"].append("Slovak SHMÚ feed unavailable")
    if sk_flood_red(sk_kom):
        result["Esztergom"]["status"] = "red"; result["Komárno"]["status"] = "red"
        result["Esztergom"]["reasons"].append("Komárno is at/above SHMÚ first flood-activity threshold")
        result["Komárno"]["reasons"].append("Komárno is at/above SHMÚ first flood-activity threshold")
    if sk_flood_red(sk_bra):
        result["Komárno"]["status"] = "red"; result["Komárno"]["reasons"].append("Bratislava is at/above SHMÚ first flood-activity threshold")
    return result


def east_overall(hungary, slovakia):
    return max(eastern_segments(hungary, slovakia).values(), key=lambda x: STATUS_RANK[x["status"]])["status"]


def combined_route(austria, germany, hungary, slovakia):
    route = [x.copy() for x in ROUTE]
    all_segments = {}
    all_segments.update(eastern_segments(hungary, slovakia))
    all_segments.update(austrian_segments(austria))
    all_segments.update(german_segments(germany))
    for stop in route:
        seg = all_segments.get(stop["name"])
        if not seg:
            continue
        stop["status"] = seg["status"]; stop["segment_to"] = seg["to"]; stop["segment_reasons"] = seg["reasons"]
        if stop["name"] in {"Budapest", "Esztergom"}:
            stop["status_source"] = "Hungarian Hydroinfo + Slovak SHMÚ official hydrology"
        elif stop["name"] == "Komárno":
            stop["status_source"] = "Slovak SHMÚ official hydrology"
        elif stop["name"] in AUSTRIAN_SEGMENT_RANGES:
            stop["status_source"] = "DoRIS depth + closures + lock states + high-water rules"
            stop["minimum_depth_m"] = seg.get("minimum_depth_m")
            stop["shallow_section_names"] = [s["name"] for s in seg.get("shallow_sections", [])]
            stop["closure_names"] = [c["name"] for c in seg.get("closures", [])]
            stop["lock_states"] = [f"{x['name']}: left {x['left_chamber']}, right {x['right_chamber']}" for x in seg.get("locks", [])]
        else:
            stop["status_source"] = "PEGELONLINE / ELWIS shipping gauges + official WSV RNW fairway depths"
            stop["official_fairway_depth_m"] = seg.get("official_fairway_depth_m")
            stop["official_depth_scope"] = seg.get("official_depth_scope")
        gauges = seg.get("gauges", [])
        if gauges:
            stop["gauge_states"] = [f"{g['name']}: {g.get('level_cm')} cm" for g in gauges]

    passau = _find_gauge(germany, "PASSAU DONAU")
    if passau and passau.get("level_cm") is not None and float(passau["level_cm"]) >= PASSAU_HIGH_WATER_CM:
        linz = next((x for x in route if x["name"] == "Linz"), None)
        if linz:
            linz["status"] = "red"; linz.setdefault("segment_reasons", []).append("Passau 780 cm border-section high-water limit reached")
    return route
