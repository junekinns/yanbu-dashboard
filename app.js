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

  const news = data.news || {};
  document.getElementById("news-count").textContent = news.ok || news.stale
    ? `${news.count_recent ?? 0}건${news.stale ? " (이전 값)" : ""}`
    : "수집 실패";

  const advisory = data.advisory || {};
  document.getElementById("advisory-level").textContent = advisory.text
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
      fillOpacity: 0.05,
    })
      .addTo(map)
      .bindTooltip(region.name, { permanent: true, direction: "center", className: "region-label" });
  });
}

function renderChart(data) {
  const daily = data.news?.daily_counts || [];
  const ctx = document.getElementById("trend-chart");
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: daily.map((d) => d.date.slice(5)), // MM-DD
      datasets: [
        {
          label: "관련 뉴스 기사 수 (일별)",
          data: daily.map((d) => d.count),
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

function renderNewsList(data) {
  const list = document.getElementById("news-list");
  const events = data.news?.events || [];
  list.innerHTML = "";

  if (events.length === 0) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "최근 7일간 관련 뉴스가 확인되지 않았습니다.";
    list.appendChild(li);
    return;
  }

  events.forEach((e) => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = e.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = e.title;
    const meta = document.createElement("div");
    meta.className = "muted small";
    meta.textContent = `${e.date} · ${e.domain || ""}`;
    li.appendChild(a);
    li.appendChild(meta);
    list.appendChild(li);
  });
}

function renderLinks(data) {
  const container = document.getElementById("links-groups");
  const links = data.external_links || [];
  const groups = {};
  links.forEach((link) => {
    if (!groups[link.group]) groups[link.group] = [];
    groups[link.group].push(link);
  });

  container.innerHTML = "";
  Object.entries(groups).forEach(([groupName, items]) => {
    const h3 = document.createElement("h3");
    h3.textContent = groupName;
    container.appendChild(h3);

    const ul = document.createElement("ul");
    ul.className = "link-list";
    items.forEach((item) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = item.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = item.name;
      const desc = document.createElement("div");
      desc.className = "muted small";
      desc.textContent = item.description;
      li.appendChild(a);
      li.appendChild(desc);
      ul.appendChild(li);
    });
    container.appendChild(ul);
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
    renderNewsList(data);
    renderLinks(data);
  } catch (err) {
    document.getElementById("risk-badge").textContent = "데이터 로드 실패";
    console.error(err);
  }
}

main();
