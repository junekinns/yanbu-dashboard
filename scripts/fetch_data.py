#!/usr/bin/env python3
"""
Red Sea Watch 데이터 수집. 세 권역(서부·중부·동부)별 간접 지표를 만든다.

  firms      NASA FIRMS VIIRS 위성 열 감지 — 권역별 이상 화점(상시 플레어 제외)
  mofa       외교부 해외안전여행 사우디 경보 단계(지점별) + 안전공지 템포
  maritime   IMF PortWatch(AIS 집계) 항구별 입항 수, 밥엘만데브·호르무즈 통과 수
  news       Google News RSS, 공신력 있는 국내·해외 매체만 5건씩
  events     공격·요격·경보 보도를 (날짜·도시·유형)으로 묶은 이벤트 로그
  telegram   후티 군 대변인 공식 Telegram 채널(웹 미리보기) — 사우디 지명 언급 메시지

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
TODAY = datetime.now(timezone.utc).date()
AST = timezone(timedelta(hours=3))  # 사우디 현지시각

# 권역. box는 위성 화점 집계 범위, primary_port는 해상 타일 대표 항.
REGIONS = [
    {"key": "west", "name": "서부", "label": "얀부 · 제다", "box": (20.0, 26.5, 37.0, 42.0),
     "primary_port": "port570", "chokepoint": "chokepoint4", "center": [23.0, 39.3], "zoom": 6},
    {"key": "central", "name": "중부", "label": "리야드", "box": (23.3, 26.2, 45.3, 48.2),
     "primary_port": None, "chokepoint": "chokepoint6", "center": [24.5, 46.9], "zoom": 7},
    {"key": "east", "name": "동부", "label": "담맘 · 다란 · 주베일", "box": (25.3, 28.6, 48.3, 50.9),
     "primary_port": "port526", "chokepoint": "chokepoint6", "center": [26.4, 49.8], "zoom": 7},
]

# 세 지표는 "몇 배"가 아니라 3단계 배지로 단순화해 보여준다.
def tier_up(value, hi=3, mid=1.5, labels=("위험", "주의", "평시")):
    """높을수록 위험한 지표(위성 열 감지·공지 템포)."""
    if value is None or value < mid:
        return labels[2]
    return labels[0] if value >= hi else labels[1]


def tier_down(value, lo=0.34, mid=0.67, labels=("끊김", "감소", "정상")):
    """낮을수록 위험한 지표(해상 교통)."""
    if value is None or value > mid:
        return labels[2]
    return labels[0] if value <= lo else labels[1]

# 지도·로그·텔레그램 지명 매칭용 지점. aliases는 한/영, ar은 아랍어. port는 PortWatch id.
PLACES = [
    {"name": "얀부", "region": "west", "aliases": ["얀부", "Yanbu"], "ar": ["ينبع"], "lat": 24.09, "lon": 38.06, "port": "port570"},
    {"name": "제다", "region": "west", "aliases": ["제다", "젯다", "Jeddah"], "ar": ["جدة", "جده"], "lat": 21.49, "lon": 39.19, "port": "port518"},
    {"name": "메디나", "region": "west", "aliases": ["메디나", "Medina", "Madinah"], "ar": ["المدينة"], "lat": 24.47, "lon": 39.61},
    {"name": "라비그", "region": "west", "aliases": ["라비그", "Rabigh"], "ar": ["رابغ"], "lat": 22.80, "lon": 39.03, "port": "port1081"},
    {"name": "킹압둘라항", "region": "west", "aliases": ["King Abdullah Port", "킹압둘라"], "ar": [], "lat": 22.52, "lon": 39.10, "port": "port2031"},
    {"name": "메카", "region": "west", "aliases": ["메카", "Mecca", "Makkah"], "ar": ["مكة"], "lat": 21.39, "lon": 39.86},
    {"name": "타이프", "region": "west", "aliases": ["타이프", "Taif"], "ar": ["الطائف"], "lat": 21.27, "lon": 40.42},
    {"name": "리야드", "region": "central", "aliases": ["리야드", "Riyadh"], "ar": ["الرياض"], "lat": 24.71, "lon": 46.68},
    {"name": "프린스술탄 공군기지", "region": "central", "aliases": ["프린스술탄", "Prince Sultan"], "ar": ["الأمير سلطان"], "lat": 24.06, "lon": 47.58},
    {"name": "담맘", "region": "east", "aliases": ["담맘", "Dammam"], "ar": ["الدمام"], "lat": 26.43, "lon": 50.10, "port": "port275"},
    {"name": "다란", "region": "east", "aliases": ["다란", "Dhahran"], "ar": ["الظهران"], "lat": 26.29, "lon": 50.11},
    {"name": "라스타누라", "region": "east", "aliases": ["라스 타누라", "라스타누라", "Ras Tanura"], "ar": ["رأس تنورة", "راس تنورة"], "lat": 26.64, "lon": 50.16, "port": "port1091"},
    {"name": "주아이마", "region": "east", "aliases": ["주아이마", "Juaymah", "Ju'aymah"], "ar": ["الجعيمة"], "lat": 26.80, "lon": 49.98, "port": "port526"},
    {"name": "주베일", "region": "east", "aliases": ["주베일", "Jubail"], "ar": ["الجبيل"], "lat": 27.01, "lon": 49.66, "port": "port24"},
    {"name": "아브카이크", "region": "east", "aliases": ["아브카이크", "Abqaiq", "Buqayq"], "ar": ["بقيق"], "lat": 25.94, "lon": 49.67},
    {"name": "샤이바 유전", "region": None, "aliases": ["샤이바", "Shaybah"], "ar": ["الشيبة"], "lat": 22.52, "lon": 53.97},
    {"name": "지잔", "region": None, "aliases": ["지잔", "자잔", "Jazan", "Jizan"], "ar": ["جازان", "جيزان"], "lat": 16.89, "lon": 42.57, "port": "port2074"},
    {"name": "아브하", "region": None, "aliases": ["아브하", "Abha"], "ar": ["أبها", "ابها"], "lat": 18.22, "lon": 42.51},
    {"name": "카미스무샤이트", "region": None, "aliases": ["카미스", "Khamis Mushait"], "ar": ["خميس مشيط", "خميس"], "lat": 18.31, "lon": 42.73},
    {"name": "나즈란", "region": None, "aliases": ["나즈란", "Najran"], "ar": ["نجران"], "lat": 17.49, "lon": 44.13},
    {"name": "송유관", "region": None, "aliases": ["송유관", "pipeline"], "ar": ["أنابيب"], "lat": None, "lon": None},
]
PLACE_BY_NAME = {p["name"]: p for p in PLACES}

MOFA_BASE = "https://www.0404.go.kr"
MOFA_COUNTRY_URL = f"{MOFA_BASE}/ntnSafetyInfo/107/detail"
MOFA_NOTICE_URL = f"{MOFA_BASE}/bbs/safetyNtc/list?ntnCd=107&pageSize=50"
FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_7d.csv"
GOOGLE_NEWS_URL = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
TELEGRAM_URL = "https://t.me/s/army21ye"  # 예멘군(후티) 대변인 야히야 사리 공식 채널
PORTWATCH_BASE = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
SAUDI_BOX = (16.0, 32.5, 34.0, 56.0)

NEWS_FEEDS = {
    "kr": {
        "query": "사우디 (후티 OR 공격 OR 드론 OR 미사일 OR 교민 OR 송유관 OR 얀부 OR 제다 OR 리야드 OR 담맘 OR 아람코) when:7d",
        "locale": {"hl": "ko", "gl": "KR", "ceid": "KR:ko"},
        "sources": ["연합뉴스", "KBS", "MBC", "SBS", "JTBC", "YTN", "조선일보", "중앙일보", "동아일보",
                    "한국일보", "한겨레", "경향신문", "뉴스1", "뉴시스", "채널A", "MBN", "국민일보", "서울신문"],
    },
    "en": {
        "query": "Saudi (Houthi OR Yanbu OR Jeddah OR Riyadh OR Dhahran OR Aramco OR pipeline OR drone OR missile) when:7d",
        "locale": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
        "sources": ["Reuters", "AP News", "Bloomberg", "BBC", "Al Jazeera", "Financial Times", "The Guardian",
                    "The New York Times", "The Washington Post", "Wall Street Journal", "CNN", "NBC News", "CBS News",
                    "ABC News", "PBS", "NPR", "CNBC", "Arab News", "Saudi Gazette", "The National", "DW", "France 24", "Euronews"],
    },
}
EVENT_QUERIES = {
    "en": ('(intercepted OR intercepts OR "shot down" OR destroyed OR strikes OR struck OR attack OR airstrike OR alert OR siren) '
           '(Houthi OR coalition OR Saudi) (Yanbu OR Jeddah OR Medina OR Mecca OR Taif OR Jazan OR Abha OR "Khamis Mushait" OR Najran '
           'OR Riyadh OR Dammam OR Dhahran OR Jubail OR "Ras Tanura" OR Abqaiq OR pipeline OR Rabigh) when:3d'),
    "kr": ("(후티 OR 사우디) (요격 OR 격추 OR 공격 OR 피격 OR 공습 OR 경보 OR 타격) "
           "(메카 OR 메디나 OR 제다 OR 얀부 OR 타이프 OR 지잔 OR 자잔 OR 아브하 OR 나즈란 OR 리야드 OR 담맘 OR 다란 OR 주베일 OR 라스타누라 OR 송유관) when:3d"),
}
EVENT_EXTRA_SOURCES = ["Middle East Eye", "The Times of Israel", "Al Arabiya", "Arab News", "The National", "Anadolu"]
TYPE_PATTERNS = [
    ("경보", r"air raid|alert|siren|civil defen[cs]e|경보|사이렌|민방위"),
    ("요격", r"intercept|shot down|shoots? down|downed|destroy|요격|격추"),
    ("공습", r"airstrike|air strike|공습"),
    ("피격", r"\bhit\b|struck|attack|strike|explosion|blast|fire|damage|suspend|shut|공격|피격|타격|폭발|화재|피해|중단|폐쇄"),
]
# 사건 자체가 아닌 기사(부인·분석·반응·후속 경제기사)는 로그에서 뺀다.
EVENT_SKIP = (r"den(y|ies|ied)|analysis|explainer|opinion|what (it|the|this)|why |pact|agreement|vow|promise|warns?|threat"
              r"|calls? (for|on)|condemn|slam|react|response|price|market|repair|insurance|shipping rate|weeks|route|reroute"
              r"|부인|분석|해설|전망|왜 |경고|촉구|규탄|다짐|유가|증시|복구|대란|항로|우회|보험|운임|주간|가동 중단될|공급|수출|고갈")
CITY_PATTERNS = [(p["name"], "|".join(rf"\b{re.escape(a)}\b" if a.isascii() else re.escape(a) for a in p["aliases"])) for p in PLACES]

# 외교부 단계. 특별여행주의보는 2단계 이상·3단계 이하로 운용되므로 2.5.
LEVELS = {"여행유의": 1, "여행자제": 2, "특별여행주의보": 2.5, "출국권고": 3, "여행금지": 4}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, headers=HEADERS, timeout=60):
    # 정부 사이트가 해외 IP에 간헐적으로 연결 타임아웃을 내서 몇 번 다시 시도한다.
    for attempt in (1, 2, 3):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 3:
                raise
            time.sleep(10 * attempt)


def strip_html(fragment):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def in_box(lat, lon, box):
    return box[0] <= lat <= box[1] and box[2] <= lon <= box[3]


def ratio(value, baseline):
    return round(value / baseline, 2) if baseline else None


def load_previous():
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def carry_over(current, previous):
    if current["ok"] or not (previous.get("ok") or previous.get("stale")):
        return current
    kept = {k: v for k, v in previous.items() if k not in ("ok", "error", "fetched_at")}
    return {**kept, **current, "stale": True}


# ------------------------------------------------------------ firms

def fetch_firms(previous):
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "source_url": FIRMS_URL, "regions": {}}
    try:
        text = get(FIRMS_URL, timeout=180).text
    except requests.RequestException as exc:
        result["error"] = str(exc)
        return result

    hotspots = []
    for row in csv.DictReader(io.StringIO(text)):
        lat, lon = float(row["latitude"]), float(row["longitude"])
        if in_box(lat, lon, SAUDI_BOX):
            hotspots.append({"lat": lat, "lon": lon, "frp": float(row["frp"]), "date": row["acq_date"],
                             "time": row["acq_time"], "confidence": row["confidence"]})

    # 정유·가스 플레어는 매일 같은 자리에서 잡힌다. 7일 중 4일 이상 같은 ~3km 격자에
    # 나타난 열원은 '상시'로 분류해 이상 화점 집계에서 뺀다.
    cell_of = lambda h: (round(h["lat"] / 0.03), round(h["lon"] / 0.03))
    cell_days = {}
    for h in hotspots:
        cell_days.setdefault(cell_of(h), set()).add(h["date"])
    persistent = {c for c, ds in cell_days.items() if len(ds) >= 4}
    anomalous = [h for h in hotspots if cell_of(h) not in persistent]

    # 오늘은 위성 패스가 다 안 들어왔으므로 일별 집계·이력은 어제까지만 쓴다.
    yesterday = (TODAY - timedelta(days=1)).isoformat()
    days = [(TODAY - timedelta(days=i)).isoformat() for i in range(7, 0, -1)]
    for region in REGIONS:
        inside = [h for h in anomalous if in_box(h["lat"], h["lon"], region["box"])]
        flares = sum(1 for h in hotspots if cell_of(h) in persistent and in_box(h["lat"], h["lon"], region["box"]) and h["date"] >= yesterday)
        per_day = Counter(h["date"] for h in inside)
        prev_hist = previous.get("regions", {}).get(region["key"], {}).get("history", {})
        history = dict(sorted({**prev_hist, **{d: per_day[d] for d in days}}.items())[-90:])
        older = [c for d, c in history.items() if d < days[0]]
        last24h = sum(1 for h in inside if h["date"] >= yesterday)
        baseline = statistics.median(older) if len(older) >= 7 else None
        result["regions"][region["key"]] = {
            "last24h": last24h,
            "flares24h": flares,
            "daily_counts": [{"date": d, "count": per_day[d]} for d in days],
            "baseline": baseline,
            "tier": tier_up(ratio(last24h, baseline)),
            "history": history,
            "hotspots": sorted(inside, key=lambda h: h["date"])[-300:],
        }
    result["ok"] = True
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


def place_level(advisories, place):
    named = [a for a in advisories if any(alias in a["regions"] for alias in place["aliases"])]
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
    counts = [sum(1 for n in notices if (end - timedelta(days=6)).isoformat() <= n["date"] <= end.isoformat()) for end in windows]
    baseline = statistics.median(counts[:-2])

    result.update({
        "ok": True,
        "advisories": advisories,
        "places": [{"name": p["name"], "region": p["region"], "lat": p["lat"], "lon": p["lon"], "port": p.get("port"),
                    **{k: place_level(advisories, p).get(k) for k in ("level", "level_name")}} for p in PLACES if p["lat"]],
        "notices": notices[:3],
        "weekly_counts": [{"week": w.isoformat(), "count": c} for w, c in zip(windows, counts)],
        "last7d": counts[-1],
        "baseline": baseline,
        "ratio": ratio(counts[-1], baseline),
        "tier": tier_up(ratio(counts[-1], baseline), labels=("급증", "증가", "평시")),
    })
    return result


# ------------------------------------------------------------ news / events

def feed_items(xml, allowed):
    """구글뉴스 RSS item → dict. 허용 매체가 아니면 버린다."""
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        title = strip_html(re.search(r"<title>(.*?)</title>", item, re.S).group(1))
        source_tag = re.search(r"<source[^>]*>(.*?)</source>", item, re.S)
        raw_source = strip_html(source_tag.group(1)) if source_tag else ""
        source = next((a for a in allowed if a.lower() in raw_source.lower()), None)
        if not source:
            continue
        published = parsedate_to_datetime(re.search(r"<pubDate>(.*?)</pubDate>", item).group(1))
        yield {
            "date": published.strftime("%Y-%m-%d"),
            "published": published.isoformat(),
            "source": source,
            "title": re.sub(rf"\s*-\s*{re.escape(raw_source)}\s*$", "", title),  # 제목 끝의 " - 매체명" 제거
            "url": htmllib.unescape(re.search(r"<link>(.*?)</link>|<link/>(.*?)<", item, re.S).group(1) or ""),
        }


def google_news(query, locale, allowed):
    return list(feed_items(get(GOOGLE_NEWS_URL.format(q=quote(query), **locale)).text, allowed))


def top_news(items):
    items = sorted(items, key=lambda i: i["published"], reverse=True)
    picked, per_source, seen = [], Counter(), set()
    for it in items:  # 제목 중복 제거 + 한 매체가 다 채우지 않게 매체당 2건까지
        key = re.sub(r"[^\w가-힣]", "", it["title"].lower())[:40]
        if key in seen or per_source[it["source"]] >= 2:
            continue
        seen.add(key)
        per_source[it["source"]] += 1
        picked.append(it)
        if len(picked) == 5:
            break
    return picked


def fetch_news():
    result = {"ok": False, "error": None, "fetched_at": now_iso()}
    try:
        for key, feed in NEWS_FEEDS.items():
            result[key] = top_news(google_news(feed["query"], feed["locale"], feed["sources"]))
    except (requests.RequestException, AttributeError, ValueError) as exc:
        result["error"] = str(exc)
        return result
    result["ok"] = True
    return result


def classify(title):
    if re.search(EVENT_SKIP, title, re.I):
        return None
    city = next((name for name, rx in CITY_PATTERNS if re.search(rx, title, re.I)), None)
    kind = next((name for name, rx in TYPE_PATTERNS if re.search(rx, title, re.I)), None)
    return (city, kind) if city and kind else None


def fetch_events():
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "events": []}
    try:
        items = google_news(EVENT_QUERIES["en"], NEWS_FEEDS["en"]["locale"], NEWS_FEEDS["en"]["sources"] + EVENT_EXTRA_SOURCES)
        items += google_news(EVENT_QUERIES["kr"], NEWS_FEEDS["kr"]["locale"], NEWS_FEEDS["kr"]["sources"])
    except requests.RequestException as exc:
        result["error"] = str(exc)
        return result

    clusters = {}
    for it in items:
        hit = classify(it["title"])
        if not hit:
            continue
        city, kind = hit
        when = datetime.fromisoformat(it["published"]).astimezone(AST)
        it["when"] = when
        it["korean"] = bool(re.search(r"[가-힣]", it["title"]))
        clusters.setdefault((when.strftime("%Y-%m-%d"), city, kind), []).append(it)

    for (day, city, kind), members in clusters.items():
        # 같은 사건을 다룬 기사 묶음: 가장 이른 보도 시각, 한국어 제목 우선, 매체 수
        members.sort(key=lambda m: m["published"])
        lead = next((m for m in members if m["korean"]), members[0])
        place = PLACE_BY_NAME[city]
        result["events"].append({
            "date": day, "time": members[0]["when"].strftime("%H:%M"), "iso": members[0]["when"].isoformat(),
            "city": city, "region": place["region"], "type": kind, "lat": place["lat"], "lon": place["lon"],
            "title": lead["title"], "url": lead["url"], "source": lead["source"],
            "outlets": len({m["source"] for m in members}),
        })
    result["events"].sort(key=lambda e: e["iso"], reverse=True)
    result["events"] = result["events"][:15]
    result["ok"] = True
    return result


# ------------------------------------------------------------ telegram

def fetch_telegram():
    """후티 군 대변인 채널의 최근 메시지 중 사우디·사우디 지명 언급만 남긴다."""
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "channel": TELEGRAM_URL, "messages": []}
    try:
        page = get(TELEGRAM_URL, BROWSER_HEADERS).text
    except requests.RequestException as exc:
        result["error"] = str(exc)
        return result

    blocks = re.split(r'(?=<div class="tgme_widget_message_wrap)', page)
    for block in blocks:
        text = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.S)
        when = re.search(r'<time datetime="([^"]+)"', block)
        link = re.search(r'class="tgme_widget_message_date"[^>]*href="([^"]+)"', block)
        if not (text and when and link):
            continue
        body = strip_html(re.sub(r"<br\s*/?>", " ", text.group(1)))
        places = [p["name"] for p in PLACES if any(a in body for a in p["ar"]) or any(a.isascii() and re.search(rf"\b{a}\b", body, re.I) for a in p["aliases"])]
        if not places and not re.search(r"السعود|Saudi", body):
            continue
        local = datetime.fromisoformat(when.group(1)).astimezone(AST)
        result["messages"].append({
            "time": local.strftime("%Y-%m-%d %H:%M"), "iso": local.isoformat(), "places": places,
            "text": body[:260] + ("…" if len(body) > 260 else ""), "url": link.group(1),
            "translate": "https://translate.google.com/?sl=auto&tl=ko&op=translate&text=" + quote(body[:900]),
        })
    result["messages"] = sorted(result["messages"], key=lambda m: m["iso"], reverse=True)[:6]
    result["ok"] = True
    return result


# ------------------------------------------------------------ maritime

def portwatch_rows(service, portid, field):
    params = {"where": f"portid='{portid}'", "outFields": f"date,{field}", "orderByFields": "date DESC",
              "resultRecordCount": 1000, "returnGeometry": "false", "f": "json"}
    data = get(f"{PORTWATCH_BASE}/{service}/FeatureServer/0/query?" + "&".join(f"{k}={quote(str(v))}" for k, v in params.items())).json()
    if "error" in data:
        raise ValueError(f"PortWatch {portid}: {data['error'].get('message')}")
    rows = []
    for f in data["features"]:
        ts = f["attributes"]["date"]
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat() if isinstance(ts, (int, float)) else str(ts)[:10]
        rows.append((day, f["attributes"][field] or 0))
    return sorted(rows)


def fetch_maritime():
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "series": {}}
    targets = [(p["port"], p["name"] if p["name"].endswith("항") else f"{p['name']}항", "Daily_Ports_Data", "portcalls") for p in PLACES if p.get("port")]
    targets += [("chokepoint4", "밥엘만데브 해협", "Daily_Chokepoints_Data", "n_total"), ("chokepoint6", "호르무즈 해협", "Daily_Chokepoints_Data", "n_total")]
    try:
        for key, name, service, field in targets:
            rows = portwatch_rows(service, key, field)
            values = [v for _, v in rows]
            rolling7 = [sum(values[i - 6:i + 1]) for i in range(6, len(values))]
            # 최근 2주를 뺀 지난 1년의 7일 합 중앙값을 평시로 본다.
            baseline = statistics.median(rolling7[-379:-14]) if len(rolling7) > 60 else None
            r = ratio(rolling7[-1], baseline)
            result["series"][key] = {
                "name": name, "last_date": rows[-1][0], "last7": rolling7[-1], "baseline7": baseline,
                "ratio": r, "tier": tier_down(r),
                "spark": [{"date": rows[i][0], "value": rolling7[i - 6]} for i in range(len(rows) - 90, len(rows))],
            }
    except (requests.RequestException, ValueError, KeyError) as exc:
        result["error"] = str(exc)
        return result
    result["ok"] = True
    return result


# ------------------------------------------------------------ main

def main():
    previous = load_previous()
    output = {
        "generated_at": now_iso(),
        "regions": [{k: r[k] for k in ("key", "name", "label", "primary_port", "chokepoint", "center", "zoom", "box")} for r in REGIONS],
        "firms": carry_over(fetch_firms(previous.get("firms", {})), previous.get("firms", {})),
        "mofa": carry_over(fetch_mofa(), previous.get("mofa", {})),
        "news": carry_over(fetch_news(), previous.get("news", {})),
        "events": carry_over(fetch_events(), previous.get("events", {})),
        "telegram": carry_over(fetch_telegram(), previous.get("telegram", {})),
        "maritime": carry_over(fetch_maritime(), previous.get("maritime", {})),
    }
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=1)
    print(" ".join(f"{k}_ok={output[k]['ok']}" for k in ("firms", "mofa", "news", "events", "telegram", "maritime")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
