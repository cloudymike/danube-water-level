# Danube Water Level

A Flask web application for showing navigation status along the Danube for river-cruise travel, initially focused on the Budapest to Regensburg route.

The goal is to turn live river and navigation data into an easy-to-read route display:

- **Green** — conditions indicate the selected vessel can pass.
- **Yellow** — passage is uncertain because conditions are close to limits or data is incomplete.
- **Red** — conditions or official restrictions indicate the selected vessel cannot pass.

The application will eventually combine gauge readings, fairway-depth information, bridge-clearance constraints, official navigation restrictions, forecasts, and vessel-specific operating limits.

## Initial route

Budapest → Bratislava → Vienna → Wachau → Linz → Passau → Vilshofen → Regensburg

## Development status

This repository currently contains the initial Flask application skeleton. Live river data and vessel-specific navigation logic will be added in subsequent iterations.

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

## Planned structure

- Flask backend for data collection and normalization
- Leaflet/OpenStreetMap frontend
- Color-coded Danube route segments
- Gauge and navigation-status details
- Configurable vessel draft, air draft, and safety margins
- Official navigation notices and closures
- Water-level trend and forecast information
