const route = window.DANUBE_ROUTE || [];

const statusColors = {
    green: "#16a34a",
    yellow: "#eab308",
    red: "#dc2626",
    unknown: "#eab308",
};

const statusLabels = {
    green: "Passable",
    yellow: "Undetermined",
    red: "Not passable",
    unknown: "Undetermined",
};

const map = L.map("map", {
    scrollWheelZoom: true,
});

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

const bounds = [];

route.forEach((stop, index) => {
    const latLng = [stop.lat, stop.lon];
    bounds.push(latLng);

    const status = stop.status || "unknown";
    const color = statusColors[status] || statusColors.unknown;

    L.circleMarker(latLng, {
        radius: 7,
        color: "#ffffff",
        weight: 2,
        fillColor: color,
        fillOpacity: 1,
    })
        .bindPopup(
            `<strong>${stop.name}</strong><br>` +
            `Status: <span class="popup-status">${statusLabels[status] || statusLabels.unknown}</span>`
        )
        .addTo(map);

    if (index < route.length - 1) {
        const next = route[index + 1];
        const segmentStatus = stop.status || "unknown";
        const segmentColor = statusColors[segmentStatus] || statusColors.unknown;

        L.polyline(
            [latLng, [next.lat, next.lon]],
            {
                color: segmentColor,
                weight: 7,
                opacity: 0.85,
                lineCap: "round",
            }
        )
            .bindPopup(
                `<strong>${stop.name} → ${next.name}</strong><br>` +
                `Navigation status: <span class="popup-status">${statusLabels[segmentStatus] || statusLabels.unknown}</span>`
            )
            .addTo(map);
    }
});

if (bounds.length > 0) {
    map.fitBounds(bounds, {
        padding: [30, 30],
    });
} else {
    map.setView([48.5, 15.5], 6);
}
