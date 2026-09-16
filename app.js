// 외교부 해외안전여행 지도와 같은 색 체계
const LEVEL_STYLE = {
  1: { cls: "level-1", color: "#1f5fbf", label: "1단계 여행유의" },
  2: { cls: "level-2", color: "#e0b83a", label: "2단계 여행자제" },
  2.5: { cls: "level-special", color: "#d9534f", label: "특별여행주의보", dashed: true },
  3: { cls: "level-3", color: "#c0392b", label: "3단계 출국권고" },
  4: { cls: "level-4", color: "#222", label: "4단계 여행금지" },
};
const styleOf = (level) => LEVEL_STYLE[level] || { cls: "level-unknown", color: "#8a97a8", label: "정보 없음" };

const TYPE_STYLE = {
  경보: { cls: "t-alert", color: "#d9534f" },
  요격: { cls: "t-intercept", color: "#1f5fbf" },
  피격: { cls: "t-hit", color: "#b8442f" },
  공습: { cls: "t-airstrike", color: "#6b4fbf" },
};

const severity = (ratio) => (ratio == null ? "" : ratio >= 3 ? "hot" : ratio >= 1.5 ? "warm" : "calm");
// 해상 교통은 낮을수록 위험: 평시의 1/3 이하면 hot, 2/3 이하면 warm
const dropSeverity = (ratio) => (ratio == null ? "" : ratio <= 0.34 ? "hot" : ratio <= 0.67 ? "warm" : "calm");
const SEV_COLOR = { hot: "#e5533d", warm: "#e0b83a", calm: "#3fa66b", "": "#8a97a8" };
const staleTag = (src) => (src?.stale ? " (이전 값)" : "");
const pct = (x) => (x?.ratio != null ? `${Math.round(x.ratio * 100)}%` : "–");

function sparkline(canvas, labels, values, type, color) {
  new Chart(canvas, {
    type,
    data: { labels, datasets: [{ data: values, borderColor: color, backgroundColor: color, borderWidth: 2, pointRadius: 0, tension: 0.3, fill: false }] },
    options: {
      animation: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { title: (items) => labels[items[0].dataIndex] } } },
      scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
    },
  });
}

function fillTile(id, { value, ratio, sev, sub, labels, values, type }) {
  const tile = document.getElementById(id);
  tile.querySelector(".value").textContent = value;
  tile.querySelector(".sub").textContent = sub;
  tile.classList.remove("hot", "warm", "calm");
  const level = sev ?? severity(ratio);
  if (level) tile.classList.add(level);
  sparkline(tile.querySelector("canvas"), labels, values, type, SEV_COLOR[level]);
}

function renderAttention(att) {
  const yanbu = att.articles?.find((a) => a.key === "yanbu");
  const jeddah = att.articles?.find((a) => a.key === "jeddah");
  if (!yanbu) return fillTile("tile-attention", { value: "–", sub: `수집 실패: ${att.error || ""}`, labels: [], values: [], type: "line" });
  fillTile("tile-attention", {
    value: yanbu.ratio != null ? `${yanbu.ratio}×` : "–",
    ratio: yanbu.ratio,
    sub: `얀부 ${yanbu.latest}회 (평시 ${Math.round(yanbu.baseline)}) · 제다 ${jeddah?.ratio ?? "–"}× · ${yanbu.latest_date}${staleTag(att)}`,
    labels: yanbu.series.map((s) => s.date),
    values: yanbu.series.map((s) => s.views),
    type: "line",
  });
}

function renderFirms(firms) {
  if (!firms.daily_counts) return fillTile("tile-firms", { value: "–", sub: `수집 실패: ${firms.error || ""}`, labels: [], values: [], type: "bar" });
  const ratio = firms.baseline ? firms.last24h / firms.baseline : null;
  const base = firms.baseline != null ? `평시 ${firms.baseline}건/일` : "평시 기준선 수집 중";
  fillTile("tile-firms", {
    value: String(firms.last24h),
    ratio,
    sub: `얀부 ${firms.regions.yanbu.h24}건 · 제다 ${firms.regions.jeddah.h24}건 · 상시 플레어 ${firms.flares24h ?? 0}건 제외 · ${base}${staleTag(firms)}`,
    labels: firms.daily_counts.map((d) => d.date),
    values: firms.daily_counts.map((d) => d.count),
    type: "bar",
  });
}

