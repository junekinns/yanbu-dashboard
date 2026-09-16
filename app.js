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
// 서버가 계산해 보내는 3단계 배지 라벨 → 색
const TIER_COLOR = {
  위험: "#e5533d", 급증: "#e5533d", 끊김: "#e5533d",
  주의: "#e0b83a", 증가: "#e0b83a", 감소: "#e0b83a",
  평시: "#3fa66b", 정상: "#3fa66b",
};
const tierClass = (label) => ({ 위험: "hot", 급증: "hot", 끊김: "hot", 주의: "warm", 증가: "warm", 감소: "warm", 평시: "calm", 정상: "calm" }[label] || "");
const staleTag = (src) => {
  if (!src?.stale) return "";
  if (!src.last_ok_at) return " (이전 값)";
  const hours = (Date.now() - Date.parse(src.last_ok_at)) / 3600e3;
  if (hours < 1) return " (1시간 이내 값)";
  return hours < 48 ? ` (${Math.round(hours)}시간 전 값)` : ` (${Math.round(hours / 24)}일 전 값)`;
};
const failed = (src) => ({ sub: "수집 실패 — 다음 갱신 때 재시도", title: src?.error || "" });
const pct = (x) => (x?.ratio != null ? `${Math.round(x.ratio * 100)}%` : "–");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const state = { data: null, hours: 72, base: "dark", map: null, layer: null, baseLayers: {}, charts: {} };
const REGION_KEYS = ["west", "central", "east"];
const regionName = (key) => state.data.regions.find((r) => r.key === key)?.name || "기타";
const regionCls = (key) => (REGION_KEYS.includes(key) ? `region-${key}` : "region-other");
const regionBadge = (key) => `<span class="region-badge ${regionCls(key)}">${esc(regionName(key))}</span>`;

// ---------------------------------------------------------------- tiles

function sparkline(tile, labels, values, type, color) {
  const canvas = tile.querySelector("canvas");
  state.charts[tile.id]?.destroy();
  state.charts[tile.id] = new Chart(canvas, {
    type,
    data: { labels, datasets: [{ data: values, borderColor: color, backgroundColor: color, borderWidth: 2, pointRadius: 0, tension: 0.3, fill: false }] },
    options: {
      animation: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { title: (items) => labels[items[0].dataIndex] } } },
      scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
    },
  });
}

function fillTile(id, { tier, sub, title = "", labels = [], values = [], type = "line" }) {
  const tile = document.getElementById(id);
  const badge = document.getElementById(`badge-${id.replace("tile-", "")}`);
  badge.textContent = tier || "–";
  tile.querySelector(".sub").textContent = sub;
  tile.title = title;
  tile.classList.remove("hot", "warm", "calm");
  const cls = tierClass(tier);
  if (cls) tile.classList.add(cls);
  sparkline(tile, labels, values, type, TIER_COLOR[tier] || "#8a97a8");
}

function renderMofaTile() {
  const m = state.data.mofa || {};
  fillTile("tile-mofa", m.weekly_counts ? {
    tier: m.tier,
    sub: `전국 최근 7일 ${m.last7d}건 (평시 ${m.baseline}건)${staleTag(m)}`,
    labels: m.weekly_counts.map((w) => w.week), values: m.weekly_counts.map((w) => w.count), type: "bar",
  } : failed(m));
}

function renderFlightsTile() {
  const fl = state.data.flights || {};
  const hist = Object.entries(fl.history || {}).sort(([a], [b]) => a.localeCompare(b));
  const baseline = fl.baseline != null ? `평시 ${fl.baseline}대` : `같은 시각 기록 ${fl.baseline_n ?? 0}/3 수집 중`;
  fillTile("tile-flights", fl.count != null ? {
    tier: fl.tier,
    sub: `홍해 회랑 상공 현재 ${fl.count}대 (${baseline})${staleTag(fl)}`,
    labels: hist.map(([k]) => k.slice(5)), values: hist.map(([, v]) => v),
  } : failed(fl));
}

