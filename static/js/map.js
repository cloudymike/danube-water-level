const route = window.DANUBE_ROUTE || [];

const statusColors = {
    green: "#166534",
    lime: "#84cc16",
    yellow: "#eab308",
    orange: "#f97316",
    red: "#dc2626",
    unknown: "#eab308",
};

const statusLabels = {
    green: "PASSABLE — authoritative data establish adequate navigation conditions",
    lime: "OBSERVED PASSABLE — recent cruise traffic supports passage, but authoritative depth data do not prove it",
    yellow: "UNDETERMINED — available data do not establish passability or non-passability",
    orange: "OBSERVED DISRUPTION — recent cruise operations were altered; this is operational evidence, not an official closure",
    red: "NOT PASSABLE — authoritative data establish a restriction or insufficient clearance",
    unknown: "UNDETERMINED — insufficient authoritative data",
};

function detailsForStop(stop) {
    const lines = [];
    if (stop.authoritative_status && stop.display_status && stop.authoritative_status !== stop.display_status) {
        lines.push(`Authoritative status: ${statusLabels[stop.authoritative_status] || stop.authoritative_status}`);
    }
    if (stop.status_source) lines.push(`Authoritative source: ${stop.status_source}`);
    if (stop.minimum_depth_m !== undefined && stop.minimum_depth_m !== null) {
        lines.push(`Minimum deep-channel depth: ${Number(stop.minimum_depth_m).toFixed(2)} m`);
    }
    if (stop.official_fairway_depth_m !== undefined && stop.official_fairway_depth_m !== null) {
        const scope = stop.official_depth_scope ? ` (${stop.official_depth_scope})` : "";
        lines.push(`Official fairway depth at RNW: ${Number(stop.official_fairway_depth_m).toFixed(2)} m${scope}`);
    }
    if (Array.isArray(stop.segment_reasons)) stop.segment_reasons.forEach((reason) => lines.push(reason));
    if (Array.isArray(stop.shallow_section_names) && stop.shallow_section_names.length) lines.push(`Mapped shallow sections: ${stop.shallow_section_names.join(", ")}`);
    if (Array.isArray(stop.closure_names) && stop.closure_names.length) lines.push(`Official closures: ${stop.closure_names.join(", ")}`);
    if (Array.isArray(stop.lock_states) && stop.lock_states.length) lines.push(`Locks: ${stop.lock_states.join("; ")}`);
    if (Array.isArray(stop.gauge_states) && stop.gauge_states.length) lines.push(`Gauges: ${stop.gauge_states.join("; ")}`);
    if (stop.operational_evidence) {
        const ev = stop.operational_evidence;
        lines.push(`Operational evidence (${ev.confidence} confidence): ${ev.summary}`);
        lines.push(`Evidence source: ${ev.source_name}`);
        lines.push(`Evidence expires: ${ev.expires_at}`);
    }
    return lines.length ? `<br>${lines.join("<br>")}` : "";
}

const map = L.map("map", { scrollWheelZoom: true });
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);

const stopByName = Object.fromEntries(route.map((stop) => [stop.name, stop]));
const mapBounds = L.latLngBounds([]);

route.forEach((stop) => {
    const latLng = [stop.lat, stop.lon];
    const status = stop.display_status || stop.status || "unknown";
    const color = statusColors[status] || statusColors.unknown;
    mapBounds.extend(latLng);
    L.circleMarker(latLng, {radius: 7, color: "#ffffff", weight: 2, fillColor: color, fillOpacity: 1})
        .bindPopup(`<strong>${stop.name}</strong><br>Status: <span class="popup-status">${statusLabels[status] || statusLabels.unknown}</span>${detailsForStop(stop)}`)
        .addTo(map);
});

fetch("/static/data/danube-route.geojson")
    .then((response) => { if (!response.ok) throw new Error(`Unable to load Danube geometry (${response.status})`); return response.json(); })
    .then((geojson) => {
        const riverLayer = L.geoJSON(geojson, {
            style: (feature) => {
                const fromStop = stopByName[feature.properties.from];
                const status = fromStop?.display_status || fromStop?.status || "unknown";
                return {color: statusColors[status] || statusColors.unknown, weight: 7, opacity: 0.85, lineCap: "round", lineJoin: "round"};
            },
            onEachFeature: (feature, layer) => {
                const from = feature.properties.from; const to = feature.properties.to; const fromStop = stopByName[from];
                const status = fromStop?.display_status || fromStop?.status || "unknown";
                layer.bindPopup(`<strong>${from} → ${to}</strong><br>Navigation status: <span class="popup-status">${statusLabels[status] || statusLabels.unknown}</span>${detailsForStop(fromStop || {})}`);
            },
        }).addTo(map);
        mapBounds.extend(riverLayer.getBounds()); map.fitBounds(mapBounds, {padding: [30, 30]});
    })
    .catch((error) => { console.error(error); if (mapBounds.isValid()) map.fitBounds(mapBounds, {padding: [30, 30]}); else map.setView([48.5, 15.5], 6); });
