#!/usr/bin/env python3
"""
얀부·제다 상황판 데이터 수집. 세 가지 간접 지표를 만든다.

  attention  영어 위키피디아 Yanbu/Jeddah 일일 조회수 ÷ 평시 중앙값
  firms      NASA FIRMS VIIRS 위성 열 감지 (서부 사우디, 최근 7일)
  mofa       외교부 해외안전여행 사우디 경보 단계 + 안전공지 주간 건수
  news       Google News RSS에서 공신력 있는 국내·해외 매체만 골라 최근 5건씩
  maritime   IMF PortWatch(AIS 집계) 얀부항·제다항 일일 입항 수, 밥엘만데브 통과 수

모두 무료·무키. 실패한 소스는 이전 성공 데이터를 유지하고 stale=true 로 표시.
"""
import csv
import html as htmllib
import io
import json
import os
import re
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "latest.json")
HEADERS = {"User-Agent": "yanbu-dashboard/1.0 (github.com/junekinns/yanbu-dashboard)"}
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}

REGIONS = [
    {"key": "yanbu", "name": "얀부", "aliases": ["얀부", "Yanbu"], "lat": 24.0895, "lon": 38.0618,
     "box": (23.7, 24.4, 37.8, 38.6), "wiki": "Yanbu"},
    {"key": "jeddah", "name": "제다", "aliases": ["제다", "젯다", "Jeddah"], "lat": 21.4858, "lon": 39.1925,
     "box": (21.2, 22.0, 38.9, 39.6), "wiki": "Jeddah"},
]
WEST_SAUDI_BOX = (20.0, 26.5, 37.0, 42.0)  # 제다~얀부~메디나주 송유관 회랑

MOFA_BASE = "https://www.0404.go.kr"
MOFA_COUNTRY_URL = f"{MOFA_BASE}/ntnSafetyInfo/107/detail"
MOFA_NOTICE_URL = f"{MOFA_BASE}/bbs/safetyNtc/list?ntnCd=107&pageSize=50"
FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_7d.csv"
WIKI_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{title}/daily/{start}/{end}"

GOOGLE_NEWS_URL = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
NEWS_FEEDS = {
    "kr": {
        "query": "사우디 (후티 OR 공격 OR 드론 OR 미사일 OR 교민 OR 송유관 OR 얀부 OR 제다) when:7d",
        "locale": {"hl": "ko", "gl": "KR", "ceid": "KR:ko"},
        "sources": ["연합뉴스", "KBS", "MBC", "SBS", "JTBC", "YTN", "조선일보", "중앙일보", "동아일보",
                    "한국일보", "한겨레", "경향신문", "뉴스1", "뉴시스", "채널A", "MBN", "국민일보", "서울신문"],
    },
    "en": {
        "query": "Saudi (Houthi OR Yanbu OR Jeddah OR pipeline OR drone OR missile) when:7d",
        "locale": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
        "sources": ["Reuters", "AP News", "Bloomberg", "BBC", "Al Jazeera", "Financial Times", "The Guardian",
                    "The New York Times", "The Washington Post", "Wall Street Journal", "CNN", "NBC News", "CBS News",
                    "ABC News", "PBS", "NPR", "CNBC", "Arab News", "Saudi Gazette", "The National", "DW", "France 24", "Euronews"],
    },
}

PORTWATCH_BASE = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
PORTWATCH_SERIES = [
    {"key": "yanbu_port", "name": "얀부항(King Fahd)", "service": "Daily_Ports_Data", "where": "portid='port570'", "field": "portcalls"},
    {"key": "jeddah_port", "name": "제다항", "service": "Daily_Ports_Data", "where": "portid='port518'", "field": "portcalls"},
    {"key": "bab_el_mandeb", "name": "밥엘만데브 해협", "service": "Daily_Chokepoints_Data", "where": "portid='chokepoint4'", "field": "n_total"},
]

# 외교부 단계. 특별여행주의보는 2단계 이상·3단계 이하로 운용되므로 2.5.
LEVELS = {"여행유의": 1, "여행자제": 2, "특별여행주의보": 2.5, "출국권고": 3, "여행금지": 4}

TODAY = datetime.now(timezone.utc).date()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, headers=HEADERS, timeout=60):
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp


