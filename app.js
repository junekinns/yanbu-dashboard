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
// 실험 타일(홍해 상공 회피)에만 남은 3단계 배지 색
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
// 페이지의 모든 날짜·시각은 사우디 현지 기준
const fmtMD = (iso) => {
  const [, m, d] = new Date(iso).toLocaleDateString("en-CA", { timeZone: "Asia/Riyadh" }).split("-");
  return `${+m}/${+d}`;
};

const state = { data: null, hours: 72, base: "dark", map: null, layer: null, baseLayers: {}, charts: {}, markers: {}, showQuiet: false };

// ---------------------------------------------------------------- 위기 단계

function renderCrisis() {
  const s = state.data.summary, el = document.getElementById("crisis");
  if (!s || s.level == null) { el.className = "crisis"; el.innerHTML = ""; return; }
  const hist = Object.entries(s.history || {}).slice(-7);
  el.className = `crisis lv${s.level}`;
  el.innerHTML = `
    <div class="crisis-num" aria-label="위기 단계 ${s.level}">${s.level}</div>
    <div class="crisis-body">
      <div class="crisis-label">위기 단계 <strong>${esc(s.label)}</strong> <span class="muted">/ 5</span>${s.stale ? `<span class="muted small"> (계산 실패 — 이전 값)</span>` : ""}</div>
      <ul class="crisis-why">${(s.reasons || []).map((r) => `<li>${esc(r)}</li>`).join("") || "<li>점수를 낸 신호 없음</li>"}</ul>
      <div class="crisis-strip">${hist.map(([d, l]) => `<span class="lv${l}" title="${d}">${l}</span>`).join("")}<span class="muted small">최근 ${hist.length}일</span></div>
    </div>`;
}

// ---------------------------------------------------------------- 도시 행 (표·헤드라인·지도 팝업이 공유)

function cityRows() {
  const d = state.data, m = d.mofa || {}, tempo = d.events?.tempo || {}, mentions = d.telegram?.mentions7d || {};
  const cutoff = Date.now() - 30 * 864e5;
  const latestChange = {};
  (m.changes || []).forEach((c) => { if (Date.parse(c.at) >= cutoff && !latestChange[c.city]) latestChange[c.city] = c; });
  return (m.places || []).map((p) => ({
    ...p,
    tempo: tempo[p.name] || { "7d": {}, total7d: 0, prev7d: null, prev_total: null },
    mentions: mentions[p.name] || 0,
    change: latestChange[p.name] || null,
  })).sort((a, b) => (b.level || 0) - (a.level || 0) || b.tempo.total7d - a.tempo.total7d || a.name.localeCompare(b.name, "ko"));
}

// ---------------------------------------------------------------- 헤드라인

function renderHeadline() {
  const m = state.data.mofa || {}, el = document.getElementById("headline");
  if (!(m.places || []).length) { el.innerHTML = `<p>외교부 데이터 수집 실패${staleTag(m)}</p>`; return; }
  const rows = cityRows();
  const high = rows.filter((p) => p.level >= 3);
  const counts = {};
  rows.filter((p) => !(p.level >= 3) && p.level).forEach((p) => { counts[p.level] = (counts[p.level] || 0) + 1; });
  const mode = Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0];
  const line1 = (high.length
    ? `<span class="dot level-3"></span><strong>출국권고</strong> ${high.map((p) => esc(p.name)).join(" · ")} <span class="muted">(${high.length}곳)</span>`
    : "출국권고 지역 없음") +
    (mode ? ` · <span class="dot ${styleOf(mode).cls}"></span>그 외 전 지역 <strong>${styleOf(mode).label}</strong>` : "");
  const recent = (m.changes || []).filter((c) => Date.now() - Date.parse(c.at) < 30 * 864e5).slice(0, 3);
  const line2 = recent.length
    ? `<strong>최근 변경</strong> ` + recent.map((c) => `${esc(c.city)} ${esc(c.from_name || c.from)} → <strong>${esc(c.to_name || c.to)}</strong> (${fmtMD(c.at)})`).join(" · ")
    : `최근 30일 단계 변경 없음 <span class="muted">(추적 시작 ${m.tracking_since ? fmtMD(m.tracking_since) : "–"})</span>`;
  const line3 = m.last7d != null ? `이번 주 외교부 공지 <strong>${m.last7d}건</strong> <span class="muted">(평시 ${m.baseline}건 · ${esc(m.tier)})</span>` : "";
  el.innerHTML = [line1, line2, line3].filter(Boolean).map((s) => `<p>${s}</p>`).join("") +
    (m.stale ? `<p class="muted small">외교부 데이터${staleTag(m)}</p>` : "");
}

