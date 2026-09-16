// 외교부 해외안전여행 지도와 같은 색 체계
const LEVEL_STYLE = {
  1: { cls: "level-1", color: "#1f5fbf", label: "1단계 여행유의" },
  2: { cls: "level-2", color: "#e0b83a", label: "2단계 여행자제" },
  2.5: { cls: "level-special", color: "#d9534f", label: "특별여행주의보", dashed: true },
  3: { cls: "level-3", color: "#c0392b", label: "3단계 출국권고" },
  4: { cls: "level-4", color: "#222", label: "4단계 여행금지" },
};

const styleOf = (level) => LEVEL_STYLE[level] || { cls: "level-unknown", color: "#8a97a8", label: "정보 없음" };

function formatDateTime(iso) {
  return iso ? new Date(iso).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" }) : "-";
}

function renderSummary(data) {
  const badge = document.getElementById("overall-badge");
  const mofa = data.mofa || {};
  const stale = mofa.stale ? " (이전 값)" : "";

  if (data.overall) {
    const s = styleOf(data.overall.level);
    badge.className = `badge ${s.cls}`;
    badge.textContent = `${s.label}${stale}`;
  } else {
    badge.className = "badge level-unknown";
    badge.textContent = "외교부 데이터 수집 실패";
  }

  const list = document.getElementById("region-levels");
  list.innerHTML = "";
  (mofa.regions || []).forEach((r) => {
    const s = styleOf(r.level);
    const li = document.createElement("li");
    li.innerHTML = `<span class="dot ${s.cls}"></span><strong>${r.name}</strong> ${s.label}`;
    list.appendChild(li);
  });

  const fcdo = data.fcdo || {};
  document.getElementById("fcdo-line").textContent = fcdo.text
    ? `영국 FCDO: ${fcdo.text}${fcdo.stale ? " (이전 값)" : ""}`
    : "";
  document.getElementById("last-updated").textContent = `마지막 업데이트: ${formatDateTime(data.generated_at)}`;
}

function renderMap(data) {
  const map = L.map("map", { scrollWheelZoom: false }).setView([22.8, 38.6], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 10,
  }).addTo(map);

  (data.mofa?.regions || []).forEach((r) => {
    const s = styleOf(r.level);
    L.circle([r.lat, r.lon], {
      radius: 60000,
      color: s.color,
      weight: 2,
      dashArray: s.dashed ? "6 6" : null,
      fillColor: s.color,
      fillOpacity: 0.35,
    })
      .addTo(map)
      .bindTooltip(`${r.name} · ${s.label}`, { permanent: true, direction: "top" });
  });

  const legend = document.getElementById("legend");
  Object.values(LEVEL_STYLE).forEach((s) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="dot ${s.cls}"></span>${s.label}`;
    legend.appendChild(li);
  });
}

function renderNotices(data) {
  const list = document.getElementById("notice-list");
  const notices = data.mofa?.notices || [];
  list.innerHTML = "";
  if (notices.length === 0) {
    list.innerHTML = '<li class="muted">표시할 공지가 없습니다.</li>';
    return;
  }
  notices.forEach((n) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="notice-date">${n.date}</div>
      <a href="${n.url}" target="_blank" rel="noopener">${n.title}</a>
      ${n.summary ? `<p class="summary">${n.summary}</p>` : ""}`;
    list.appendChild(li);
  });
}

function renderChart(data) {
  const weekly = data.mofa?.weekly_counts || [];
  new Chart(document.getElementById("trend-chart"), {
    type: "bar",
    data: {
      labels: weekly.map((w) => w.week.slice(5)),
      datasets: [{ data: weekly.map((w) => w.count), backgroundColor: "#c0392b" }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#8a97a8" }, grid: { display: false } },
        y: { ticks: { color: "#8a97a8", precision: 0 }, grid: { color: "#263140" }, beginAtZero: true },
      },
    },
  });
}

async function main() {
  try {
    const res = await fetch("data/latest.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`data/latest.json ${res.status}`);
    const data = await res.json();
    renderSummary(data);
    renderMap(data);
    renderNotices(data);
    renderChart(data);
  } catch (err) {
    document.getElementById("overall-badge").textContent = "데이터 로드 실패";
    console.error(err);
  }
}

main();
