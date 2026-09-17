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
const TYPES = Object.keys(TYPE_STYLE);
const TIER_COLOR = { 끊김: "#e5533d", 감소: "#e0b83a", 정상: "#3fa66b" };
const tierClass = (label) => ({ 끊김: "hot", 감소: "warm", 정상: "calm" }[label] || "");
const staleTag = (src) => {
  if (!src?.stale) return "";
  if (!src.last_ok_at) return " (이전 값)";
  const hours = (Date.now() - Date.parse(src.last_ok_at)) / 3600e3;
  if (hours < 1) return " (1시간 이내 값)";
  return hours < 48 ? ` (${Math.round(hours)}시간 전 값)` : ` (${Math.round(hours / 24)}일 전 값)`;
};
const failed = (src) => ({ sub: "수집 실패 — 다음 갱신 때 재시도", title: src?.error || "" });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtMD = (iso) => {
  const [, m, d] = new Date(iso).toLocaleDateString("en-CA", { timeZone: "Asia/Riyadh" }).split("-");
  return `${+m}/${+d}`;
};

const state = { data: null, hours: 72, base: "dark", map: null, layer: null, baseLayers: {}, charts: {}, markers: {} };

// ---------------------------------------------------------------- 도시 행

function cityRows() {
  const d = state.data, m = d.mofa || {}, tempo = d.events?.tempo || {}, mentions = d.telegram?.mentions7d || {};
  const cutoff = Date.now() - 30 * 864e5, pinned = new Set(d.summary?.pinned || []);
  const latestChange = {};
  (m.changes || []).forEach((c) => { if (Date.parse(c.at) >= cutoff && !latestChange[c.city]) latestChange[c.city] = c; });
  return (m.places || []).map((p) => {
    const t = tempo[p.name] || { "7d": {}, total7d: 0, prev7d: null, prev_total: null };
    const row = { ...p, tempo: t, mentions: mentions[p.name] || 0, change: latestChange[p.name] || null };
    row.shown = pinned.has(p.name) || t.total7d > 0 || row.mentions > 0 || !!row.change;
    return row;
  }).sort((a, b) => (b.level || 0) - (a.level || 0) || b.tempo.total7d - a.tempo.total7d || a.name.localeCompare(b.name, "ko"));
}

// ---------------------------------------------------------------- 위기 단계 · 헤드라인

function renderCrisis() {
  const s = state.data.summary, el = document.getElementById("crisis");
  if (!s || s.level == null) { el.className = "crisis"; el.innerHTML = ""; return; }
  const hist = Object.entries(s.history || {}).slice(-7);
  el.className = `crisis lv${s.level}`;
  el.innerHTML = `
    <div class="crisis-num">${s.level}</div>
    <div class="crisis-body">
      <div class="crisis-label"><strong>${esc(s.label)}</strong> <span class="muted">${s.level}/5 · 자체 기준${s.stale ? " · 계산 실패, 이전 값" : ""}</span></div>
      <div class="crisis-why">${(s.reasons || []).map((r) => `<span>${esc(r)}</span>`).join("") || `<span class="muted">점수를 낸 신호 없음</span>`}</div>
      <div class="crisis-strip">${hist.map(([d, l]) => `<span class="lv${l}" title="${d}">${l}</span>`).join("")}</div>
    </div>`;
}

function renderHeadline() {
  const m = state.data.mofa || {}, el = document.getElementById("headline");
  if (!(m.places || []).length) { el.innerHTML = `<p>외교부 데이터 수집 실패${staleTag(m)}</p>`; return; }
  const high = cityRows().filter((p) => p.level >= 3);
  const recent = (m.changes || []).filter((c) => Date.now() - Date.parse(c.at) < 30 * 864e5).slice(0, 2);
  const parts = [
    high.length ? `<span class="dot level-3"></span><strong>출국권고 ${high.length}곳</strong> <span class="muted">${high.map((p) => esc(p.name)).join(" · ")}</span>` : "출국권고 없음",
    recent.length ? `<strong>단계 변경</strong> ` + recent.map((c) => `${esc(c.city)} → ${esc(c.to_name || c.to)} (${fmtMD(c.at)})`).join(", ") : `30일 내 단계 변경 없음`,
    m.last7d != null ? `이번 주 공지 <strong>${m.last7d}건</strong> <span class="muted">(평시 ${m.baseline})</span>` : "",
  ].filter(Boolean);
  el.innerHTML = `<p>${parts.join(" · ")}${staleTag(m)}</p>`;
}

