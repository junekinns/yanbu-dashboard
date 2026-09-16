const RISK_LABELS = {
  calm: { class: "risk-calm", emoji: "🟢" },
  caution: { class: "risk-caution", emoji: "🟡" },
  alert: { class: "risk-alert", emoji: "🔴" },
};

function formatDateTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" });
}

function renderSummary(data) {
  const badge = document.getElementById("risk-badge");
  const risk = RISK_LABELS[data.risk_level] || { class: "risk-unknown", emoji: "❔" };
  badge.className = `risk-badge ${risk.class}`;
  badge.textContent = `${risk.emoji} ${data.risk_label_ko || "확인 불가"}`;

  document.getElementById("acled-count").textContent = `${data.acled?.count_7d ?? "-"}건`;

  const ukmtoCount = data.ukmto?.count_7d ?? 0;
  document.getElementById("ukmto-count").textContent =
    data.ukmto?.ok || data.ukmto?.stale ? `${ukmtoCount}건${data.ukmto?.stale ? " (이전 값)" : ""}` : "수집 실패";

  const advisory = data.advisory;
  document.getElementById("advisory-level").textContent = advisory?.text
    ? `${advisory.text}${advisory.stale ? " (이전 값)" : ""}`
    : "수집 실패";

  document.getElementById("last-updated").textContent = `마지막 업데이트: ${formatDateTime(data.generated_at)}`;
}

function renderMap(data) {
  const map = L.map("map", { scrollWheelZoom: false }).setView([22.8, 38.6], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 12,
  }).addTo(map);

  (data.regions || []).forEach((region) => {
    L.circle([region.lat, region.lon], {
      radius: region.radius_km * 1000,
      color: "#8a97a8",
      weight: 1,
      fillOpacity: 0.03,
    }).addTo(map).bindTooltip(region.name, { permanent: false });
  });

  const acledEvents = data.acled?.events || [];
  acledEvents.forEach((e) => {
    L.circleMarker([e.lat, e.lon], {
      radius: 6,
      color: "#d9534f",
      fillColor: "#d9534f",
      fillOpacity: 0.8,
    })
      .addTo(map)
      .bindPopup(`<strong>${e.type || "사건"}</strong><br>${e.date}<br>${e.region}<br>${e.notes || ""}`);
  });

  if (acledEvents.length === 0) {
    // 표시할 사건이 없으면 지역 원만 보여줌
  }
}

function renderChart(data) {
  const weekly = data.acled?.count_90d_weekly || [];
  const ctx = document.getElementById("trend-chart");
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: weekly.map((w) => w.week),
      datasets: [
        {
          label: "ACLED 사건 수 (주간)",
          data: weekly.map((w) => w.count),
          backgroundColor: "#d9534f",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#8a97a8" }, grid: { color: "#263140" } },
        y: { ticks: { color: "#8a97a8", precision: 0 }, grid: { color: "#263140" }, beginAtZero: true },
      },
    },
  });
}

async function main() {
  try {
    const res = await fetch("data/latest.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`data/latest.json 로드 실패: ${res.status}`);
    const data = await res.json();
    renderSummary(data);
    renderMap(data);
    renderChart(data);
  } catch (err) {
    document.getElementById("risk-badge").textContent = "데이터 로드 실패";
    console.error(err);
  }
}

main();