def strip_html(fragment):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def in_box(lat, lon, box):
    return box[0] <= lat <= box[1] and box[2] <= lon <= box[3]


def ratio(value, baseline):
    return round(value / baseline, 1) if baseline else None


def load_previous():
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


# ------------------------------------------------------------ attention

def fetch_attention():
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "articles": []}
    start, end = (TODAY - timedelta(days=60)).strftime("%Y%m%d"), TODAY.strftime("%Y%m%d")
    try:
        for region in REGIONS:
            items = get(WIKI_URL.format(title=region["wiki"], start=start, end=end)).json()["items"]
            series = [{"date": f"{i['timestamp'][:4]}-{i['timestamp'][4:6]}-{i['timestamp'][6:8]}", "views": i["views"]} for i in items]
            baseline = statistics.median(s["views"] for s in series[:-14]) if len(series) > 20 else None
            latest = series[-1]
            result["articles"].append({
                "key": region["key"], "name": region["name"], "title": region["wiki"],
                "baseline": baseline, "latest": latest["views"], "latest_date": latest["date"],
                "ratio": ratio(latest["views"], baseline), "series": series[-30:],
            })
    except (requests.RequestException, KeyError, ValueError) as exc:
        result["error"] = str(exc)
        return result
    result["ok"] = True
    return result


# ------------------------------------------------------------ firms

def fetch_firms(previous_history):
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "source_url": FIRMS_URL}
    try:
        text = get(FIRMS_URL, timeout=180).text
    except requests.RequestException as exc:
        result["error"] = str(exc)
        return result

    hotspots = []
    for row in csv.DictReader(io.StringIO(text)):
        lat, lon = float(row["latitude"]), float(row["longitude"])
        if in_box(lat, lon, WEST_SAUDI_BOX):
            hotspots.append({"lat": lat, "lon": lon, "frp": float(row["frp"]), "date": row["acq_date"],
                             "time": row["acq_time"], "confidence": row["confidence"]})

    # 정유공장 가스 플레어는 매일 같은 자리에서 잡힌다. 7일 중 4일 이상 같은
    # ~3km 격자에 나타난 열원은 '상시'로 분류해 이상 화점 집계에서 뺀다.
    cell_of = lambda h: (round(h["lat"] / 0.03), round(h["lon"] / 0.03))
    cell_days = {}
    for h in hotspots:
        cell_days.setdefault(cell_of(h), set()).add(h["date"])
    persistent = {c for c, ds in cell_days.items() if len(ds) >= 4}
    for h in hotspots:
        h["persistent"] = cell_of(h) in persistent
    anomalous = [h for h in hotspots if not h["persistent"]]

    # 오늘은 위성 패스가 다 안 들어왔으므로 일별 집계·이력은 어제까지만 쓴다.
    yesterday = (TODAY - timedelta(days=1)).isoformat()
    days = [(TODAY - timedelta(days=i)).isoformat() for i in range(7, 0, -1)]
    per_day = Counter(h["date"] for h in anomalous)
    per_day_flare = Counter(h["date"] for h in hotspots if h["persistent"])
    history = dict(sorted({**previous_history, **{d: per_day[d] for d in days}}.items())[-90:])
    older = [c for d, c in history.items() if d < days[0]]
    baseline = statistics.median(older) if len(older) >= 7 else None

    regions = {}
    for region in REGIONS:
        inside = [h for h in anomalous if in_box(h["lat"], h["lon"], region["box"])]
        regions[region["key"]] = {"h24": sum(1 for h in inside if h["date"] >= yesterday), "d7": len(inside)}

    result.update({
        "ok": True,
        "hotspots": sorted(hotspots, key=lambda h: h["date"])[-300:],
        "flare_sites": [{"lat": round(c[0] * 0.03, 3), "lon": round(c[1] * 0.03, 3), "days": len(cell_days[c])} for c in sorted(persistent)],
        "daily_counts": [{"date": d, "count": per_day[d], "flares": per_day_flare[d]} for d in days],
        "last24h": sum(1 for h in anomalous if h["date"] >= yesterday),
        "flares24h": sum(1 for h in hotspots if h["persistent"] and h["date"] >= yesterday),
        "baseline": baseline,
        "history": history,
        "regions": regions,
    })
    return result