// ---------------------------------------------------------------- 도시 현황표

function renderCityTable() {
  const ev = state.data.events || {};
  const rows = cityRows().filter((p) => p.shown), compare = (ev.history_days || 0) >= 14;
  const zero = `<span class="zero">—</span>`;
  const cell = (n, type) => (n ? `<span class="ev-type ${TYPE_STYLE[type].cls}">${n}</span>` : zero);
  const delta = (t) => {
    if (!compare || t.prev_total == null) return zero;
    const diff = t.total7d - t.prev_total;
    return diff > 0 ? `<span class="up">▲ +${diff}</span>` : diff < 0 ? `<span class="down">▼ ${diff}</span>` : `<span class="flat">=</span>`;
  };
  document.querySelector("#city-table tbody").innerHTML = rows.map((p) => `
    <tr data-city="${esc(p.name)}">
      <td class="col-city"><button type="button" class="city-link">${esc(p.name)}</button></td>
      <td class="col-level"><span class="dot ${styleOf(p.level).cls}"></span>${styleOf(p.level).label}${p.change
        ? ` <span class="chg" title="${esc(p.change.from_name || p.change.from)} → ${esc(p.change.to_name || p.change.to)}">▲ ${fmtMD(p.change.at)}</span>` : ""}</td>
      ${TYPES.map((t) => `<td class="col-type num">${cell(p.tempo["7d"][t] || 0, t)}</td>`).join("")}
      <td class="col-total num">${p.tempo.total7d ? `<strong>${p.tempo.total7d}</strong>` : zero}</td>
      <td class="col-delta num">${delta(p.tempo)}</td>
      <td class="col-houthi num">${p.mentions ? `<span class="place-badge">${p.mentions}</span>` : zero}</td>
    </tr>`).join("") || `<tr><td colspan="9" class="muted">외교부 데이터 수집 실패</td></tr>`;
  const note = [];
  if (ev.history_days != null && !compare) note.push(`지난주 대비는 사건 이력 14일부터 (현재 ${ev.history_days}일)`);
  if (ev.stale) note.push(`사건${staleTag(ev).trim()}`);
  document.getElementById("city-note").textContent = note.join(" · ");
}

document.getElementById("city-table").addEventListener("click", (e) => {
  const btn = e.target.closest(".city-link");
  if (!btn) return;
  const marker = state.markers[btn.closest("tr").dataset.city];
  if (!marker) return;
  document.getElementById("map").scrollIntoView({ behavior: "smooth", block: "center" });
  state.map.once("moveend", () => marker.openPopup());
  state.map.flyTo(marker.getLatLng(), 8, { duration: 0.8 });
});

// ---------------------------------------------------------------- 목록

function renderEvents() {
  const ev = state.data.events || {};
  const since = Date.now() - 72 * 3600e3;
  const events = (ev.events || []).filter((e) => new Date(e.iso) >= since);
  document.getElementById("event-log").innerHTML = events.map((e) => `
    <li>
      <span class="ev-time">${e.date.slice(5)} ${e.time}</span>
      <span class="ev-city">${esc(e.city)}</span>
      <span class="ev-type ${TYPE_STYLE[e.type]?.cls || ""}">${e.type}${e.weapon ? ` · ${esc(e.weapon)}` : ""}</span>
      <a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a>
      <span class="ev-meta">${esc(e.source)}${e.outlets > 1 ? ` 외 ${e.outlets - 1}` : ""}</span>
    </li>`).join("") || `<li class="muted">72시간 내 보도 없음${staleTag(ev)}</li>`;
}

