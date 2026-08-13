"""Fetch current German Danube fairway restrictions from ELWIS.

ELWIS publishes fairway restrictions as Notices to Skippers (NfB).  This
service queries the current restriction list, follows candidate Danube notices,
and normalizes their river-km range and restriction text for route logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.elwis.de"
# Current NfB notices carrying restrictions.  ELWIS may return notices for many
# waterways, so the parser keeps only notices whose result text identifies Donau.
LIST_URL = (
    BASE_URL
    + "/DE/dynamisch/Nfb/NfbList:elwis_nfb_search:1"
    + "?searchParams%5BalleNfbs%5D=1"
    + "&searchParams%5Beinschraenkung%5D=1"
    + "&searchParams%5BausgabeIn%5D=6"
    + "&searchParams%5BsortColumn%5D=nfb_id"
    + "&searchParams%5BsortOrder%5D=desc"
)
REQUEST_TIMEOUT = 10
GERMAN_DANUBE_KM_MIN = 2201.8
GERMAN_DANUBE_KM_MAX = 2414.7


@dataclass
class GermanyRestrictionsData:
    restrictions: list[dict[str, Any]]
    source_url: str = LIST_URL
    fetched_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "restrictions": self.restrictions,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at,
            "error": self.error,
        }


def _number(text: str) -> float | None:
    """Parse German-formatted river-km/depth numbers such as 2.303,4."""
    match = re.search(r"(?:\d{1,3}\.)?\d{1,3}(?:,\d+)?", text or "")
    if not match:
        return None
    raw = match.group(0).replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _candidate_links(html: bytes) -> list[str]:
    soup = BeautifulSoup(html, "html.parser", from_encoding="utf-8")
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href"))
        if "NfbDetailview" not in href:
            continue
        context = " ".join(anchor.parent.stripped_strings) if anchor.parent else anchor.get_text(" ", strip=True)
        # Keep explicit Danube results.  If ELWIS changes the list layout and the
        # waterway is not repeated in the row, detail parsing below is still safe,
        # but we avoid following every German notice by default.
        if "Donau" in context or "Donau" in anchor.get_text(" ", strip=True):
            links.append(urljoin(BASE_URL, href))
    return list(dict.fromkeys(links))


def _detail_restrictions(html: bytes, url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser", from_encoding="utf-8")
    text = "\n".join(soup.stripped_strings)
    if "Wasserstraße Donau" not in text and "Wasserstrasse Donau" not in text:
        return []
    if "Diese NfB ist abgelaufen" in text:
        return []

    # ELWIS detail pages contain one or more waterway table rows.  Parse table
    # rows because they retain the locality, km range, and restriction together.
    results: list[dict[str, Any]] = []
    for row in soup.find_all("tr"):
        cells = [" ".join(cell.stripped_strings) for cell in row.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        row_text = " | ".join(cells)
        km_values = []
        for match in re.finditer(r"\b(?:2\.)?\d{3},\d\b", row_text):
            value = _number(match.group(0))
            if value is not None and GERMAN_DANUBE_KM_MIN - 5 <= value <= GERMAN_DANUBE_KM_MAX + 5:
                km_values.append(value)
        if not km_values:
            continue
        km_from = km_values[0]
        km_to = km_values[1] if len(km_values) > 1 else km_from
        restriction_text = " ".join(cells[1:])
        lowered = restriction_text.casefold()
        if "keine einschränkung" in lowered:
            continue
        if not any(word in lowered for word in ("einschr", "sperre", "tiefe", "breite", "fahrwasser", "fahrrinne")):
            continue
        results.append(
            {
                "name": cells[0] or "ELWIS fairway restriction",
                "river_km_from": km_from,
                "river_km_to": km_to,
                "restriction": restriction_text,
                "source_url": url,
            }
        )
    return results


def fetch_germany_restrictions() -> GermanyRestrictionsData:
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        session = requests.Session()
        headers = {"User-Agent": "danube-water-level/0.1"}
        response = session.get(LIST_URL, timeout=REQUEST_TIMEOUT, headers=headers)
        response.raise_for_status()
        links = _candidate_links(response.content)

        restrictions: list[dict[str, Any]] = []
        for url in links[:30]:
            detail = session.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
            detail.raise_for_status()
            restrictions.extend(_detail_restrictions(detail.content, url))

        # Remove duplicate table representations of the same notice/range.
        unique = []
        seen = set()
        for item in restrictions:
            key = (item["source_url"], item["river_km_from"], item["river_km_to"], item["restriction"])
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return GermanyRestrictionsData(restrictions=unique, fetched_at=fetched_at)
    except (requests.RequestException, ValueError, TypeError) as exc:
        return GermanyRestrictionsData(restrictions=[], fetched_at=fetched_at, error=str(exc))