function renderRegionTiles() {
  const d = state.data;
  const container = document.getElementById("region-tiles");
  container.innerHTML = d.regions.map((r) => `
    <div class="region-group">
      <h2 class="region-heading">${esc(r.name)} <small>${esc(r.label)}</small></h2>
      <div class="tiles region-tile-row">
        <article class="card tile" id="tile-firms-${r.key}">
          <h3>위성 열 감지</h3>
          <div class="badge" id="badge-firms-${r.key}">–</div>
          <p class="sub"></p>
          <canvas height="48"></canvas>
        </article>
        <article class="card tile" id="tile-maritime-${r.key}">
          <h3>${r.primary_port ? "해상 교통" : "해상 교통 · 호르무즈(전국 수출 회랑)"}</h3>
          <div class="badge" id="badge-maritime-${r.key}">–</div>
          <p class="sub"></p>
          <canvas height="48"></canvas>
        </article>
      </div>
    </div>`).join("");

  d.regions.forEach((r) => {
    const fr = (d.firms?.regions || {})[r.key];
    fillTile(`tile-firms-${r.key}`, fr ? {
      tier: fr.tier,
      sub: `최근 24h ${fr.last24h}건 (${fr.baseline != null ? `평시 ${fr.baseline}건` : "평시 수집 중"}) · 상시 플레어 ${fr.flares24h}건 제외${staleTag(d.firms)}`,
      labels: fr.daily_counts.map((x) => x.date), values: fr.daily_counts.map((x) => x.count), type: "bar",
    } : failed(d.firms));

    const series = d.maritime?.series || {};
    const port = (r.primary_port && series[r.primary_port]) || series[r.chokepoint];
    fillTile(`tile-maritime-${r.key}`, port ? {
      tier: port.tier,
      sub: `${port.name} 최근 7일 ${port.last7}척 (평시 ${Math.round(port.baseline7)}척, ${pct(port)}) · ${port.last_date} 기준${staleTag(d.maritime)}`,
      labels: port.spark.map((p) => p.date), values: port.spark.map((p) => p.value),
    } : failed(d.maritime));
  });
}

// ---------------------------------------------------------------- header / lists

const levelDot = (p) => `<span class="dot ${styleOf(p.level).cls}"></span>${esc(p.name)} <strong>${styleOf(p.level).label}</strong>`;

function renderHeader() {
  const m = state.data.mofa || {};
  const line = document.getElementById("mofa-line");
  const places = m.places || [];
  if (!places.length) {
    line.textContent = "외교부 데이터 수집 실패";
  } else {
    // 3단계(출국권고) 이상만 권역별로 나열하고, 그 외 지역의 기본 단계는 전국 최빈값 하나로 한 번만.
    const high = places.filter((p) => p.level >= 3);
    const groups = [...state.data.regions.map((r) => r.key), null]
      .map((key) => ({ key, items: high.filter((p) => (p.region || null) === key) }))
      .filter((g) => g.items.length)
      .map((g) => `${regionBadge(g.key)} ${g.items.map(levelDot).join(" · ")}`);
    const counts = {};
    places.filter((p) => !(p.level >= 3) && p.level).forEach((p) => { counts[p.level] = (counts[p.level] || 0) + 1; });
    const mode = Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0];
    const rest = mode ? `<span class="dot ${styleOf(mode).cls}"></span>그 외 전 지역 <strong>${styleOf(mode).label}</strong>` : "";
    line.innerHTML = "외교부 경보 · " + [...groups, rest].filter(Boolean).join(" · ") + staleTag(m);
  }

  document.getElementById("notice-list").innerHTML = (m.notices || []).map((n) => `
    <li><div class="notice-date">${n.date}</div>
      <a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a>
      ${n.summary ? `<p class="summary">${esc(n.summary)}</p>` : ""}</li>`).join("") || '<li class="muted">공지 없음</li>';
}

function renderEvents() {
  const ev = state.data.events || {};
  const since = Date.now() - 72 * 3600e3;
  const events = (ev.events || []).filter((e) => new Date(e.iso) >= since);
  document.getElementById("event-log").innerHTML = events.map((e) => `
    <li>
      <span class="ev-time">${e.date.slice(5)} ${e.time}</span>
      ${regionBadge(e.region)}
      <span class="ev-city">${esc(e.city)}</span>
      <span class="ev-type ${TYPE_STYLE[e.type]?.cls || ""}">${e.type}</span>
      <a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a>
      <span class="ev-meta">${esc(e.source)}${e.outlets > 1 ? ` 외 ${e.outlets - 1}` : ""}</span>
    </li>`).join("") || `<li class="muted">${ev.error ? "수집 실패" : "최근 72시간 해당 보도 없음"}</li>`;
}

