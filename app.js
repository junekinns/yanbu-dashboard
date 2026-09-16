// 외교부 해외안전여행 지도와 같은 색 체계
const LEVEL_STYLE = {
  1: { cls: "level-1", color: "#1f5fbf", label: "1단계 여행유의" },
  2: { cls: "level-2", color: "#e0b83a", label: "2단계 여행자제" },
  2.5: { cls: "level-special", color: "#d9534f", label: "특별여행주의보", dashed: true },
  3: { cls: "level-3", color: "#c0392b", label: "3단계 출국권고" },
  4: { cls: "level-4", color: "#222", label: "4단계 여행금지" },
};
const styleOf = (level) => LEVEL_STYLE[level] || { cls: "level-unknown", color: "#8a97a8", label: "정보 없음" };

const severity = (ratio) => (ratio == null ? "" : ratio >= 3 ? "hot" : ratio >= 1.5 ? "warm" : "calm");
const staleTag = (src) => (src?.stale ? " (이전 값)" : "");

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
  const color = { hot: "#e5533d", warm: "#e0b83a", calm: "#3fa66b", "": "#8a97a8" }[level];
  sparkline(tile.querySelector("canvas"), labels, values, type, color);
}

// 해상 교통은 낮을수록 위험: 평시의 1/3 이하면 hot, 2/3 이하면 warm
const dropSeverity = (ratio) => (ratio == null ? "" : ratio <= 0.34 ? "hot" : ratio <= 0.67 ? "warm" : "calm");

function renderMaritime(m) {
  const s = m.series || {};
  const y = s.yanbu_port;
  if (!y) return fillTile("tile-maritime", { value: "–", sub: `수집 실패: ${m.error || ""}`, labels: [], values: [], type: "line" });
  const pct = (x) => (x?.ratio != null ? `${Math.round(x.ratio * 100)}%` : "–");
  fillTile("tile-maritime", {
    value: pct(y),
    sev: dropSeverity(y.ratio),
    sub: `7일 ${y.last7}척 (평시 ${Math.round(y.baseline7)}) · 제다항 ${pct(s.jeddah_port)} · 밥엘만데브 ${pct(s.bab_el_mandeb)} · ${y.last_date} 기준${staleTag(m)}`,
    labels: y.spark.map((p) => p.date),
    values: y.spark.map((p) => p.value),
    type: "line",
  });
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

function renderMap(data) {
  const map = L.map("map", { scrollWheelZoom: false }).setView([23.0, 39.3], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap", maxZoom: 10 }).addTo(map);

  (data.mofa?.regions || []).forEach((r) => {
    const s = styleOf(r.level);
    L.circle([r.lat, r.lon], { radius: 60000, color: s.color, weight: 2, dashArray: s.dashed ? "6 6" : null, fillColor: s.color, fillOpacity: 0.12 })
      .addTo(map).bindTooltip(`${r.name} · ${s.label}`, { permanent: true, direction: "top" });
  });

  const hotspots = data.firms?.hotspots || [];
  const newest = hotspots.at(-1)?.date;
  hotspots.filter((h) => !h.persistent).forEach((h) => {
    const ageDays = newest ? (new Date(newest) - new Date(h.date)) / 864e5 : 0;
    L.circleMarker([h.lat, h.lon], {
      radius: 3 + Math.sqrt(h.frp),
      color: "#ff7a1a", fillColor: "#ff4d1a", weight: 1,
      fillOpacity: Math.max(0.15, 0.85 - ageDays * 0.12), opacity: Math.max(0.3, 1 - ageDays * 0.1),
    }).addTo(map).bindTooltip(`${h.date} ${h.time.padStart(4, "0")} UTC · FRP ${h.frp} · ${h.confidence}`);
  });
  (data.firms?.flare_sites || []).forEach((f) => {
    L.circleMarker([f.lat, f.lon], { radius: 6, color: "#8a97a8", fillColor: "#8a97a8", weight: 1, fillOpacity: 0.5 })
      .addTo(map).bindTooltip(`상시 열원 (7일 중 ${f.days}일 감지) · 정유 플레어 추정`);
  });

  document.getElementById("legend").innerHTML =
    `<li><span class="dot" style="background:#ff4d1a"></span>이상 화점 (평소엔 없던 불)</li>` +
    `<li><span class="dot" style="background:#8a97a8"></span>상시 열원 (정유 플레어 추정)</li>` +
    Object.values(LEVEL_STYLE).map((s) => `<li><span class="dot ${s.cls}"></span>${s.label}</li>`).join("");
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

const TYPE_CLASS = { 경보: "t-alert", 요격: "t-intercept", 피격: "t-hit", 공습: "t-airstrike" };

function renderEvents(ev) {
  const log = document.getElementById("event-log");
  const events = ev.events || [];
  log.innerHTML = events.map((e) => `
    <li class="${e.local ? "local" : ""}">
      <span class="ev-time">${e.date.slice(5)} ${e.time}</span>
      <span class="ev-city">${e.city}</span>
      <span class="ev-type ${TYPE_CLASS[e.type] || ""}">${e.type}</span>
      <a href="${e.url}" target="_blank" rel="noopener">${e.title}</a>
      <span class="ev-meta">${e.source}${e.outlets > 1 ? ` 외 ${e.outlets - 1}` : ""}</span>
    </li>`).join("") || `<li class="muted">${ev.error ? "수집 실패" : "최근 72시간 해당 보도 없음"}</li>`;

  const houthi = ev.houthi || [];
  document.getElementById("houthi-list").innerHTML = houthi.map((h) =>
    `<li><a href="${h.url}" target="_blank" rel="noopener">${h.title}</a></li>`).join("") || '<li class="muted">없음</li>';
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
