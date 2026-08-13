"""Operational cruise evidence, kept separate from authoritative navigation status.

This layer is intentionally evidence-based rather than a navigation guarantee. Entries
should be time-bounded and sourced. Later, an AIS provider can replace or supplement
these curated observations without changing the map/status model.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class OperationalEvidence:
    from_stop: str
    to_stop: str
    signal: str  # observed_passable | observed_disruption
    observed_at: str
    expires_at: str
    summary: str
    source_name: str
    source_url: str
    confidence: str = "medium"

    def to_dict(self):
        return asdict(self)


# Current public reporting, 12 Aug 2026: AmaSofia departed Vilshofen toward Budapest
# but the vessel itself only reached Melk; passengers continued toward Budapest by land.
# This is strong evidence of operational disruption on the intended Melk->Budapest route,
# but it is not proof that every individual subsegment was physically impassable.
CURATED_EVIDENCE = [
    OperationalEvidence(
        from_stop="Budapest", to_stop="Esztergom", signal="observed_disruption",
        observed_at="2026-08-12T12:00:00Z", expires_at="2026-08-19T12:00:00Z",
        summary="Recent AmaSofia Vilshofen→Budapest itinerary ended at Melk; guests continued toward Budapest by land because of low-water disruption.",
        source_name="Town & Country, 12 Aug 2026",
        source_url="https://www.townandcountrymag.com/leisure/travel-guide/a73366575/europe-heat-wave-river-cruise-impact-2026/",
        confidence="medium",
    ),
    OperationalEvidence(
        from_stop="Esztergom", to_stop="Komárno", signal="observed_disruption",
        observed_at="2026-08-12T12:00:00Z", expires_at="2026-08-19T12:00:00Z",
        summary="Recent AmaSofia Vilshofen→Budapest itinerary ended at Melk; guests continued toward Budapest by land because of low-water disruption.",
        source_name="Town & Country, 12 Aug 2026",
        source_url="https://www.townandcountrymag.com/leisure/travel-guide/a73366575/europe-heat-wave-river-cruise-impact-2026/",
        confidence="medium",
    ),
    OperationalEvidence(
        from_stop="Komárno", to_stop="Bratislava", signal="observed_disruption",
        observed_at="2026-08-12T12:00:00Z", expires_at="2026-08-19T12:00:00Z",
        summary="Recent AmaSofia Vilshofen→Budapest itinerary ended at Melk; guests continued toward Budapest by land because of low-water disruption.",
        source_name="Town & Country, 12 Aug 2026",
        source_url="https://www.townandcountrymag.com/leisure/travel-guide/a73366575/europe-heat-wave-river-cruise-impact-2026/",
        confidence="medium",
    ),
]


def current_operational_evidence(now=None):
    now = now or datetime.now(timezone.utc)
    result = {}
    for item in CURATED_EVIDENCE:
        expiry = datetime.fromisoformat(item.expires_at.replace("Z", "+00:00"))
        if now <= expiry:
            result[item.from_stop] = item.to_dict()
    return result


def apply_operational_evidence(route, evidence=None):
    """Add a display status without overwriting the authoritative status.

    Red/green authoritative results stay red/green. Operational evidence only refines
    authoritative yellow/unknown: observed transit -> lime; disruption -> orange.
    """
    evidence = evidence if evidence is not None else current_operational_evidence()
    for stop in route:
        authoritative = stop.get("status", "unknown")
        stop["authoritative_status"] = authoritative
        stop["display_status"] = authoritative
        item = evidence.get(stop.get("name"))
        if not item:
            continue
        stop["operational_evidence"] = item
        if authoritative in {"yellow", "unknown"}:
            if item["signal"] == "observed_passable":
                stop["display_status"] = "lime"
            elif item["signal"] == "observed_disruption":
                stop["display_status"] = "orange"
    return route
