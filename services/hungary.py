"""Fetch current/forecast Danube levels from Hungary's official Hydroinfo pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

REQUEST_TIMEOUT = 10
STATIONS = {
    "Budapest": "https://www.hydroinfo.hu/tables/ENG/442027H.html",
    "Esztergom": "https://www.hydroinfo.hu/tables/ENG/442025H.html",
}


@dataclass
class HungaryData:
    gauges: list[dict[str, Any]]
    fetched_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gauges": self.gauges,
            "fetched_at": self.fetched_at,
            "error": self.error,
            "source": "Hungarian Hydroinfo",
        }


def _parse_station(name: str, url: str) -> dict[str, Any]:
    response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "danube-water-level/0.1"})
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser", from_encoding="utf-8")
    text = soup.get_text(" ", strip=True)

    issued_at = None
    marker = "Issued at:"
    if marker in text:
        issued_at = text.split(marker, 1)[1].split("Water level forecast", 1)[0].strip()

    rows = []
    for tr in soup.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        candidate = cells[-1].replace("−", "-").replace("–", "-").strip()
        try:
            value = float(candidate.split()[0])
        except (ValueError, IndexError):
            continue
        rows.append({"label": " ".join(cells[:-1]), "level_cm": value})

    if not rows:
        raise ValueError(f"No water-level rows found for {name}")

    # Hydroinfo forecast pages place the observed/current morning value first.
    current = rows[0]
    return {
        "name": name,
        "level_cm": current["level_cm"],
        "observation_label": current["label"],
        "issued_at": issued_at,
        "source_url": url,
    }


def fetch_hungary_data() -> HungaryData:
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        gauges = [_parse_station(name, url) for name, url in STATIONS.items()]
        return HungaryData(gauges=gauges, fetched_at=fetched_at)
    except (requests.RequestException, ValueError) as exc:
        return HungaryData(gauges=[], fetched_at=fetched_at, error=str(exc))