function renderTelegram() {
  const tg = state.data.telegram || {};
  const cityRegion = {};
  (state.data.mofa?.places || []).forEach((p) => { cityRegion[p.name] = p.region; });
  document.getElementById("telegram-list").innerHTML = (tg.messages || []).map((msg) => {
    const regions = [...new Set(msg.places.map((p) => cityRegion[p] || null))];
    return `
    <li>
      <div class="tg-head"><span class="ev-time">${msg.time}</span>
        ${regions.map(regionBadge).join("")}
        ${msg.places.map((p) => `<span class="place-badge">${esc(p)}</span>`).join("")}
        <a class="tg-link" href="${esc(msg.url)}" target="_blank" rel="noopener">채널에서 보기</a></div>
      <p class="tg-text">${msg.text_ko ? esc(msg.text_ko) : '<span class="muted">번역 실패 — 아래 원문 참고</span>'}</p>
      <details class="tg-original">
        <summary>아랍어 원문${msg.text_ko ? "" : " (번역 없음)"}</summary>
        <p class="tg-text" dir="rtl" lang="ar">${esc(msg.text_ar)}</p>
      </details>
    </li>`;
  }).join("") || `<li class="muted">${tg.error ? "수집 실패" : "최근 메시지 중 사우디 언급 없음"}</li>`;
}

function renderNews() {
  const news = state.data.news || {};
  for (const key of ["kr", "en"]) {
    document.getElementById(`news-${key}`).innerHTML = (news[key] || []).map((n) => `
      <li><div class="notice-date">${n.date} · ${esc(n.source)}</div>
        <a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a></li>`).join("")
      || `<li class="muted">${news.error ? "수집 실패" : "해당 없음"}</li>`;
  }
}

// ---------------------------------------------------------------- map

function combinedBounds(regions, places) {
  const bounds = L.latLngBounds();
  regions.forEach((r) => { bounds.extend([r.box[0], r.box[2]]); bounds.extend([r.box[1], r.box[3]]); });
  places.forEach((p) => { if (p.lat != null && p.lon != null) bounds.extend([p.lat, p.lon]); });
  return bounds;
}

function renderMap() {
  const d = state.data;
  if (!state.map) {
    state.map = L.map("map", { scrollWheelZoom: false });
    state.baseLayers.dark = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { attribution: "&copy; OpenStreetMap &copy; CARTO", maxZoom: 11 }).addTo(state.map);
    state.baseLayers.sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "Esri World Imagery", maxZoom: 18 });
    state.map.fitBounds(combinedBounds(d.regions, d.mofa?.places || []), { padding: [16, 16] });
  }
  state.layer?.remove();
  state.layer = L.layerGroup().addTo(state.map);

  const since = Date.now() - state.hours * 3600e3;
  const events = (d.events?.events || []).filter((e) => e.lat && new Date(e.iso) >= since);
  const hotspots = Object.values(d.firms?.regions || {})
    .flatMap((fr) => fr.hotspots || [])
    .filter((h) => new Date(`${h.date}T${h.time.padStart(4, "0").replace(/(\d\d)(\d\d)/, "$1:$2")}:00Z`) >= since);

  // 위성 이상 화점 — 클수록 화력, 옅을수록 오래된 것
  hotspots.forEach((h) => {
    const age = (Date.now() - new Date(`${h.date}T00:00:00Z`)) / 864e5;
    L.circleMarker([h.lat, h.lon], { radius: 3 + Math.sqrt(h.frp), color: "#ff7a1a", fillColor: "#ff4d1a", weight: 1,
      fillOpacity: Math.max(0.2, 0.85 - age * 0.1), opacity: Math.max(0.35, 1 - age * 0.1) })
      .bindTooltip(`위성 화점 · ${h.date} ${h.time.padStart(4, "0")} UTC · FRP ${h.frp}`).addTo(state.layer);
  });

  // 도시 — 외교부 단계 색, 항만 활동은 팝업에
  const series = d.maritime?.series || {};
  (d.mofa?.places || []).forEach((p) => {
    const s = styleOf(p.level), port = p.port && series[p.port];
    const here = events.filter((e) => e.city === p.name).length;
    L.circleMarker([p.lat, p.lon], { radius: 8, color: "#fff", weight: 1.5, fillColor: s.color, fillOpacity: 0.95, dashArray: s.dashed ? "3 3" : null })
      .bindTooltip(p.name, { permanent: true, direction: "right", offset: [8, 0], className: "place-label" })
      .bindPopup(`<b>${esc(p.name)}</b> · ${esc(regionName(p.region))}<br>외교부 ${s.label}` +
        (port ? `<br>${esc(port.name)} 7일 입항 ${port.last7}척 · 평시 ${Math.round(port.baseline7)}척 (${pct(port)})` : "") +
        (here ? `<br>최근 ${state.hours}시간 사건 ${here}건` : ""))
      .addTo(state.layer);
  });

  // 사건 — 같은 도시는 원형으로 살짝 벌려 겹치지 않게. 6시간 이내는 pulse 애니메이션으로 강조.
  const perCity = {};
  events.forEach((e) => {
    const k = (perCity[e.city] = (perCity[e.city] || 0) + 1), ang = k * 2.1, rr = 0.12;
    const ts = TYPE_STYLE[e.type] || { color: "#8a97a8" };
    const isRecent = Date.now() - new Date(e.iso) < 6 * 3600e3;
    L.circleMarker([e.lat + rr * Math.sin(ang), e.lon + rr * Math.cos(ang)], {
      radius: 6 + 2 * Math.log2(e.outlets), color: "#0f1720", weight: 1, fillColor: ts.color, fillOpacity: 0.95,
      className: isRecent ? "pulse-marker" : "",
    })
      .bindPopup(`<span class="ev-type ${ts.cls || ""}">${e.type}</span> <b>${esc(e.city)}</b> · ${e.date} ${e.time}<br>` +
        `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a><br><small>${esc(e.source)}${e.outlets > 1 ? ` 외 ${e.outlets - 1}개 매체` : ""}</small>`)
      .addTo(state.layer);
  });

  const present = [...new Set((d.mofa?.places || []).map((p) => p.level).filter(Boolean))].sort();
  document.getElementById("legend").innerHTML =
    present.map((l) => `<li><span class="dot ${styleOf(l).cls}"></span>${styleOf(l).label}</li>`).join("") +
    Object.entries(TYPE_STYLE).map(([k, v]) => `<li><span class="dot" style="background:${v.color}"></span>${k}</li>`).join("") +
    `<li><span class="dot" style="background:#ff4d1a"></span>위성 이상 화점</li>` +
    `<li class="muted">${state.hours}시간 내 · 사건 ${events.length}건 · 화점 ${hotspots.length}건</li>`;
}

