#!/usr/bin/env python3
"""
사우디 얀부/제다 위기 지수 대시보드 - 데이터 수집 스크립트.

자동 수집(best-effort, 실패해도 죽지 않고 이전 데이터 유지):
  1. GDELT DOC 2.0 API - 얀부/제다/홍해/후티 관련 최신 뉴스 헤드라인
     (무료, 키 불필요, ~15분 단위 갱신. ACLED API는 개인 계정에는
     막혀있어(Open 등급=API 접근 불가) 포기하고 이걸로 대체함)
  2. 미국무부(travel.state.gov) 사우디아라비아 여행경보 등급

자동 수집하지 않는 것(신뢰도/약관 문제로 링크만 제공):
  - ACLED Yemen Conflict Monitor, UKMTO, 외교부/대사관, Luberef 공시 등
    -> EXTERNAL_LINKS 로 정적 제공
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "latest.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

REGIONS = [
    {"name": "얀부", "lat": 24.0895, "lon": 38.0618, "radius_km": 80},
    {"name": "제다", "lat": 21.4858, "lon": 39.1925, "radius_km": 80},
]

GDELT_QUERY = (
    '(Yanbu OR Jeddah OR Luberef) '
    '("Houthi attack" OR "drone attack" OR "missile strike" OR "Houthi strike" '
    'OR "pipeline explosion" OR "Red Sea attack" OR "oil pipeline" OR "under attack")'
)
NEWS_LOOKBACK_DAYS = 7

EXTERNAL_LINKS = [
    {
        "group": "국제 공식/전문 소스",
        "name": "ACLED Yemen Conflict Monitor (홍해 공격 지도 포함)",
        "url": "https://acleddata.com/monitor/yemen-conflict-monitor",
        "description": "ACLED가 직접 운영하는 예멘/홍해 분쟁 전용 대시보드. 주간 갱신, 홍해 공격 전용 지도 별도 제공.",
    },
    {
        "group": "국제 공식/전문 소스",
        "name": "UKMTO 홍해·아덴만 해상 보안 속보",
        "url": "https://www.ukmto.org/",
        "description": "영국 해군 해상무역작전실의 실시간 해상 사고 속보. 자동 수집은 차단되어 직접 확인 필요.",
    },
    {
        "group": "국제 공식/전문 소스",
        "name": "미국무부 사우디아라비아 여행경보 (원문)",
        "url": "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/saudi-arabia-travel-advisory.html",
        "description": "이 대시보드의 여행경보 등급 출처 원문.",
    },
    {
        "group": "국제 공식/전문 소스",
        "name": "영국 FCDO 사우디아라비아 여행 정보",
        "url": "https://www.gov.uk/foreign-travel-advice/saudi-arabia",
        "description": "영국 외무부의 사우디아라비아 여행 권고.",
    },
    {
        "group": "대한민국 관련",
        "name": "외교부 해외안전여행 (국가별 정보)",
        "url": "https://www.0404.go.kr",
        "description": "사우디아라비아 검색 시 대한민국 정부의 공식 여행경보 단계와 공지를 확인할 수 있음.",
    },
    {
        "group": "대한민국 관련",
        "name": "주사우디아라비아 대한민국대사관",
        "url": "https://overseas.mofa.go.kr/sa-ko/index.do",
        "description": "공지사항/안전공지 게시판에서 현지 대사관의 공식 안내를 확인.",
    },
    {
        "group": "Luberef(얀부 아람코 계열)",
        "name": "Luberef 공식 뉴스/공시 (사건·안전 정보 아님, 참고용)",
        "url": "https://luberef.com/en/news",
        "description": "일반 기업 홍보·공시 페이지일 뿐 안전/사고 관련 실시간 채널이 아닙니다. 사기업 특성상 사건 관련 정보는 공개적으로 얻기 어려워, 위 뉴스 언급량 검색어에 'Luberef/refinery' 키워드를 포함해 대신 감시합니다.",
    },
]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_previous():
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def fetch_gdelt():
    """GDELT DOC 2.0 API에서 얀부/제다/홍해/후티 관련 최신 뉴스를 가져온다.

    동일 제목이 낯선 도메인 여러 곳에 동시에 뜨는 경우(콘텐츠 파밍/
    역정보 확산 패턴)가 흔해서, 제목 기준으로 중복 제거한 뒤
    "distinct 헤드라인 수"를 신호로 쓴다.
    """
    result = {"events": [], "count_recent": 0, "daily_counts": [], "ok": False,
              "fetched_at": now_iso(), "error": None}

    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": GDELT_QUERY,
        "mode": "artlist",
        "format": "json",
        "maxrecords": 75,
        "timespan": f"{NEWS_LOOKBACK_DAYS}d",
        "sort": "datedesc",
    }

    payload = None
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if resp.status_code == 429:
                last_error = "rate limited (429)"
                time.sleep(5)
                continue
            resp.raise_for_status()
            payload = resp.json()
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            time.sleep(3)

    if payload is None:
        result["error"] = last_error or "알 수 없는 오류"
        return result

    articles = payload.get("articles", [])
    seen_titles = set()
    events = []
    daily = {}
    for a in articles:
        title = (a.get("title") or "").strip()
        key = title.lower()
        seendate = a.get("seendate")  # e.g. 20260911T223000Z
        if not title or not seendate:
            continue
        try:
            dt = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ")
        except ValueError:
            continue
        day = dt.date().isoformat()
        daily[day] = daily.get(day, 0) + 1  # 중복 포함 - 언론 보도량 자체도 신호

        if key in seen_titles:
            continue
        seen_titles.add(key)
        events.append({
            "date": dt.strftime("%Y-%m-%d %H:%M UTC"),
            "title": title,
            "domain": a.get("domain"),
            "url": a.get("url"),
        })

    events.sort(key=lambda e: e["date"], reverse=True)
    today = datetime.now(timezone.utc).date()
    daily_counts = []
    for i in range(NEWS_LOOKBACK_DAYS - 1, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        daily_counts.append({"date": day, "count": daily.get(day, 0)})

    result.update({
        "events": events[:12],
        "count_recent": len(events),
        "daily_counts": daily_counts,
        "ok": True,
        "error": None,
    })
    return result


def fetch_travel_advisory():
    """미국무부 사우디아라비아 여행경보 등급 (best-effort, RSS 없음 → 페이지 파싱)."""
    result = {"level": None, "text": None, "source": "US Department of State",
              "ok": False, "fetched_at": now_iso(), "error": None}
    url = "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/saudi-arabia-travel-advisory.html"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"fetch 실패: {exc}"
        return result

    match = re.search(r"Level\s+(\d)\s*:?\s*([^<\n]{0,80})", html)
    if not match:
        result["error"] = "페이지에서 Level 표기를 찾지 못함 (구조 변경 가능성)"
        return result

    result.update({
        "level": int(match.group(1)),
        "text": f"Level {match.group(1)}: {match.group(2).strip()}",
        "ok": True,
        "error": None,
    })
    return result


def compute_risk(advisory):
    """위험도 배지는 신뢰도가 검증된 여행경보 등급만으로 산정한다.

    GDELT 뉴스 언급량은 테스트 결과 키워드 조합만으로는 무관한 기사가
    다수 섞여(예: F1 사우디 GP 기사가 'Jeddah'로 매칭) 배지 산정에
    쓰기엔 신뢰도가 부족함을 확인함. 그래서 배지에는 반영하지 않고
    화면 하단에 원문 그대로(참고용, 직접 판단 필요)만 노출한다.
    """
    level = advisory.get("level") or 2
    if level >= 4:
        return "alert", "경계"
    if level == 3:
        return "caution", "주의"
    return "calm", "평온"


def main():
    previous = load_previous() or {}

    news = fetch_gdelt()
    advisory = fetch_travel_advisory()

    # graceful degrade: 실패한 소스는 이전 데이터를 유지하고 ok/error만 갱신
    if not news["ok"] and previous.get("news", {}).get("events"):
        news["events"] = previous["news"]["events"]
        news["count_recent"] = previous["news"].get("count_recent", 0)
        news["daily_counts"] = previous["news"].get("daily_counts", [])
        news["stale"] = True

    if not advisory["ok"] and previous.get("advisory", {}).get("level") is not None:
        advisory["level"] = previous["advisory"]["level"]
        advisory["text"] = previous["advisory"]["text"]
        advisory["stale"] = True

    risk_level, risk_label_ko = compute_risk(advisory)

    output = {
        "generated_at": now_iso(),
        "risk_level": risk_level,
        "risk_label_ko": risk_label_ko,
        "advisory": advisory,
        "news": news,
        "external_links": EXTERNAL_LINKS,
        "regions": REGIONS,
    }

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"risk={risk_level} news_ok={news['ok']} count_recent={news.get('count_recent')} advisory_ok={advisory['ok']}")


if __name__ == "__main__":
    sys.exit(main())
