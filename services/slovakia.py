"""Fetch current Slovak Danube water levels from official SHMÚ station pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import re

import requests
from bs4 import BeautifulSoup

REQUEST_TIMEOUT = 10
STATIONS = {
    "Bratislava": "https://www.shmu.sk/en/?page=765&station_id=5140",
    "Komárno": "https://www.shmu.sk/en/?page=765&station_id=6849",
}


@dataclass
class SlovakiaData:
    gauges: list[dict[str, Any]]
    fetched_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gauges": self.gauges,
            "fetched_at": self.fetched_at,
            "error": self.error,
            "source": "SHMÚ",
        }


def _first_number(text: str) -> float | None:
    match = re.search(r"-?\d+(?:[.,]\d+)?", text)
    return float(match.group(0).replace(",", ".")) if match else None


def _parse_station(name: str, url: str) -> dict[str, Any]:
    response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "danube-water-level/0.1"})
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser", from_encoding="utf-8")

    flood_thresholds = []
    text = soup.get_text(" ", strip=True)
    for degree in (1, 2, 3):
        patterns = [
            rf"{degree}\.\s*stupeň[^0-9]*(\d+)\s*cm",
            rf"{degree}(?:st|nd|rd|th)?\s*(?:flood|degree)[^0-9]*(\d+)\s*cm",
        ]
        value = None
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                break
        flood_thresholds.append(value)

    measurements = []
    for tr in soup.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        # Measurement table rows begin with a date/time and then water stage in cm.
        if not re.search(r"\d{1,2}\.\d{1,2}\.\d{4}", cells[0]):
            continue
        level = _first_number(cells[1])
        if level is not None:
            measurements.append({"timestamp": cells[0], "level_cm": level})

    if not measurements:
        raise ValueError(f"No current SHMÚ measurements found for {name}")

    current = measurements[0]
    return {
        "name": name,
        "level_cm": current["level_cm"],
        "timestamp": current["timestamp"],
        "flood_stage_1_cm": flood_thresholds[0],
        "flood_stage_2_cm": flood_thresholds[1],
        "flood_stage_3_cm": flood_thresholds[2],
        "source_url": url,
    }


def fetch_slovakia_data() -> SlovakiaData:
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        gauges = [_parse_station(name, url) for name, url in STATIONS.items()]
        return SlovakiaData(gauges=gauges, fetched_at=fetched_at)
    except (requests.RequestException, ValueError) as exc:
        return SlovakiaData(gauges=[], fetched_at=fetched_at, error=str(exc))
