"""Fetch and normalize official Austrian Danube fairway information from DoRIS."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

DORIS_OVERVIEW_URL = "https://www.doris.bmimi.gv.at/fileadmin/doris_iframe/OnePageInfo_en.html"
REQUEST_TIMEOUT = 10


@dataclass
class AustriaData:
    gauges: list[dict[str, Any]]
    shallow_sections: list[dict[str, Any]]
    source_url: str = DORIS_OVERVIEW_URL
    fetched_at: str | None = None
    source_updated_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gauges": self.gauges,
            "shallow_sections": self.shallow_sections,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at,
            "source_updated_at": self.source_updated_at,
            "error": self.error,
        }


def _number(text: str) -> float | None:
    """Return the first numeric value from a table cell."""
    cleaned = text.strip().replace(",", ".")
    token = ""
    started = False
    for char in cleaned:
        if char.isdigit() or (char in ".-" and (started or char == "-")):
            token += char
            started = True
        elif started:
            break
    try:
        return float(token) if token not in {"", "-", ".", "-."} else None
    except ValueError:
        return None


def _table_after_heading(soup: BeautifulSoup, heading_text: str):
    heading = soup.find(
        lambda tag: tag.name in {"h1", "h2", "h3", "h4"}
        and heading_text.lower() in tag.get_text(" ", strip=True).lower()
    )
    return heading.find_next("table") if heading else None


def _parse_gauges(table) -> list[dict[str, Any]]:
    if table is None:
        return []

    gauges = []
    for row in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        if len(cells) < 2 or cells[0].lower() in {"water gauge", "gauge"}:
            continue
        current = _number(cells[1])
        if current is None:
            continue
        gauges.append(
            {
                "name": cells[0],
                "level_cm": current,
                "hour_change_cm": _number(cells[2]) if len(cells) > 2 else None,
                "forecast_24h_cm": _number(cells[3]) if len(cells) > 3 else None,
                "forecast_48h_cm": _number(cells[4]) if len(cells) > 4 else None,
                "forecast_72h_cm": _number(cells[5]) if len(cells) > 5 else None,
            }
        )
    return gauges


def _parse_shallow_sections(table) -> list[dict[str, Any]]:
    if table is None:
        return []

    sections = []
    for row in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        if len(cells) < 4:
            continue

        # DoRIS table columns begin with name, river-km from/to, marked fairway
        # depth, then deep-channel depth. Values are published in decimetres.
        river_km_from = _number(cells[1])
        river_km_to = _number(cells[2])
        marked_depth_dm = _number(cells[3])
        deep_depth_dm = _number(cells[4]) if len(cells) > 4 else None
        if river_km_from is None or river_km_to is None:
            continue

        sections.append(
            {
                "name": cells[0],
                "river_km_from": river_km_from,
                "river_km_to": river_km_to,
                "marked_fairway_depth_m": marked_depth_dm / 10 if marked_depth_dm is not None else None,
                "deep_channel_depth_m": deep_depth_dm / 10 if deep_depth_dm is not None else None,
                "forecast_24h_depth_m": (_number(cells[5]) / 10) if len(cells) > 5 and _number(cells[5]) is not None else None,
                "forecast_48h_depth_m": (_number(cells[6]) / 10) if len(cells) > 6 and _number(cells[6]) is not None else None,
                "forecast_72h_depth_m": (_number(cells[7]) / 10) if len(cells) > 7 and _number(cells[7]) is not None else None,
            }
        )
    return sections


def fetch_austria_data() -> AustriaData:
    """Retrieve the current Austrian fairway overview from official DoRIS."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        response = requests.get(
            DORIS_OVERVIEW_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "danube-water-level/0.1"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        gauges_table = _table_after_heading(soup, "Waterlevels")
        shallow_table = _table_after_heading(soup, "Shallow sections")

        # The overview includes timestamps immediately below the section headings.
        source_updated_at = None
        water_heading = soup.find(
            lambda tag: tag.name in {"h1", "h2", "h3", "h4"}
            and "waterlevels" in tag.get_text(" ", strip=True).lower()
        )
        if water_heading:
            timestamp_heading = water_heading.find_next(["h3", "h4"])
            if timestamp_heading:
                source_updated_at = timestamp_heading.get_text(" ", strip=True)

        gauges = _parse_gauges(gauges_table)
        shallow_sections = _parse_shallow_sections(shallow_table)
        if not gauges and not shallow_sections:
            raise ValueError("DoRIS page loaded but expected fairway tables were not found")

        return AustriaData(
            gauges=gauges,
            shallow_sections=shallow_sections,
            fetched_at=fetched_at,
            source_updated_at=source_updated_at,
        )
    except (requests.RequestException, ValueError) as exc:
        return AustriaData(
            gauges=[],
            shallow_sections=[],
            fetched_at=fetched_at,
            error=str(exc),
        )
