# Danube Water Level

A Flask web application for showing navigation status along the Danube for river-cruise travel, initially focused on the Budapest to Regensburg route.

The goal is to turn live river and navigation data into an easy-to-read route display:

- **Green** — conditions have a configured safety margin above the assumed vessel requirement.
- **Yellow** — passage is uncertain because conditions are close to limits or data is incomplete.
- **Red** — published conditions are below the assumed vessel requirement or an official restriction prevents passage.

The application is intended to combine gauge readings, fairway-depth information, bridge-clearance constraints, official navigation restrictions, forecasts, and vessel-specific operating limits.

## Initial route

Budapest → Bratislava → Vienna → Wachau → Linz → Passau → Vilshofen → Regensburg

## Current development status

The application now includes:

- Flask backend
- Leaflet/OpenStreetMap interactive map
- Simplified Danube route geometry stored as GeoJSON
- Independently colorable river sections
- Live Austrian DoRIS fairway information
- Current Austrian gauge readings and shallow-section depths
- A normalized JSON endpoint at `/api/austria`
- Prototype Austrian navigation coloring based on the minimum published deep-channel depth

Countries outside Austria remain undetermined until their live data sources are connected.

### Austrian prototype assumptions

The first passability calculation currently assumes:

- Vessel draft: **1.50 m**
- Safety margin: **0.30 m**

The current minimum deep-channel depth reported for Austrian shallow sections is compared with those values. These assumptions are placeholders and are not yet specific to a Scenic vessel.

DoRIS describes its continuously published values as unverified raw information and does not guarantee uninterrupted availability or accuracy. The application's current colors should therefore be treated as an informational prototype rather than navigation advice or a guarantee of vessel passage.

## Data source

Austrian fairway data is fetched from the official viadonau DoRIS Fairway Information Overview:

`https://www.doris.bmimi.gv.at/fileadmin/doris_iframe/OnePageInfo_en.html`

The backend parser is in `services/austria.py`.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Then open `http://127.0.0.1:5000`.

The normalized Austrian data can also be inspected at:

`http://127.0.0.1:5000/api/austria`

## Next steps

- Replace placeholder vessel draft with vessel-specific requirements
- Map Austrian shallow sections more precisely to individual route sections
- Add official Notices to Skippers and high-water closures
- Add bridge-clearance restrictions
- Connect Slovakia, Hungary, and Germany
- Add water-level trends and forecasts