// ---------------------------------------------------------------- 도시 현황표

function renderCityTable() {
  const ev = state.data.events || {}, tg = state.data.telegram || {};
  const rows = cityRows(), compare = (ev.history_days || 0) >= 14;
  const zero = `<span class="zero">—</span>`;
  const cell = (n, type) => (n ? `<span class="ev-type ${TYPE_STYLE[type].cls}">${n}</span>` : zero);
  const delta = (t) => {
    if (!compare || t.prev_total == null) return zero;
    const diff = t.total7d - t.prev_total;
    return diff > 0 ? `<span class="up">▲ +${diff}</span>` : diff < 0 ? `<span class="down">▼ ${diff}</span>` : `<span class="flat">=</span>`;
  };
  const pinned = new Set(state.data.summary?.pinned || []);
  const active = (p) => pinned.has(p.name) || p.tempo.total7d > 0 || p.mentions > 0 || !!p.change;
  const shown = rows.filter(active), quiet = rows.filter((p) => !active(p));
  const tr = (p, cls = "") => `
    <tr class="${cls}" data-city="${esc(p.name)}">
      <td class="col-city"><button type="button" class="city-link">${esc(p.name)}</button></td>
      <td class="col-level"><span class="dot ${styleOf(p.level).cls}"></span>${styleOf(p.level).label}${p.change
        ? ` <span class="chg" title="${esc(p.change.from_name || p.change.from)} → ${esc(p.change.to_name || p.change.to)}">▲ ${fmtMD(p.change.at)}</span>` : ""}</td>
      ${TYPES.map((t) => `<td class="col-type num">${cell(p.tempo["7d"][t] || 0, t)}</td>`).join("")}
      <td class="col-total num">${p.tempo.total7d ? `<strong>${p.tempo.total7d}</strong>` : zero}</td>
      <td class="col-delta num">${delta(p.tempo)}</td>
      <td class="col-houthi num">${p.mentions ? `<span class="place-badge">${p.mentions}</span>` : zero}</td>
    </tr>`;
  document.querySelector("#city-table tbody").innerHTML = (shown.map((p) => tr(p)).join("") +
    (quiet.length ? `<tr class="more"><td colspan="9"><button type="button" class="quiet-toggle">${state.showQuiet ? "▲ 조용한 도시 접기" : `▼ 조용한 도시 ${quiet.length}곳 보기`} <span class="muted">(7일 사건·후티 언급 없음)</span></button></td></tr>` : "") +
    (state.showQuiet ? quiet.map((p) => tr(p, "quiet")).join("") : ""))
    || `<tr><td colspan="9" class="muted">외교부 데이터 수집 실패</td></tr>`;

  const houthi = `후티: 최근 7일 이 도시를 지목한 메시지 수 (상대측 발표 · 검증되지 않음)${staleTag(tg)}`;
  document.getElementById("city-note").textContent = ev.history_days == null ? houthi
    : compare
      ? `사건: 최근 7일 vs 이전 7일 (이력 ${ev.history_days}일)${staleTag(ev)} · ${houthi}`
      : `사건 이력 ${ev.history_days}일째 — 지난주 대비는 14일부터 표시${staleTag(ev)} · ${houthi}`;
}