function renderTelegram() {
  const tg = state.data.telegram || {};
  const mentions = Object.entries(tg.mentions7d || {});
  document.getElementById("tg-mentions").innerHTML =
    `<span class="muted small">7일 표적 언급</span> ` +
    (mentions.length ? mentions.map(([c, n]) => `<span class="place-badge">${esc(c)} <b>${n}</b></span>`).join(" ") : `<span class="muted">없음</span>`) +
    (tg.stale ? `<span class="muted small">${staleTag(tg)}</span>` : "");
  document.getElementById("telegram-list").innerHTML = (tg.messages || []).slice(0, 5).map((msg) => `
    <li>
      <div class="tg-head"><span class="ev-time">${msg.time}</span>
        ${msg.places.map((p) => `<span class="place-badge">${esc(p)}</span>`).join("")}
        <a class="tg-link" href="${esc(msg.url)}" target="_blank" rel="noopener">원문</a></div>
      <p class="tg-text">${msg.text_ko ? esc(msg.text_ko) : `<span dir="rtl" lang="ar">${esc(msg.text_ar)}</span>`}</p>
    </li>`).join("") || `<li class="muted">최근 사우디 언급 없음</li>`;
}

function renderNotices() {
  const m = state.data.mofa || {};
  document.getElementById("notice-list").innerHTML = (m.notices || []).map((n) => `
    <li><div class="notice-date">${n.date}</div>
      <a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a>
      ${n.summary ? `<p class="summary">${esc(n.summary)}</p>` : ""}</li>`).join("") || '<li class="muted">공지 없음</li>';
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

// ---------------------------------------------------------------- NOTAM (자격증명이 있을 때만 존재)

function renderNotams() {
  const n = state.data.notams;
  document.getElementById("notam")?.remove();
  document.getElementById("src-notam").textContent = "";
  if (!n?.enabled) return;
  const items = n.items || [];
  const sec = document.createElement("section");
  sec.className = "card";
  sec.id = "notam";
  sec.innerHTML = `<h2>공역 NOTAM <span class="muted small">${(n.locations || []).join(" · ")}${staleTag(n)}</span></h2>` +
    (n.ok === false && !n.stale
      ? `<p class="muted" title="${esc(n.error || "")}">수집 실패 — 다음 갱신 때 재시도</p>`
      : items.length
        ? `<ul class="notice-list">${items.map((i) => `<li><div class="notice-date">${esc(i.location)} · ${esc(i.kind)} · ${esc((i.effective_start || "").slice(0, 16))} ~ ${esc((i.effective_end || "").slice(0, 16))}</div><p class="summary">${esc(i.text)}</p></li>`).join("")}</ul>`
        : `<p class="muted">현행 공역 제한 없음</p>`);
  document.getElementById("lab").before(sec);
  document.getElementById("src-notam").innerHTML = ' · <a href="https://api.faa.gov/" target="_blank" rel="noopener">FAA NOTAM</a>';
}

// ---------------------------------------------------------------- 실험 타일

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
  document.getElementById(`badge-${id.replace("tile-", "")}`).textContent = tier || "–";
  tile.querySelector(".sub").textContent = sub;
  tile.title = title;
  tile.classList.remove("hot", "warm", "calm");
  const cls = tierClass(tier);
  if (cls) tile.classList.add(cls);
  sparkline(tile, labels, values, type, TIER_COLOR[tier] || "#8a97a8");
}