# ------------------------------------------------------------ mofa

def parse_advisories(page):
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)  # 주석 처리된 예시 <li>가 남아있음
    block = re.search(r'<ul class="info-02">(.*?)</ul>', page, re.S)
    if not block:
        raise ValueError("info-02 블록 없음 (페이지 구조 변경?)")
    advisories = []
    for li in re.findall(r"<li>(.*?)</li>", block.group(1), re.S):
        tag = re.search(r'<span class="box-tag-01[^"]*">(.*?)</span>', li, re.S)
        if tag:
            name = strip_html(tag.group(1))
            advisories.append({"level_name": name, "level": LEVELS.get(name), "regions": strip_html(li.replace(tag.group(0), ""))})
    if not advisories:
        raise ValueError("경보 항목 없음")
    return advisories


def region_level(advisories, region):
    named = [a for a in advisories if any(alias in a["regions"] for alias in region["aliases"])]
    if named:
        return max(named, key=lambda a: a["level"] or 0)
    rest = [a for a in advisories if "제외한" in a["regions"]]
    return rest[0] if rest else {}


def parse_notices(page):
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    notices = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        link = re.search(r'<a href="(/bbs/safetyNtc/[^"]+)" class="btn title">(.*?)</a>', row, re.S)
        day = re.search(r"<td>\s*(\d{4}-\d{2}-\d{2})\s*</td>", row)
        if link and day:
            notices.append({"date": day.group(1), "title": strip_html(link.group(2)),
                            "url": MOFA_BASE + htmllib.unescape(link.group(1))})
    return sorted(notices, key=lambda n: n["date"], reverse=True)


def fetch_summary(url):
    try:
        body = re.search(r'<textarea id="textCnHtml"[^>]*>(.*?)</textarea>', get(url, BROWSER_HEADERS).text, re.S)
    except requests.RequestException:
        return None
    if not body:
        return None
    text = strip_html(htmllib.unescape(body.group(1)))
    return text[:200] + ("…" if len(text) > 200 else "")


def fetch_mofa():
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "source_url": MOFA_COUNTRY_URL}
    try:
        advisories = parse_advisories(get(MOFA_COUNTRY_URL, BROWSER_HEADERS).text)
        notices = parse_notices(get(MOFA_NOTICE_URL, BROWSER_HEADERS).text)
    except (requests.RequestException, ValueError) as exc:
        result["error"] = str(exc)
        return result

    for n in notices[:3]:
        n["summary"] = fetch_summary(n["url"])
        time.sleep(0.5)

    # 달력 주가 아니라 오늘로 끝나는 7일 창을 8개 이어 붙인다 (주중에도 값이 덜 잡히지 않게).
    windows = [TODAY - timedelta(days=7 * i) for i in range(7, -1, -1)]
    counts = []
    for end in windows:
        start = end - timedelta(days=6)
        counts.append(sum(1 for n in notices if start.isoformat() <= n["date"] <= end.isoformat()))
    baseline = statistics.median(counts[:-2])

    result.update({
        "ok": True,
        "advisories": advisories,
        "regions": [{"key": r["key"], "name": r["name"], "lat": r["lat"], "lon": r["lon"],
                     **{k: region_level(advisories, r).get(k) for k in ("level", "level_name")}} for r in REGIONS],
        "notices": notices[:3],
        "weekly_counts": [{"week": w.isoformat(), "count": c} for w, c in zip(windows, counts)],
        "last7d": counts[-1],
        "baseline": baseline,
        "ratio": ratio(counts[-1], baseline),
    })
    return result


# ------------------------------------------------------------ news