document.getElementById("city-table").addEventListener("click", (e) => {
  if (e.target.closest(".quiet-toggle")) { state.showQuiet = !state.showQuiet; renderCityTable(); return; }
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
      <span class="ev-type ${TYPE_STYLE[e.type]?.cls || ""}">${e.type}</span>
      <a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a>
      <span class="ev-meta">${esc(e.source)}${e.outlets > 1 ? ` 외 ${e.outlets - 1}` : ""}</span>
    </li>`).join("") || `<li class="muted">${ev.error && !ev.events ? "수집 실패" : "최근 72시간 해당 보도 없음"}${staleTag(ev)}</li>`;
}

function renderTelegram() {
  const tg = state.data.telegram || {};
  const mentions = Object.entries(tg.mentions7d || {});
  document.getElementById("tg-mentions").innerHTML =
    `<span class="muted small">최근 7일 언급 표적</span> ` +
    (mentions.length ? mentions.map(([c, n]) => `<span class="place-badge">${esc(c)} <b>${n}</b></span>`).join(" ") : `<span class="muted">사우디 도시 언급 없음</span>`) +
    ` <span class="muted small">· 상대측 발표 · 검증되지 않음${staleTag(tg)}</span>`;
  document.getElementById("telegram-list").innerHTML = (tg.messages || []).slice(0, 6).map((msg) => `
    <li>
      <div class="tg-head"><span class="ev-time">${msg.time}</span>
        ${msg.places.map((p) => `<span class="place-badge">${esc(p)}</span>`).join("")}
        <a class="tg-link" href="${esc(msg.url)}" target="_blank" rel="noopener">채널에서 보기</a></div>
      <p class="tg-text">${msg.text_ko ? esc(msg.text_ko) : '<span class="muted">번역 실패 — 아래 원문 참고</span>'}</p>
      <details class="tg-original">
        <summary>아랍어 원문${msg.text_ko ? "" : " (번역 없음)"}</summary>
        <p class="tg-text" dir="rtl" lang="ar">${esc(msg.text_ar)}</p>
      </details>
    </li>`).join("") || `<li class="muted">${tg.error && !tg.messages ? "수집 실패" : "최근 메시지 중 사우디 언급 없음"}</li>`;
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
  sec.innerHTML = `<h2>사우디 공역 NOTAM <span class="muted small">${(n.locations || []).join(" · ")} · 공역 폐쇄·제한·위험구역만${staleTag(n)}</span></h2>` +
    (n.ok === false && !n.stale
      ? `<p class="muted" title="${esc(n.error || "")}">수집 실패 — 다음 갱신 때 재시도</p>`
      : items.length
        ? `<ul class="notice-list">${items.map((i) => `<li><div class="notice-date">${esc(i.location)} · ${esc(i.kind)} · ${esc((i.effective_start || "").slice(0, 16))} ~ ${esc((i.effective_end || "").slice(0, 16))}</div><p class="summary">${esc(i.text)}</p></li>`).join("")}</ul>`
        : `<p class="muted">현행 공역 제한 NOTAM 없음</p>`);
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
    sub: `홍해 회랑 상공 현재 ${fl.count}대 (${baseline})${staleTag(fl)}`,
    labels: hist.map(([k]) => k.slice(5)), values: hist.map(([, v]) => v),
  } : failed(fl));
}

// ---------------------------------------------------------------- 지도

function placeBounds(places) {
  const bounds = L.latLngBounds();
  places.forEach((p) => { if (p.lat != null && p.lon != null) bounds.extend([p.lat, p.lon]); });
  return bounds;
}

function renderMap() {
  const d = state.data, places = d.mofa?.places || [];
  if (!state.map) {
    state.map = L.map("map", { scrollWheelZoom: false });
    state.baseLayers.dark = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { attribution: "&copy; OpenStreetMap &copy; CARTO", maxZoom: 11 }).addTo(state.map);
    state.baseLayers.sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "Esri World Imagery", maxZoom: 18 });
    if (places.length) state.map.fitBounds(placeBounds(places), { padding: [16, 16] });
    else state.map.setView([24, 45], 5);
  }
  state.layer?.remove();
  state.layer = L.layerGroup().addTo(state.map);
  state.markers = {};

  const since = Date.now() - state.hours * 3600e3;
  const events = (d.events?.events || []).filter((e) => e.lat && new Date(e.iso) >= since);
  const hotspots = (d.firms?.hotspots || [])
    .filter((h) => new Date(`${h.date}T${h.time.padStart(4, "0").replace(/(\d\d)(\d\d)/, "$1:$2")}:00Z`) >= since);

  // 위성 이상 화점 — 클수록 화력, 옅을수록 오래된 것
  hotspots.forEach((h) => {
    const age = (Date.now() - new Date(`${h.date}T00:00:00Z`)) / 864e5;
    L.circleMarker([h.lat, h.lon], { radius: 3 + Math.sqrt(h.frp), color: "#ff7a1a", fillColor: "#ff4d1a", weight: 1,
      fillOpacity: Math.max(0.2, 0.85 - age * 0.1), opacity: Math.max(0.35, 1 - age * 0.1) })
      .bindTooltip(`위성 화점 · ${h.date} ${h.time.padStart(4, "0")} UTC · FRP ${h.frp}`).addTo(state.layer);
  });

  // 도시 — 외교부 단계 색. 팝업은 표와 같은 숫자.
  const tempo = d.events?.tempo || {}, mentions = d.telegram?.mentions7d || {};
  places.forEach((p) => {
    const s = styleOf(p.level), t = tempo[p.name];
    state.markers[p.name] = L.circleMarker([p.lat, p.lon], { radius: 8, color: "#fff", weight: 1.5, fillColor: s.color, fillOpacity: 0.95, dashArray: s.dashed ? "3 3" : null })
      .bindTooltip(p.name, { permanent: true, direction: "right", offset: [8, 0], className: "place-label" })
      .bindPopup(`<b>${esc(p.name)}</b><br>외교부 ${s.label}` +
        (t ? `<br>최근 7일 사건 ${t.total7d}건` : "") +
        (mentions[p.name] ? `<br>후티 언급 ${mentions[p.name]}회 (7일)` : ""))
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

  const present = [...new Set(places.map((p) => p.level).filter(Boolean))].sort();
  document.getElementById("legend").innerHTML =
    present.map((l) => `<li><span class="dot ${styleOf(l).cls}"></span>${styleOf(l).label}</li>`).join("") +
    Object.entries(TYPE_STYLE).map(([k, v]) => `<li><span class="dot" style="background:${v.color}"></span>${k}</li>`).join("") +
    `<li><span class="dot" style="background:#ff4d1a"></span>위성 이상 화점</li>` +
    `<li class="muted">${state.hours}시간 내 · 사건 ${events.length}건 · 화점 ${hotspots.length}건${staleTag(d.firms)}</li>`;
}

// ---------------------------------------------------------------- shell

function renderAll() {
  renderCrisis(); renderHeadline(); renderCityTable(); renderEvents(); renderTelegram(); renderNotices(); renderNews(); renderMap(); renderFlightsTile(); renderNotams();
}

function setLastUpdated(iso) {
  // 사건·채널 시각이 사우디 현지라 여기도 맞춘다. 한국 가족의 브라우저에서도 같은 값이 보이도록 시간대를 고정.
  document.getElementById("last-updated").textContent =
    `마지막 업데이트: ${new Date(iso).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Riyadh" })} (사우디 현지)`;
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
    status.textContent = changed ? "새 데이터로 갱신했습니다" : "이미 최신입니다 (다음 자동 수집까지 대기)";
  } catch {
    status.textContent = "새로고침 실패 — 잠시 후 다시 시도";
  } finally {
    refreshBtn.disabled = false;
    setTimeout(() => { status.textContent = ""; }, 6000);
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