function renderFlightsTile() {
  const fl = state.data.flights || {};
  const hist = Object.entries(fl.history || {}).sort(([a], [b]) => a.localeCompare(b));
  const baseline = fl.baseline != null ? `평시 ${fl.baseline}대` : `같은 시각 기록 ${fl.baseline_n ?? 0}/3 수집 중`;
  fillTile("tile-flights", fl.count != null ? {
    tier: fl.tier,
    sub: `현재 ${fl.count}대 (${baseline})${staleTag(fl)}`,
    labels: hist.map(([k]) => k.slice(5)), values: hist.map(([, v]) => v),
  } : failed(fl));
}

// ---------------------------------------------------------------- 지도

// 모양 = 무기(기사 제목에서), 색 = 유형. 궤적은 데이터가 없어 그리지 않는다.
const ICON_SVG = {
  미사일: (c) => `<svg viewBox="0 0 24 24"><path d="M4 20l5-1.5L19 8.5 15.5 5 5.5 15z" fill="${c}"/><path d="M15.5 5l3.5 3.5 2-5.5z" fill="#fff" opacity=".85"/></svg>`,
  드론: (c) => `<svg viewBox="0 0 24 24"><g stroke="${c}" stroke-width="2.2" fill="none"><path d="M6 6l6 6 6-6M6 18l6-6 6 6"/><circle cx="5" cy="5" r="2.6"/><circle cx="19" cy="5" r="2.6"/><circle cx="5" cy="19" r="2.6"/><circle cx="19" cy="19" r="2.6"/></g><circle cx="12" cy="12" r="3" fill="${c}"/></svg>`,
  기타: (c) => `<svg viewBox="0 0 24 24"><path d="M12 2l2.4 6.2L21 7l-4.6 4.6L19 18l-6-3.2L7 18l2.6-6.4L5 7l6.6 1.2z" fill="${c}"/></svg>`,
};
const eventIcon = (e, recent) => L.divIcon({
  className: `ev-icon${recent ? " pulse-marker" : ""}`,
  html: ICON_SVG[e.weapon] ? ICON_SVG[e.weapon]((TYPE_STYLE[e.type] || {}).color || "#8a97a8") : ICON_SVG.기타((TYPE_STYLE[e.type] || {}).color || "#8a97a8"),
  iconSize: [22, 22], iconAnchor: [11, 11], popupAnchor: [0, -10],
});

function placeBounds(places) {
  const bounds = L.latLngBounds();
  places.forEach((p) => { if (p.lat != null && p.lon != null) bounds.extend([p.lat, p.lon]); });
  return bounds;
}