def parse_feed(xml, allowed):
    items = []
    seen = set()
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        title = strip_html(re.search(r"<title>(.*?)</title>", item, re.S).group(1))
        source_tag = re.search(r"<source[^>]*>(.*?)</source>", item, re.S)
        raw_source = strip_html(source_tag.group(1)) if source_tag else ""
        source = next((a for a in allowed if a.lower() in raw_source.lower()), None)
        if not source:
            continue
        title = re.sub(rf"\s*-\s*{re.escape(raw_source)}\s*$", "", title)  # 구글뉴스는 제목 끝에 " - 매체명"을 붙임
        key = re.sub(r"[^\w가-힣]", "", title.lower())[:40]
        if key in seen:
            continue
        seen.add(key)
        published = parsedate_to_datetime(re.search(r"<pubDate>(.*?)</pubDate>", item).group(1))
        items.append({
            "date": published.strftime("%Y-%m-%d"),
            "published": published.isoformat(),
            "source": source,
            "title": title,
            "url": htmllib.unescape(re.search(r"<link>(.*?)</link>|<link/>(.*?)<", item, re.S).group(1) or ""),
        })
    items.sort(key=lambda i: i["published"], reverse=True)
    picked, per_source = [], Counter()
    for i in items:  # 한 매체가 비슷한 기사로 다 채우지 않게 매체당 2건까지
        if per_source[i["source"]] < 2:
            picked.append(i)
            per_source[i["source"]] += 1
        if len(picked) == 5:
            break
    return picked


def fetch_news():
    result = {"ok": False, "error": None, "fetched_at": now_iso()}
    try:
        for key, feed in NEWS_FEEDS.items():
            url = GOOGLE_NEWS_URL.format(q=quote(feed["query"]), **feed["locale"])
            result[key] = parse_feed(get(url).text, feed["sources"])
    except (requests.RequestException, AttributeError, ValueError) as exc:
        result["error"] = str(exc)
        return result
    result["ok"] = True
    return result


# ------------------------------------------------------------ maritime

def portwatch_rows(spec):
    params = {"where": spec["where"], "outFields": f"date,{spec['field']}", "orderByFields": "date DESC",
              "resultRecordCount": 1000, "returnGeometry": "false", "f": "json"}
    data = get(f"{PORTWATCH_BASE}/{spec['service']}/FeatureServer/0/query?" + "&".join(f"{k}={quote(str(v))}" for k, v in params.items())).json()
    if "error" in data:
        raise ValueError(f"PortWatch {spec['key']}: {data['error'].get('message')}")
    rows = []
    for f in data["features"]:
        ts = f["attributes"]["date"]
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat() if isinstance(ts, (int, float)) else str(ts)[:10]
        rows.append((day, f["attributes"][spec["field"]] or 0))
    return sorted(rows)


def fetch_maritime():
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "series": {}}
    try:
        for spec in PORTWATCH_SERIES:
            rows = portwatch_rows(spec)
            values = [v for _, v in rows]
            rolling7 = [sum(values[i - 6:i + 1]) for i in range(6, len(values))]
            last7 = rolling7[-1]
            # 최근 2주를 뺀 지난 1년의 7일 합 중앙값을 평시로 본다.
            baseline = statistics.median(rolling7[-379:-14]) if len(rolling7) > 60 else None
            result["series"][spec["key"]] = {
                "name": spec["name"], "last_date": rows[-1][0], "last7": last7,
                "baseline7": baseline, "ratio": ratio(last7, baseline),
                "spark": [{"date": rows[i][0], "value": rolling7[i - 6]} for i in range(len(rows) - 90, len(rows))],
            }
    except (requests.RequestException, ValueError, KeyError) as exc:
        result["error"] = str(exc)
        return result
    result["ok"] = True
    return result


# ------------------------------------------------------------ main

def carry_over(current, previous):
    if current["ok"] or not (previous.get("ok") or previous.get("stale")):
        return current
    kept = {k: v for k, v in previous.items() if k not in ("ok", "error", "fetched_at")}
    return {**kept, **current, "stale": True}


def main():
    previous = load_previous()
    output = {
        "generated_at": now_iso(),
        "attention": carry_over(fetch_attention(), previous.get("attention", {})),
        "firms": carry_over(fetch_firms(previous.get("firms", {}).get("history", {})), previous.get("firms", {})),
        "mofa": carry_over(fetch_mofa(), previous.get("mofa", {})),
        "news": carry_over(fetch_news(), previous.get("news", {})),
        "maritime": carry_over(fetch_maritime(), previous.get("maritime", {})),
    }
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=1)
    print(" ".join(f"{k}_ok={output[k]['ok']}" for k in ("attention", "firms", "mofa", "news", "maritime")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
