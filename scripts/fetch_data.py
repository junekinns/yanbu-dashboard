#!/usr/bin/env python3
"""
Red Sea Watch 데이터 수집. 도시 단위 상황표에 들어갈 파생 신호를 만든다.

  mofa       외교부 해외안전여행 사우디 경보 단계(지점별) + 단계 변경 이력(90일) + 안전공지 템포
  events     공격·요격·경보 보도를 (날짜·도시·유형)으로 묶어 30일 누적, 도시별 7일/이전 7일 템포
  telegram   후티 군 대변인 공식 Telegram 채널 — 사우디 지명 언급 메시지 14일 누적, 7일 표적 언급 순위
  firms      NASA FIRMS VIIRS 위성 열 감지 — 지도 화점 레이어(상시 플레어 제외)
  news       Google News RSS, 공신력 있는 국내·해외 매체만 5건씩
  flights    (실험) FlightRadar24 비공식 피드 — 홍해 회랑 상공 항공편 수
  notams     (선택) FAA NOTAM — 사우디 공역 제한, GitHub Secrets에 자격증명이 있을 때만

키는 서버 측(Actions secrets)만. 실패한 소스는 이전 성공 데이터를 유지하고 stale=true 로 표시.
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
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlencode

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "latest.json")
HEADERS = {"User-Agent": "yanbu-dashboard/1.0 (github.com/junekinns/yanbu-dashboard)"}
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
TODAY = datetime.now(timezone.utc).date()
AST = timezone(timedelta(hours=3))  # 사우디 현지시각
TODAY_AST = datetime.now(AST).date()  # 사건·메시지 이력의 날짜 창 기준

# 배율 대신 3단계 배지로 단순화해 보여준다.
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
# 표에 항상 보이는 도시: 가족(얀부), 가까운 대도시·공항(제다), 대사관(리야드), 아람코 본사(다란·담맘).
PINNED = ["얀부", "제다", "리야드", "다란", "담맘"]
# 위기 단계 1~5. 점수 → 단계 문턱. 규칙은 crisis_summary()에 전부 있고 화면에 근거를 나열한다.
CRISIS_LEVELS = [(0, "평온"), (2, "주의"), (4, "경계"), (6, "심각"), (8, "위급")]

MOFA_BASE = "https://www.0404.go.kr"
MOFA_COUNTRY_URL = f"{MOFA_BASE}/ntnSafetyInfo/107/detail"
MOFA_NOTICE_URL = f"{MOFA_BASE}/bbs/safetyNtc/list?ntnCd=107&pageSize=100"  # 8주 창이 50건을 넘는 시기가 있다
FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_7d.csv"
GOOGLE_NEWS_URL = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
TELEGRAM_URL = "https://t.me/s/army21ye"  # 예멘군(후티) 대변인 야히야 사리 공식 채널
SAUDI_BOX = (16.0, 32.5, 34.0, 56.0)
# FAA NOTAM API. 자격증명은 GitHub Actions secrets → 환경변수로만 들어온다.
NOTAM_URL = "https://external-api.faa.gov/notamapi/v1/notams"
NOTAM_LOCATIONS = ["OEJN", "OERK", "OEDF", "OEMA", "OEJD"]  # 제다·리야드·담맘·메디나 공항 + 사우디 FIR
NOTAM_KINDS = [
    ("공역 폐쇄", r"AIRSPACE.*(CLSD|CLOSED)|CLOSED.*AIRSPACE"),
    ("제한/금지", r"RESTRICTED|PROHIBITED|QRTCA|QRPCA|QRRCA"),
    ("위험구역", r"DANGER|QRDCA"),
    ("사격/미사일", r"MISSILE|ROCKET|FIRING|\bGUN"),
    ("UAS", r"\bUAS\b|DRONE"),
    ("GPS 간섭", r"GPS.*(INTERFER|JAM)|GNSS"),
]
# 밥엘만데브~제다 사이 홍해 회랑. FlightRadar24 bounds 포맷은 "북,남,서,동".
FLIGHTS_URL = "https://data-cloud.flightradar24.com/zones/fcgi/feed.js"
FLIGHTS_PARAMS = {"bounds": "24,12,35,44", "faa": 1, "satellite": 1, "mlat": 1, "flarm": 1,
                  "adsb": 1, "gnd": 0, "air": 1, "vehicles": 0, "estimated": 1, "maxage": 900, "gliders": 0, "stats": 0}

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
# 매시간은 3일 창이면 충분(이력은 누적). 최초 시드 때만 EVENT_DAYS=14 — Google News RSS가 100건 캡이라 영문은 하루치만 온다.
EVENT_DAYS = int(os.environ.get("EVENT_DAYS", "3"))
event_query = lambda lang: EVENT_QUERIES[lang].replace("when:3d", f"when:{EVENT_DAYS}d")
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
# 지도 아이콘용. 제목에 무기가 드러날 때만 — 없으면 None(일반 아이콘). 궤적은 데이터가 없어 그리지 않는다.
WEAPON_PATTERNS = [("드론", r"드론|drone|UAV|무인기"), ("미사일", r"미사일|missile|탄도|순항|ballistic|cruise")]

# 외교부 단계. 특별여행주의보는 2단계 이상·3단계 이하로 운용되므로 2.5.
LEVELS = {"여행유의": 1, "여행자제": 2, "특별여행주의보": 2.5, "출국권고": 3, "여행금지": 4}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, headers=HEADERS, timeout=60):
    # 정부 사이트가 해외 IP에 간헐적으로 연결 타임아웃을 내서 몇 번 다시 시도한다.
    # 연결은 10초면 충분하고, 긴 timeout은 큰 파일(FIRMS 44MB) 읽기용 — 연결 자체가 안 되는데
    # 180초×3회를 기다리면 GitHub Actions 한 번이 10분을 넘긴다.
    for attempt in (1, 2, 3):
        try:
            resp = requests.get(url, headers=headers, timeout=(10, timeout))
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
    # 실패한 결과의 빈 컨테이너("regions": {}, "events": [] 등)가 이전 값을 덮어쓰지 않게
    # 상태 필드만 가져온다. 특히 firms.history(평시 계산용 90일 이력)가 한 번의 실패로 날아가면 안 된다.
    kept = {k: v for k, v in previous.items() if k not in ("ok", "error", "fetched_at")}
    return {**kept, "ok": False, "error": current.get("error"), "fetched_at": current["fetched_at"], "stale": True}


def merge_history(prev, new, key, keep_days, day_of, update=None):
    """이력 병합. 새 항목이 같은 키의 기존 항목을 대체하되 update(old, new)가 있으면 그 결과를 쓴다.
    keep_days보다 오래된 항목은 버리고 최신순으로 돌려준다."""
    merged = {key(item): item for item in prev}
    for item in new:
        k = key(item)
        merged[k] = update(merged[k], item) if (update and k in merged) else item
    floor = (TODAY_AST - timedelta(days=keep_days)).isoformat()
    kept = [item for item in merged.values() if day_of(item) >= floor]
    return sorted(kept, key=lambda item: (day_of(item), item.get("iso", item.get("at", ""))), reverse=True)


# ------------------------------------------------------------ firms

def fetch_firms(previous):
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "source_url": FIRMS_URL, "hotspots": []}
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

    # 타일·평시는 없앴다(며칠에 한 번 바뀌는 그래프는 장식이라는 판단). 지도 화점 레이어용으로만 남긴다.
    result["hotspots"] = sorted(anomalous, key=lambda h: (h["date"], h["time"]))[-500:]
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
        # 요약은 있으면 좋은 정도라 짧게. 정부 사이트가 해외 IP에 느릴 때 3건×재시도로 몇 분을 잡아먹지 않게.
        body = re.search(r'<textarea id="textCnHtml"[^>]*>(.*?)</textarea>', get(url, BROWSER_HEADERS, timeout=15).text, re.S)
    except requests.RequestException:
        return None
    if not body:
        return None
    text = strip_html(htmllib.unescape(body.group(1)))
    return text[:200] + ("…" if len(text) > 200 else "")


def fetch_mofa(previous):
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

    places = [{"name": p["name"], "lat": p["lat"], "lon": p["lon"],
               **{k: place_level(advisories, p).get(k) for k in ("level", "level_name")}} for p in PLACES if p["lat"]]

    # 교민에게 가장 실질적인 사건은 "내 도시의 단계가 바뀐 것". 이전 수집과 비교해 변경만 90일 이력으로.
    # 수집이 실패한 실행은 여기 오지 않으므로(위에서 return) 실패가 가짜 변경을 만들지 않는다.
    prev_levels = {p["name"]: p.get("level") for p in previous.get("places", [])}
    prev_names = {p["name"]: p.get("level_name") for p in previous.get("places", [])}
    new_changes = [
        {"city": p["name"], "from": prev_levels[p["name"]], "from_name": prev_names[p["name"]],
         "to": p["level"], "to_name": p["level_name"], "at": result["fetched_at"]}
        for p in places
        if isinstance(p["level"], (int, float)) and isinstance(prev_levels.get(p["name"]), (int, float)) and prev_levels[p["name"]] != p["level"]
    ]
    changes = merge_history(previous.get("changes", []), new_changes, key=lambda c: (c["city"], c["at"]), keep_days=90, day_of=lambda c: c["at"][:10])

    result.update({
        "ok": True,
        "advisories": advisories,
        "places": places,
        "changes": changes,
        "tracking_since": previous.get("tracking_since") or result["fetched_at"],
        "notices": notices[:3],
        "last7d": counts[-1],
        "baseline": baseline,
        # 조용한 6주 뒤 첫 급증에서 평시 0 → '평시'가 되지 않게 하한 1.
        "tier": tier_up(ratio(counts[-1], max(baseline, 1)), labels=("급증", "증가", "평시")),
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


def fetch_events(previous):
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "events": []}
    try:
        items = google_news(event_query("en"), NEWS_FEEDS["en"]["locale"], NEWS_FEEDS["en"]["sources"] + EVENT_EXTRA_SOURCES)
        items += google_news(event_query("kr"), NEWS_FEEDS["kr"]["locale"], NEWS_FEEDS["kr"]["sources"])
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
        weapon = next((w for w, rx in WEAPON_PATTERNS if any(re.search(rx, m["title"], re.I) for m in members)), None)
        result["events"].append({
            "date": day, "time": members[0]["when"].strftime("%H:%M"), "iso": members[0]["when"].isoformat(),
            "city": city, "type": kind, "weapon": weapon, "lat": place["lat"], "lon": place["lon"],
            "title": lead["title"], "url": lead["url"], "source": lead["source"],
            "outlets": len({m["source"] for m in members}),
        })
    # 30일 누적. 같은 사건이 다시 오면 매체 수는 큰 값, 시각은 더 이른 값, 대표 기사는 기존 유지.
    def refresh(old, new):
        earlier = new["iso"] < old["iso"]
        return {**old, "outlets": max(old["outlets"], new["outlets"]), "weapon": old.get("weapon") or new.get("weapon"),
                **({"time": new["time"], "iso": new["iso"]} if earlier else {})}
    events = merge_history(previous.get("events", []), result["events"],
                           key=lambda e: (e["date"], e["city"], e["type"]), keep_days=30, day_of=lambda e: e["date"], update=refresh)

    # 도시별 템포: 최근 7일 vs 이전 7일(사우디 현지 날짜). 이력이 14일 미만이면 비교하지 않는다 — 없는 비교를 0으로 꾸미지 않기.
    today = TODAY_AST
    w7 = {(today - timedelta(days=i)).isoformat() for i in range(7)}
    p7 = {(today - timedelta(days=i)).isoformat() for i in range(7, 14)}
    dates = [e["date"] for e in events]
    history_days = (today - date.fromisoformat(min(dates))).days + 1 if dates else 0
    tempo = {}
    for p in PLACES:
        if not p["lat"]:
            continue
        mine = [e for e in events if e["city"] == p["name"]]
        c7 = Counter(e["type"] for e in mine if e["date"] in w7)
        cp = Counter(e["type"] for e in mine if e["date"] in p7) if history_days >= 14 else None
        tempo[p["name"]] = {"7d": dict(c7), "total7d": sum(c7.values()),
                            "prev7d": dict(cp) if cp is not None else None,
                            "prev_total": sum(cp.values()) if cp is not None else None}
    result.update({"events": events, "tempo": tempo, "history_days": history_days,
                   "history_since": min(dates) if dates else None, "today": today.isoformat()})
    result["ok"] = True
    return result


# ------------------------------------------------------------ telegram

MYMEMORY_URL = "https://api.mymemory.translated.net/get"


def translate_ar_ko(text):
    """MyMemory 무료 번역 API(무키). 실패하면 None을 돌려주고 원문만 남긴다."""
    try:
        resp = get(f"{MYMEMORY_URL}?q={quote(text)}&langpair=ar|ko", timeout=15)
        data = resp.json()
        translated = data.get("responseData", {}).get("translatedText")
        return translated if translated and "MYMEMORY WARNING" not in translated else None
    except (requests.RequestException, ValueError):
        return None


def fetch_telegram(previous):
    """후티 군 대변인 채널의 최근 메시지 중 사우디·사우디 지명 언급만 남기고 한국어로 번역한다."""
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
        original = body[:400] + ("…" if len(body) > 400 else "")
        key = re.sub(r"\s+", "", body)[:60]
        if any(m["_key"] == key for m in result["messages"]):
            continue
        result["messages"].append({
            "time": local.strftime("%Y-%m-%d %H:%M"), "iso": local.isoformat(), "places": places,
            "text_ar": original, "text_ko": None, "url": link.group(1), "_key": key,
        })
    for m in result["messages"]:
        del m["_key"]
    # 채널은 하루 ~18건, 미리보기는 ~1일치만 보여주므로 매시간 수집분을 14일 누적한다.
    # 같은 url이 다시 오면 새 원문을 쓰되, 원문이 그대로면 이전 번역을 재사용(MyMemory 무료 한도 절약).
    keep_ko = lambda old, new: {**new, "text_ko": old.get("text_ko") if old.get("text_ar") == new["text_ar"] else None}
    result["messages"] = merge_history(previous.get("messages", []), result["messages"],
                                       key=lambda m: m["url"], keep_days=14, day_of=lambda m: m["iso"][:10], update=keep_ko)
    for m in result["messages"][:6]:  # 화면에 보이는 최신 6건만 번역
        if m.get("text_ko"):
            continue
        m["text_ko"] = translate_ar_ko(m["text_ar"][:480])  # MyMemory 무료 한도는 요청당 500자
        time.sleep(0.3)

    # 후티는 공격 전에 도시를 지명한다. 최근 7일 언급을 메시지당 1회로 센 순위 — 이 대시보드만 가진 선행 신호.
    since = datetime.now(timezone.utc) - timedelta(days=7)
    mentions = Counter(city for m in result["messages"] if datetime.fromisoformat(m["iso"]) >= since for city in set(m["places"]))
    result["mentions7d"] = dict(mentions.most_common())
    result["ok"] = True
    return result


# ------------------------------------------------------------ notams (선택)
#
# 공역 폐쇄·제한 NOTAM은 공식 경보보다 먼저 나오는 진짜 선행 신호. FAA NOTAM API는
# 수동 승인이라 자격증명이 없을 수 있다 — 없으면 "비활성"이지 실패가 아니다.
# 응답 필드 경로는 첫 실제 응답으로 확정한다(specs/003 research.md §5). .get() 체인으로 방어.

def fetch_notams(previous):
    cid, sec = os.environ.get("FAA_CLIENT_ID"), os.environ.get("FAA_CLIENT_SECRET")
    if not (cid and sec):
        return {"ok": True, "enabled": False, "fetched_at": now_iso()}
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "enabled": True, "locations": NOTAM_LOCATIONS, "items": []}
    headers = {**HEADERS, "client_id": cid, "client_secret": sec}
    try:
        for loc in NOTAM_LOCATIONS:
            data = get(f"{NOTAM_URL}?icaoLocation={loc}&responseFormat=geoJson&pageSize=100", headers, timeout=30).json()
            for it in data.get("items", []):
                n = it.get("properties", {}).get("coreNOTAMData", {}).get("notam", {})
                text = re.sub(r"\s+", " ", str(n.get("text", "")))
                kind = next((k for k, rx in NOTAM_KINDS if re.search(rx, text, re.I)), None)
                if not kind:
                    continue
                result["items"].append({"location": n.get("location") or loc, "number": n.get("number"),
                                        "effective_start": n.get("effectiveStart"), "effective_end": n.get("effectiveEnd"),
                                        "kind": kind, "text": text[:200]})
            time.sleep(0.5)
    except (requests.RequestException, ValueError) as exc:
        result["error"] = str(exc)  # URL·상태만 담긴다. 자격증명은 헤더라 메시지에 안 들어감.
        return result
    result["ok"] = True
    return result


# ------------------------------------------------------------ flights (실험적)
#
# 항공사가 위협을 인지하면 공식 경보보다 먼저 조용히 항로를 우회하는 경향이 있다는
# 가설로 시도해보는 실험적 지표. OpenSky Network(공식 무료 API)를 먼저 테스트했으나
# 사우디·홍해 상공에 자원봉사자 지상 수신기가 거의 없어(제다·리야드 공항 반경도
# 실시간 조회 0건) 기각. FlightRadar24는 위성 ADS-B(Aireon)까지 합쳐 같은 박스에서
# 실제로 수십 대가 잡혀 채택했지만, 이건 공식 API가 아니라 지도 페이지가 자체적으로
# 쓰는 비공식 엔드포인트라 야후 파이낸스 때처럼 GitHub Actions IP가 언제든 차단될
# 수 있다(그레이스풀 디그레이드로 이전 값 유지, 막히면 조용히 뺄 것).

def fetch_flights(previous):
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "source_url": FLIGHTS_URL}
    try:
        data = get(f"{FLIGHTS_URL}?{urlencode(FLIGHTS_PARAMS)}", BROWSER_HEADERS, timeout=20).json()
        count = sum(1 for k, v in data.items() if k not in ("full_count", "version", "stats") and isinstance(v, list))
    except (requests.RequestException, ValueError) as exc:
        result["error"] = str(exc)
        return result

    # 매시간 스냅샷. 항공편 수는 밤낮 차이가 커서 같은 UTC 시각의 과거 값끼리만 비교한다(14일 보관).
    now_key = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
    history = dict(sorted({**previous.get("history", {}), now_key: count}.items())[-336:])
    same_hour = [c for k, c in history.items() if k != now_key and k[-2:] == now_key[-2:]]
    baseline = statistics.median(same_hour) if len(same_hour) >= 3 else None
    result.update({
        "ok": True,
        "count": count,
        "baseline": baseline,
        "baseline_n": len(same_hour),
        "tier": tier_down(ratio(count, baseline)),
        "history": history,
    })
    return result


# ------------------------------------------------------------ 위기 단계 (파생)
#
# "들어가자마자 위기 정도를 알 수 있는 숫자 하나". 새 데이터가 아니라 위 소스들의 점수 합이고,
# 어떤 항목이 점수를 냈는지 reasons에 전부 적어 화면에 그대로 보여준다 — 근거 없는 숫자는 장식이다.

def crisis_summary(output, previous):
    mofa, ev, tg = output.get("mofa", {}), output.get("events", {}), output.get("telegram", {})
    now = datetime.now(timezone.utc)
    score, reasons = 0, []

    levels = {p["name"]: p.get("level") or 0 for p in mofa.get("places", [])}
    top = max(levels.values(), default=0)
    if top >= 4:
        cities = sorted(n for n, l in levels.items() if l >= 4)
        score += 4
        reasons.append(f"여행금지 {len(cities)}곳 ({' · '.join(cities)})")
    elif top >= 3:
        cities = [n for n, l in levels.items() if l >= 3]
        pinned = [c for c in PINNED if c in cities]
        score += 2
        reasons.append(f"출국권고 {len(cities)}곳" + (f" — {' · '.join(pinned)} 포함" if pinned else ""))
    rest = [l for l in levels.values() if 0 < l < 3]
    if rest and statistics.median(rest) >= 2.5:
        score += 1
        reasons.append("그 외 전 지역 특별여행주의보")

    recent = [e for e in ev.get("events", []) if (now - datetime.fromisoformat(e["iso"])).total_seconds() <= 72 * 3600]
    hits = [e for e in recent if e["type"] in ("피격", "공습")]
    if hits:
        score += 2
        reasons.append(f"72시간 내 피격·공습 {len(hits)}건 ({' · '.join(sorted({e['city'] for e in hits}))})")
    elif recent:
        score += 1
        reasons.append(f"72시간 내 경보·요격 {len(recent)}건 ({' · '.join(sorted({e['city'] for e in recent}))})")
    tempo = ev.get("tempo", {})
    total7 = sum(t["total7d"] for t in tempo.values())
    prev = [t["prev_total"] for t in tempo.values() if t.get("prev_total") is not None]
    if prev and total7 >= 3 and total7 >= 2 * max(1, sum(prev)):
        score += 1
        reasons.append(f"사건 7일 {total7}건 — 이전 7일 {sum(prev)}건의 2배 이상")

    mentions = tg.get("mentions7d", {})
    pinned_m = [c for c in PINNED if mentions.get(c)]
    if pinned_m:
        score += 1
        reasons.append(f"후티가 7일 내 {' · '.join(pinned_m)} 지목")
    if mentions and max(mentions.values()) >= 5:
        c = max(mentions, key=mentions.get)
        score += 1
        reasons.append(f"후티 표적 언급 집중 — {c} {mentions[c]}회/7일")

    ups = [c for c in mofa.get("changes", [])
           if (now - datetime.fromisoformat(c["at"])).days < 7 and (c.get("to") or 0) > (c.get("from") or 0)]
    if ups:
        score += 1
        reasons.append(f"7일 내 단계 상향 {len(ups)}건 ({' · '.join(sorted({c['city'] for c in ups}))})")

    level = max(i for i, (threshold, _) in enumerate(CRISIS_LEVELS, start=1) if score >= threshold)
    history = dict(sorted({**previous.get("history", {}), TODAY_AST.isoformat(): level}.items())[-90:])
    return {"level": level, "label": CRISIS_LEVELS[level - 1][1], "score": score, "reasons": reasons,
            "pinned": PINNED, "history": history, "computed_at": now_iso(),
            "inputs_ok": {k: bool(output.get(k, {}).get("ok")) for k in ("mofa", "events", "telegram")}}


# ------------------------------------------------------------ main
#
# "시장 반응"(아람코 주가·타다울 지수) 지표는 시도했다가 뺐다: 야후
# 파이낸스 비공식 API가 GitHub Actions IP를 지속적으로 차단(429)했고,
# Stooq·MarketWatch·WSJ·사우디거래소 공식 사이트도 전부 봇 차단
# (Cloudflare/DataDome/Anubis)에 막혀 무료·무키로는 안정적인 대안이
# 없었다. 자세한 내용은 README "시도했지만 버린 것" 참고.

def safe(fetch, previous):
    # 예상 밖 예외(RSS item에 <title>이 없어 AttributeError, PortWatch 7행 미만에 IndexError 등)
    # 하나가 그 시간의 전 소스 갱신을 막지 않게 한다. 함수 안의 세밀한 except는 더 좋은 메시지를 위해 그대로.
    try:
        result = fetch(previous)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "fetched_at": now_iso()}
    if result["ok"]:
        result["last_ok_at"] = result["fetched_at"]
    return result


FETCHERS = {
    "mofa": fetch_mofa,
    "events": fetch_events,
    "telegram": fetch_telegram,
    "firms": fetch_firms,
    "news": lambda previous: fetch_news(),
    "flights": fetch_flights,
    "notams": fetch_notams,
}


def main():
    previous = load_previous()
    output = {"generated_at": now_iso()}
    for key, fetch in FETCHERS.items():
        prev = previous.get(key, {})
        started = time.monotonic()
        output[key] = carry_over(safe(fetch, prev), prev)
        # Actions 로그에서 어느 소스가 느린지/막혔는지 바로 보이게.
        print(f"{key}: ok={output[key]['ok']} {time.monotonic() - started:.1f}s" + (f" error={output[key]['error']}" if output[key].get("error") else ""), flush=True)
    try:
        output["summary"] = crisis_summary(output, previous.get("summary", {}))
    except Exception as exc:  # 파생 계산이 깨져도 원천 데이터 저장은 막지 않는다
        output["summary"] = {**previous.get("summary", {}), "stale": True, "error": f"{type(exc).__name__}: {exc}"}
    print(f"summary: level={output['summary'].get('level')} score={output['summary'].get('score')} reasons={len(output['summary'].get('reasons', []))}", flush=True)
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=1)
    print(" ".join(f"{k}_ok={output[k]['ok']}" for k in FETCHERS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