function renderMap() {
  const d = state.data, rows = cityRows();
  if (!state.map) {
    state.map = L.map("map", { scrollWheelZoom: false });
    state.baseLayers.dark = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { attribution: "&copy; OpenStreetMap &copy; CARTO", maxZoom: 11 }).addTo(state.map);
    state.baseLayers.sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "Esri World Imagery", maxZoom: 18 });
    if (rows.length) state.map.fitBounds(placeBounds(rows), { padding: [16, 16] });
    else state.map.setView([24, 45], 5);
  }
  state.layer?.remove();
  state.layer = L.layerGroup().addTo(state.map);
  state.markers = {};

  const since = Date.now() - state.hours * 3600e3;
  const events = (d.events?.events || []).filter((e) => e.lat && new Date(e.iso) >= since);
  const hotspots = (d.firms?.hotspots || [])
    .filter((h) => new Date(`${h.date}T${h.time.padStart(4, "0").replace(/(\d\d)(\d\d)/, "$1:$2")}:00Z`) >= since);

  hotspots.forEach((h) => {
    const age = (Date.now() - new Date(`${h.date}T00:00:00Z`)) / 864e5;
    L.circleMarker([h.lat, h.lon], { radius: 3 + Math.sqrt(h.frp), color: "#ff7a1a", fillColor: "#ff4d1a", weight: 1,
      fillOpacity: Math.max(0.2, 0.85 - age * 0.1), opacity: Math.max(0.35, 1 - age * 0.1) })
      .bindTooltip(`위성 화점 · ${h.date} ${h.time.padStart(4, "0")} UTC · FRP ${h.frp}`).addTo(state.layer);
  });

  // 도시 — 표에 있는 도시만 이름을 붙이고, 나머지는 작은 점
  rows.forEach((p) => {
    const s = styleOf(p.level);
    const marker = L.circleMarker([p.lat, p.lon], { radius: p.shown ? 7 : 4, color: "#fff", weight: p.shown ? 1.5 : 1, fillColor: s.color, fillOpacity: p.shown ? 0.95 : 0.7, dashArray: s.dashed ? "3 3" : null })
      .bindTooltip(p.name, p.shown ? { permanent: true, direction: "right", offset: [8, 0], className: "place-label" } : {})
      .bindPopup(`<b>${esc(p.name)}</b> · ${s.label}` +
        (p.tempo.total7d ? `<br>7일 사건 ${p.tempo.total7d}건` : "") +
        (p.mentions ? `<br>후티 언급 ${p.mentions}회` : ""))
      .addTo(state.layer);
    state.markers[p.name] = marker;
  });

  // 사건 — 같은 도시는 원형으로 살짝 벌려 겹치지 않게. 6시간 이내는 깜빡임.
  const perCity = {};
  events.forEach((e) => {
    const k = (perCity[e.city] = (perCity[e.city] || 0) + 1), ang = k * 2.1, rr = 0.14;
    const isRecent = Date.now() - new Date(e.iso) < 6 * 3600e3;
    L.marker([e.lat + rr * Math.sin(ang), e.lon + rr * Math.cos(ang)], { icon: eventIcon(e, isRecent) })
      .bindPopup(`<span class="ev-type ${TYPE_STYLE[e.type]?.cls || ""}">${e.type}${e.weapon ? ` · ${esc(e.weapon)}` : ""}</span> <b>${esc(e.city)}</b> · ${e.date} ${e.time}<br>` +
        `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a><br><small>${esc(e.source)}${e.outlets > 1 ? ` 외 ${e.outlets - 1}개 매체` : ""}</small>`)
      .addTo(state.layer);
  });

  document.getElementById("legend").innerHTML =
    Object.entries(TYPE_STYLE).map(([k, v]) => `<li><span class="dot" style="background:${v.color}"></span>${k}</li>`).join("") +
    `<li><span class="lg-icon">${ICON_SVG.미사일("#c3ccd8")}</span>미사일 <span class="lg-icon">${ICON_SVG.드론("#c3ccd8")}</span>드론 <span class="lg-icon">${ICON_SVG.기타("#c3ccd8")}</span>기타</li>` +
    `<li><span class="dot" style="background:#ff4d1a"></span>위성 화점</li>` +
    `<li class="muted">${state.hours}시간 · 사건 ${events.length} · 화점 ${hotspots.length}${staleTag(d.firms)}</li>`;
}

// ---------------------------------------------------------------- shell

function renderAll() {
  renderCrisis(); renderHeadline(); renderCityTable(); renderEvents(); renderTelegram(); renderNotices(); renderNews(); renderMap(); renderFlightsTile(); renderNotams();
}

function setLastUpdated(iso) {
  document.getElementById("last-updated").textContent =
    `업데이트 ${new Date(iso).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Riyadh" })} (사우디 현지) · 매시간 자동`;
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
    setLastUpdated(fresh.generated_at);
    status.textContent = changed ? "갱신됨" : "이미 최신";
  } catch {
    status.textContent = "실패 — 잠시 후 다시";
  } finally {
    refreshBtn.disabled = false;
    setTimeout(() => { status.textContent = ""; }, 5000);
  }
});

async function main() {
  try {
    const res = await fetch("data/latest.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`data/latest.json ${res.status}`);
    state.data = await res.json();
    renderAll();
    setLastUpdated(state.data.generated_at);
  } catch (err) {
    document.getElementById("headline").innerHTML = "<p>데이터 로드 실패</p>";
    console.error(err);
  }
}

main();
