# Danube Water Level

A Flask web application that shows river-cruise navigation status along the Danube, currently focused on the Budapest → Regensburg route.

The application combines official river/navigation data with separate operational cruise evidence and displays the result on an interactive Leaflet/OpenStreetMap map.

## Route

Budapest → Esztergom → Komárno → Bratislava → Vienna → Wachau → Linz → Passau → Vilshofen → Straubing → Regensburg

## Status colors

The map uses five colors so authoritative navigation information is kept separate from observed cruise operations:

- **Dark green — PASSABLE:** authoritative data establish adequate navigation conditions for the configured vessel assumptions.
- **Lime — OBSERVED PASSABLE:** recent comparable cruise traffic supports passage, but authoritative depth data do not independently prove it.
- **Yellow — UNDETERMINED:** available data do not establish either passability or non-passability.
- **Orange — OBSERVED DISRUPTION:** recent cruise operations were altered, such as ship swaps, shortened sailings, or passenger transfers by land.
- **Red — NOT PASSABLE:** authoritative data establish a closure, high-water restriction, insufficient clearance, or another blocking condition.

Operational lime/orange evidence never replaces authoritative green/red. It only refines otherwise yellow/unknown sections.

## Vessel assumptions

The current prototype assumes:

- Vessel draft: **1.50 m**
- Safety margin: **0.30 m**
- Required navigation depth for a green depth-based result: **1.80 m**

These values are placeholders and are not yet tied to a specific Scenic vessel.

## Data refresh

Live data is fetched when the Flask page is loaded.

Refreshing the browser, or using the **Refresh data** button, causes the application to retrieve the current upstream data again and recalculate all section statuses. There is currently no automatic background refresh.

The page displays a local **Data loaded** timestamp so it is clear when the currently displayed data was retrieved.

## Country data sources and logic

### Austria

Austria uses official viadonau/DoRIS information, including:

- Current Danube gauge readings
- Shallow-section deep-channel depths
- Section closures
- Lock chamber availability
- High-water restrictions

Austrian shallow sections are mapped to route segments by river-kilometer range. The minimum relevant published deep-channel depth is compared with the configured vessel draft and safety margin.

DoRIS values are treated as official operational information but remain subject to the source agency's own accuracy/availability disclaimers.

Implementation: `services/austria.py` and `services/navigation.py`

### Germany

Germany uses official WSV/ELWIS and PEGELONLINE information.

PEGELONLINE supplies current German Danube gauge readings and characteristic values including **RNW** (Regulierungsniedrigwasserstand / Regulation Low Water Level) and **HSW** high-water limits.

The current navigation calculation uses WSV-published fairway depths at the applicable RNW reference gauges:

- Passau → Vilshofen: approximately **2.70 m**
- Vilshofen → Straubing: controlling value **2.00 m** for the Sand → Vilshofen reach
- Straubing → Sand: **2.65 m**
- Straubing → Regensburg: **2.90 m**

When all required reference gauges are at or above RNW and the official fairway depth exceeds the configured 1.80 m vessel requirement, the section can be dark green. Below RNW, the application does not extrapolate a simple gauge-to-depth formula; the result remains yellow unless stronger evidence is available.

German status also checks live ELWIS **Fahrrinneneinschränkungen** / Notices to Skippers:

- An explicit closure makes the affected segment red.
- Another active fairway restriction downgrades an otherwise green segment to yellow.
- If the ELWIS restriction feed cannot be retrieved, an otherwise green German section is conservatively downgraded to yellow.

Implementation: `services/germany.py`, `services/germany_restrictions.py`, and `services/germany_status.py`

### Hungary

Hungary uses official Hydroinfo Danube gauge data, including Budapest and Esztergom.

Gauge height alone is not converted into a vessel-specific fairway depth, so ordinary Hungarian sections remain yellow unless stronger authoritative or operational evidence is available.

Implementation: `services/hungary.py`

### Slovakia

Slovakia uses official SHMÚ Danube gauge information for Komárno and Bratislava.

The app uses published flood-activity thresholds as high-water evidence. Ordinary gauge levels are not converted into a vessel-specific fairway depth, so these sections normally remain yellow unless another evidence layer applies.

Implementation: `services/slovakia.py`

## Operational cruise evidence

Operational evidence is kept in a separate layer from official navigation status.

The current implementation supports time-bounded observations such as cruise itinerary disruptions. Each observation contains:

- Affected route segment
- Signal (`observed_passable` or `observed_disruption`)
- Observation time
- Expiration time
- Summary
- Source
- Confidence level

The current implementation uses curated public reporting. The architecture is designed so AIS or port-call data can later be added without changing the underlying authoritative navigation logic.

Implementation: `services/operational.py`

## Map

The frontend uses Leaflet with OpenStreetMap tiles.

The Danube route geometry is stored separately in:

`static/data/danube-route.geojson`

Each route section can therefore be colored independently while the geographic geometry remains separate from the navigation calculations.

## API endpoints

The application exposes normalized JSON endpoints for troubleshooting and future frontend use:

- `/api/austria`
- `/api/germany`
- `/api/hungary`
- `/api/slovakia`
- `/api/operations`

`/api/germany` includes current PEGELONLINE gauge information, calculated segment status, RNW fairway-depth assumptions, and the normalized ELWIS fairway-restriction feed.

## Project structure

```text
app.py
services/
    austria.py
    germany.py
    germany_restrictions.py
    germany_status.py
    hungary.py
    navigation.py
    operational.py
    slovakia.py
static/
    css/style.css
    data/danube-route.geojson
    js/map.js
templates/
    index.html
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Then open:

`http://127.0.0.1:5000`

## Limitations

This is an informational application, not navigation advice or a guarantee that a specific cruise vessel will sail an advertised itinerary.

Important limitations include:

- The configured vessel draft is still generic.
- Gauge heights are not treated as direct fairway-depth measurements unless an official relationship supports that conversion.
- Operator-specific safety margins and loading conditions are generally not public.
- Bridge/air-draft constraints are not yet fully modeled.
- Operational evidence may apply to a cruise itinerary without proving that every individual river segment was physically impassable.
- Public upstream data feeds can be unavailable or change format.

## Possible next steps

- Add Scenic-specific vessel dimensions and draft where reliable data are available.
- Add bridge-clearance and air-draft constraints.
- Add water-level trends and forecasts.
- Add an AIS/port-call evidence provider for recent comparable cruise-vessel transits.
- Improve route geometry and river-kilometer mapping where needed.
- Add tests for country parsers and navigation status rules.