function renderMofa(mofa) {
  const line = document.getElementById("mofa-line");
  if (mofa.regions) {
    line.innerHTML = "외교부 경보 · " + mofa.regions.map((r) => {
      const s = styleOf(r.level);
      return `<span class="dot ${s.cls}"></span>${r.name} <strong>${s.label}</strong>`;
    }).join(" · ") + staleTag(mofa);
  } else {
    line.textContent = "외교부 데이터 수집 실패";
  }

  if (!mofa.weekly_counts) return fillTile("tile-mofa", { value: "–", sub: `수집 실패: ${mofa.error || ""}`, labels: [], values: [], type: "bar" });
  fillTile("tile-mofa", {
    value: String(mofa.last7d),
    ratio: mofa.ratio,
    sub: `평시 ${mofa.baseline}건/주 · 7일 창 8개${staleTag(mofa)}`,
    labels: mofa.weekly_counts.map((w) => w.week),
    values: mofa.weekly_counts.map((w) => w.count),
    type: "bar",
  });

  const list = document.getElementById("notice-list");
  list.innerHTML = (mofa.notices || []).map((n) => `
    <li><div class="notice-date">${n.date}</div>
      <a href="${n.url}" target="_blank" rel="noopener">${n.title}</a>
      ${n.summary ? `<p class="summary">${n.summary}</p>` : ""}</li>`).join("") || '<li class="muted">공지 없음</li>';
}

function renderMaritime(m) {
  const s = m.series || {};
  const y = s.yanbu_port;
  if (!y) return fillTile("tile-maritime", { value: "–", sub: `수집 실패: ${m.error || ""}`, labels: [], values: [], type: "line" });
  fillTile("tile-maritime", {
    value: pct(y),
    sev: dropSeverity(y.ratio),
    sub: `7일 ${y.last7}척 (평시 ${Math.round(y.baseline7)}) · 제다항 ${pct(s.jeddah_port)} · 밥엘만데브 ${pct(s.bab_el_mandeb)} · ${y.last_date} 기준${staleTag(m)}`,
    labels: y.spark.map((p) => p.date),
    values: y.spark.map((p) => p.value),
    type: "line",
  });
}

function renderNews(news) {
  for (const key of ["kr", "en"]) {
    const list = document.getElementById(`news-${key}`);
    const items = news[key] || [];
    list.innerHTML = items.map((n) => `
      <li><div class="notice-date">${n.date} · ${n.source}</div>
        <a href="${n.url}" target="_blank" rel="noopener">${n.title}</a></li>`).join("")
      || `<li class="muted">${news.error ? "수집 실패" : "해당 없음"}</li>`;
  }
}

function renderEvents(ev) {
  const log = document.getElementById("event-log");
  const events = ev.events || [];
  log.innerHTML = events.map((e) => `
    <li class="${e.local ? "local" : ""}">
      <span class="ev-time">${e.date.slice(5)} ${e.time}</span>
      <span class="ev-city">${e.city}</span>
      <span class="ev-type ${TYPE_STYLE[e.type]?.cls || ""}">${e.type}</span>
      <a href="${e.url}" target="_blank" rel="noopener">${e.title}</a>
      <span class="ev-meta">${e.source}${e.outlets > 1 ? ` 외 ${e.outlets - 1}` : ""}</span>
    </li>`).join("") || `<li class="muted">${ev.error ? "수집 실패" : "최근 72시간 해당 보도 없음"}</li>`;

  const houthi = ev.houthi || [];
  document.getElementById("houthi-list").innerHTML = houthi.map((h) =>
    `<li><a href="${h.url}" target="_blank" rel="noopener">${h.title}</a></li>`).join("") || '<li class="muted">없음</li>';
}

// ---------------------------------------------------------------- map