// ---------------------------------------------------------------- shell

function renderAll() {
  renderHeader(); renderMofaTile(); renderFlightsTile(); renderRegionTiles(); renderEvents(); renderTelegram(); renderMap();
}

document.getElementById("range-tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-hours]");
  if (!btn) return;
  state.hours = Number(btn.dataset.hours);
  document.querySelectorAll("#range-tabs button").forEach((b) => b.classList.toggle("on", b === btn));
  renderMap();
});
document.getElementById("basemap-tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-base]");
  if (!btn || btn.dataset.base === state.base) return;
  state.baseLayers[state.base]?.remove();
  state.base = btn.dataset.base;
  state.baseLayers[state.base]?.addTo(state.map).bringToBack();
  document.querySelectorAll("#basemap-tabs button").forEach((b) => b.classList.toggle("on", b === btn));
});

const refreshBtn = document.getElementById("refresh-btn");
refreshBtn.addEventListener("click", async () => {
  const status = document.getElementById("refresh-status");
  refreshBtn.disabled = true;
  status.textContent = "확인 중...";
  try {
    const res = await fetch(`data/latest.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(String(res.status));
    const fresh = await res.json();
    const changed = fresh.generated_at !== state.data?.generated_at;
    state.data = fresh;
    renderAll();
    renderNews();
    setLastUpdated(fresh.generated_at);
    status.textContent = changed ? "새 데이터로 갱신했습니다" : "이미 최신입니다 (다음 자동 수집까지 대기)";
  } catch {
    status.textContent = "새로고침 실패 — 잠시 후 다시 시도";
  } finally {
    refreshBtn.disabled = false;
    setTimeout(() => { status.textContent = ""; }, 6000);
  }
});

function setLastUpdated(iso) {
  // 사건·채널 시각이 사우디 현지라 여기도 맞춘다. 한국 가족의 브라우저에서도 같은 값이 보이도록 시간대를 고정.
  document.getElementById("last-updated").textContent =
    `마지막 업데이트: ${new Date(iso).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Riyadh" })} (사우디 현지)`;
}

async function main() {
  try {
    const res = await fetch("data/latest.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`data/latest.json ${res.status}`);
    state.data = await res.json();
    renderAll();
    renderNews();
    setLastUpdated(state.data.generated_at);
  } catch (err) {
    document.getElementById("mofa-line").textContent = "데이터 로드 실패";
    console.error(err);
  }
}

main();
