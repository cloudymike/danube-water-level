"""Fetch and normalize official German Danube gauge data from PEGELONLINE."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

PEGELONLINE_URL = (
    "https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json"
    "?waters=DONAU&includeTimeseries=true&includeCurrentMeasurement=true"
    "&includeCharacteristicValues=true"
)
REQUEST_TIMEOUT = 10
TARGET_GAUGES = {
    "PASSAU DONAU",
    "HOFKIRCHEN",
    "VILSHOFEN",
    "PFELLING",
    "PFATTER",
    "SCHWABELWEIS",
    "OBERNDORF",
    "REGENSBURG EISERNE BRÜCKE",
}


@dataclass
class GermanyData:
    gauges: list[dict[str, Any]]
    source_url: str = PEGELONLINE_URL
    fetched_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gauges": self.gauges,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at,
            "error": self.error,
        }


def _characteristic_value(timeseries: dict[str, Any], shortname: str) -> float | None:
    for item in timeseries.get("characteristicValues", []) or []:
        if str(item.get("shortname", "")).upper() == shortname.upper():
            try:
                return float(item.get("value"))
            except (TypeError, ValueError):
                return None
    return None


def _water_timeseries(station: dict[str, Any]) -> dict[str, Any] | None:
    for ts in station.get("timeseries", []) or []:
        if str(ts.get("shortname", "")).upper() == "W":
            return ts
    return None


def fetch_germany_data() -> GermanyData:
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        response = requests.get(
            PEGELONLINE_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "danube-water-level/0.1"},
        )
        response.raise_for_status()
        stations = response.json()
        gauges = []

        for station in stations:
            name = station.get("shortname") or station.get("longname") or ""
            if name.upper() not in TARGET_GAUGES:
                continue
            ts = _water_timeseries(station)
            if not ts:
                continue
            measurement = ts.get("currentMeasurement") or {}
            gauges.append(
                {
                    "name": name,
                    "uuid": station.get("uuid"),
                    "river_km": station.get("km"),
                    "level_cm": measurement.get("value"),
                    "timestamp": measurement.get("timestamp"),
                    "shipping_state": measurement.get("stateNswHsw"),
                    "mnw_mhw_state": measurement.get("stateMnwMhw"),
                    "hsw_cm": _characteristic_value(ts, "HSW"),
                    "rnw_cm": _characteristic_value(ts, "RNW"),
                }
            )

        if not gauges:
            raise ValueError("PEGELONLINE returned no expected German Danube gauges")
        return GermanyData(gauges=gauges, fetched_at=fetched_at)
    except (requests.RequestException, ValueError, TypeError) as exc:
        return GermanyData(gauges=[], fetched_at=fetched_at, error=str(exc))
