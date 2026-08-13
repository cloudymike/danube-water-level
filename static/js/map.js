const route = window.DANUBE_ROUTE || [];

const statusColors = {
    green: "#16a34a",
    yellow: "#eab308",
    red: "#dc2626",
    unknown: "#eab308",
};

const statusLabels = {
    green: "No identified restriction",
    yellow: "Caution / reduced margin",
    red: "Navigation blocked / threshold exceeded",
    unknown: "Undetermined",
};

function detailsForStop(stop) {
    const lines = [];
    if (stop.status_source) lines.push(`Source: ${stop.status_source}`);
    if (stop.minimum_depth_m !== undefined && stop.minimum_depth_m !== null) {
        lines.push(`Minimum deep-channel depth: ${Number(stop.minimum_depth_m).toFixed(2)} m`);
    }
    if (stop.official_fairway_depth_m !== undefined && stop.official_fairway_depth_m !== null) {
        const scope = stop.official_depth_scope ? ` (${stop.official_depth_scope})` : "";
        lines.push(`Official fairway depth at RNW: ${Number(stop.official_fairway_depth_m).toFixed(2)} m${scope}`);
    }
    if (Array.isArray(stop.segment_reasons)) {
        stop.segment_reasons.forEach((reason) => lines.push(reason));
    }
    if (Array.isArray(stop.shallow_section_names) && stop.shallow_section_names.length) {
        lines.push(`Mapped shallow sections: ${stop.shallow_section_names.join(", ")}`);
    }
    if (Array.isArray(stop.closure_names) && stop.closure_names.length) {
        lines.push(`Official closures: ${stop.closure_names.join(", ")}`);
    }
    if (Array.isArray(stop.lock_states) && stop.lock_states.length) {
        lines.push(`Locks: ${stop.lock_states.join("; ")}`);
    }
    if (Array.isArray(stop.gauge_states) && stop.gauge_states.length) {
        lines.push(`Gauges: ${stop.gauge_states.join("; ")}`);
    }
    if (stop.high_water_override) lines.push("High-water override active");
    return lines.length ? `<br>${lines.join("<br>")}` : "";
}

const map = L.map("map", { scrollWheelZoom: true });

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

const stopByName = Object.fromEntries(route.map((stop) => [stop.name, stop]));
const mapBounds = L.latLngBounds([]);

route.forEach((stop) => {
    const latLng = [stop.lat, stop.lon];
    const status = stop.status || "unknown";
    const color = statusColors[status] || statusColors.unknown;
    mapBounds.extend(latLng);

    L.circleMarker(latLng, {
        radius: 7,
        color: "#ffffff",
        weight: 2,
        fillColor: color,
        fillOpacity: 1,
    })
        .bindPopup(
            `<strong>${stop.name}</strong><br>` +
            `Status: <span class="popup-status">${statusLabels[status] || statusLabels.unknown}</span>` +
            detailsForStop(stop)
        )
        .addTo(map);
});

fetch("/static/data/danube-route.geojson")
    .then((response) => {
        if (!response.ok) throw new Error(`Unable to load Danube geometry (${response.status})`);
        return response.json();
    })
    .then((geojson) => {
        const riverLayer = L.geoJSON(geojson, {
            style: (feature) => {
                const fromStop = stopByName[feature.properties.from];
                const status = fromStop?.status || "unknown";
                return {
                    color: statusColors[status] || statusColors.unknown,
                    weight: 7,
                    opacity: 0.85,
                    lineCap: "round",
                    lineJoin: "round",
                };
            },
            onEachFeature: (feature, layer) => {
                const from = feature.properties.from;
                const to = feature.properties.to;
                const fromStop = stopByName[from];
                const status = fromStop?.status || "unknown";
                layer.bindPopup(
                    `<strong>${from} → ${to}</strong><br>` +
                    `Navigation status: <span class="popup-status">${statusLabels[status] || statusLabels.unknown}</span>` +
                    detailsForStop(fromStop || {})
                );
            },
        }).addTo(map);

        mapBounds.extend(riverLayer.getBounds());
        map.fitBounds(mapBounds, { padding: [30, 30] });
    })
    .catch((error) => {
        console.error(error);
        if (mapBounds.isValid()) map.fitBounds(mapBounds, { padding: [30, 30] });
        else map.setView([48.5, 15.5], 6);
    });
