#!/usr/bin/env python3
"""
얀부·제다 상황판 데이터 수집. 세 가지 간접 지표를 만든다.

  attention  영어 위키피디아 Yanbu/Jeddah 일일 조회수 ÷ 평시 중앙값
  firms      NASA FIRMS VIIRS 위성 열 감지 (서부 사우디, 최근 7일)
  mofa       외교부 해외안전여행 사우디 경보 단계 + 안전공지 주간 건수

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

    # 오늘은 위성 패스가 다 안 들어왔으므로 일별 집계·이력은 어제까지만 쓴다.
    yesterday = (TODAY - timedelta(days=1)).isoformat()
    days = [(TODAY - timedelta(days=i)).isoformat() for i in range(7, 0, -1)]
    per_day = Counter(h["date"] for h in hotspots)
    history = dict(sorted({**previous_history, **{d: per_day[d] for d in days}}.items())[-90:])
    older = [c for d, c in history.items() if d < days[0]]
    baseline = statistics.median(older) if len(older) >= 7 else None

    regions = {}
    for region in REGIONS:
        inside = [h for h in hotspots if in_box(h["lat"], h["lon"], region["box"])]
        regions[region["key"]] = {"h24": sum(1 for h in inside if h["date"] >= yesterday), "d7": len(inside)}

    result.update({
        "ok": True,
        "hotspots": sorted(hotspots, key=lambda h: h["date"])[-300:],
        "daily_counts": [{"date": d, "count": per_day[d]} for d in days],
        "last24h": sum(1 for h in hotspots if h["date"] >= yesterday),
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
    }
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=1)
    print(" ".join(f"{k}_ok={output[k]['ok']}" for k in ("attention", "firms", "mofa")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