function renderMap(data) {
  const map = L.map("map", { scrollWheelZoom: false }).setView([24.2, 44.0], 5);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: "&copy; OpenStreetMap &copy; CARTO", maxZoom: 11,
  }).addTo(map);

  const places = data.mofa?.places || [];
  const events = (data.events?.events || []).filter((e) => e.lat);
  const series = data.maritime?.series || {};
  const portOf = (p) => series[{ port570: "yanbu_port", port518: "jeddah_port" }[p.port] || p.port];

  // 1) 외교부 경보 도시
  const advisoryLayer = L.layerGroup();
  places.forEach((p) => {
    const s = styleOf(p.level);
    const port = portOf(p);
    const here = events.filter((e) => e.city === p.name);
    const marker = L.circleMarker([p.lat, p.lon], {
      radius: p.local ? 9 : 7, color: p.local ? "#fff" : s.color, weight: p.local ? 2 : 1,
      fillColor: s.color, fillOpacity: 0.9, dashArray: s.dashed ? "3 3" : null,
    });
    marker.bindTooltip(p.name, { permanent: p.local || p.level >= 3, direction: "right", offset: [8, 0], className: "place-label" });
    marker.bindPopup(
      `<b>${p.name}</b><br>외교부 ${s.label}` +
      (port ? `<br>항만 7일 입항 ${port.last7}척 · 평시 ${Math.round(port.baseline7)}척 (${pct(port)}) · ${port.last_date}` : "") +
      (here.length ? `<br>최근 72시간 사건 ${here.length}건` : "")
    );
    advisoryLayer.addLayer(marker);
  });

  // 2) 공격·요격·경보 이벤트 — 같은 도시는 원형으로 살짝 벌려 겹치지 않게
  const eventLayer = L.layerGroup();
  const perCity = {};
  events.forEach((e) => {
    const k = (perCity[e.city] = (perCity[e.city] || 0) + 1);
    const ang = k * 2.1, r = 0.28;
    const ts = TYPE_STYLE[e.type] || { color: "#8a97a8" };
    L.circleMarker([e.lat + r * Math.sin(ang), e.lon + r * Math.cos(ang)], {
      radius: 6 + 2 * Math.log2(e.outlets), color: "#0f1720", weight: 1, fillColor: ts.color, fillOpacity: 0.95,
    })
      .bindPopup(`<span class="ev-type ${TYPE_STYLE[e.type]?.cls || ""}">${e.type}</span> <b>${e.city}</b> · ${e.date} ${e.time}<br>` +
        `<a href="${e.url}" target="_blank" rel="noopener">${e.title}</a><br><small>${e.source}${e.outlets > 1 ? ` 외 ${e.outlets - 1}개 매체` : ""}</small>`)
      .addTo(eventLayer);
  });

  // 3) 위성 이상 화점 (전국, 7일)
  const hotspots = data.firms?.hotspots || [];
  const newest = hotspots.at(-1)?.date;
  const hotspotLayer = L.layerGroup();
  hotspots.forEach((h) => {
    const ageDays = newest ? (new Date(newest) - new Date(h.date)) / 864e5 : 0;
    L.circleMarker([h.lat, h.lon], {
      radius: 3 + Math.sqrt(h.frp), color: "#ff7a1a", fillColor: "#ff4d1a", weight: 1,
      fillOpacity: Math.max(0.15, 0.85 - ageDays * 0.12), opacity: Math.max(0.3, 1 - ageDays * 0.1),
    }).bindTooltip(`${h.date} ${h.time.padStart(4, "0")} UTC · FRP ${h.frp} · ${h.confidence}`).addTo(hotspotLayer);
  });

  // 4) 상시 플레어
  const flareLayer = L.layerGroup();
  (data.firms?.flare_sites || []).forEach((f) => {
    L.circleMarker([f.lat, f.lon], { radius: 5, color: "#8a97a8", fillColor: "#8a97a8", weight: 1, fillOpacity: 0.5 })
      .bindTooltip(`상시 열원 (7일 중 ${f.days}일) · 정유·가스 플레어 추정`).addTo(flareLayer);
  });

  // 5) 항만 활동 — 평시 대비 링
  const portLayer = L.layerGroup();
  places.filter((p) => portOf(p)).forEach((p) => {
    const port = portOf(p);
    L.circle([p.lat, p.lon], { radius: 28000, color: SEV_COLOR[dropSeverity(port.ratio)], weight: 3, fill: false, opacity: 0.9 })
      .bindTooltip(`${port.name} · 7일 ${port.last7}척 / 평시 ${Math.round(port.baseline7)}척 = ${pct(port)}`)
      .addTo(portLayer);
  });

  advisoryLayer.addTo(map); eventLayer.addTo(map); hotspotLayer.addTo(map); portLayer.addTo(map);
  L.control.layers(null, {
    "외교부 경보 도시": advisoryLayer,
    "공격·요격·경보 (72h)": eventLayer,
    "위성 이상 화점 (7일)": hotspotLayer,
    "항만 활동 (평시 대비)": portLayer,
    "상시 플레어": flareLayer,
  }, { collapsed: false }).addTo(map);

  const present = [...new Set(places.map((p) => p.level).filter(Boolean))].sort();
  document.getElementById("legend").innerHTML =
    present.map((l) => `<li><span class="dot ${styleOf(l).cls}"></span>${styleOf(l).label}</li>`).join("") +
    Object.entries(TYPE_STYLE).map(([k, v]) => `<li><span class="dot" style="background:${v.color}"></span>${k}</li>`).join("") +
    `<li><span class="dot" style="background:#ff4d1a"></span>이상 화점</li>` +
    `<li><span class="ring" style="border-color:${SEV_COLOR.calm}"></span>항만 정상 · <span class="ring" style="border-color:${SEV_COLOR.warm}"></span>둔화 · <span class="ring" style="border-color:${SEV_COLOR.hot}"></span>급감</li>`;
}

async function main() {
  try {
    const res = await fetch("data/latest.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`data/latest.json ${res.status}`);
    const data = await res.json();
    renderAttention(data.attention || {});
    renderFirms(data.firms || {});
    renderMofa(data.mofa || {});
    renderNews(data.news || {});
    renderMaritime(data.maritime || {});
    renderEvents(data.events || {});
    renderMap(data);
    document.getElementById("last-updated").textContent =
      `마지막 업데이트: ${new Date(data.generated_at).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" })}`;
  } catch (err) {
    document.getElementById("mofa-line").textContent = "데이터 로드 실패";
    console.error(err);
  }
}

main();
