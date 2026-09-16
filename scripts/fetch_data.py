#!/usr/bin/env python3
"""
사우디 얀부/제다 위기 지수 대시보드 - 데이터 수집 스크립트.

세 가지 소스를 모아 data/latest.json 하나로 합친다.
  1. ACLED  - 분쟁 이벤트 (신뢰도 높음, API 키 필요)
  2. UKMTO  - 홍해/아덴만 해상 보안 사고 속보 (best-effort. 차단되면
              이전 데이터를 그대로 유지하고 ok=false만 표시한다)
  3. 미국무부 여행경보 등급 (best-effort. 실패하면 이전 값 유지)

실패한 소스가 있어도 전체 스크립트는 죽지 않고, 마지막으로 성공한
데이터를 유지한 채 "ok": false 로 표시한다. (graceful degrade)
"""
import json
import math
import os
import re
import sys
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

ACLED_LOOKBACK_DAYS = 90
RECENT_WINDOW_DAYS = 7


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


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def near_regions(lat, lon):
    for region in REGIONS:
        if haversine_km(lat, lon, region["lat"], region["lon"]) <= region["radius_km"]:
            return region["name"]
    return None


def weekly_buckets(events, weeks=13):
    """최근 N주간 주간 이벤트 건수."""
    today = datetime.now(timezone.utc).date()
    buckets = []
    for i in range(weeks - 1, -1, -1):
        week_start = today - timedelta(days=today.weekday() + 7 * i)
        week_end = week_start + timedelta(days=6)
        count = sum(
            1
            for e in events
            if week_start <= datetime.fromisoformat(e["date"]).date() <= week_end
        )
        buckets.append({"week": week_start.isoformat(), "count": count})
    return buckets


def get_acled_token(email, password):
    """myACLED 계정 이메일/비밀번호로 OAuth access token 발급 (24시간 유효)."""
    resp = requests.post(
        "https://acleddata.com/oauth/token",
        data={
            "username": email,
            "password": password,
            "grant_type": "password",
            "client_id": "acled",
            "scope": "authenticated",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_acled():
    """ACLED API에서 사우디 서부(얀부/제다 인근) 최근 사건을 가져온다.

    ACLED는 OAuth 토큰 방식을 쓴다. myACLED 계정의 이메일/비밀번호로
    매 실행마다 access token(24시간 유효)을 새로 발급받아 사용한다.
    (참고: https://acleddata.com/api-documentation/getting-started)
    """
    email = os.environ.get("ACLED_EMAIL")
    password = os.environ.get("ACLED_PASSWORD")
    result = {"events": [], "count_7d": 0, "count_90d_weekly": [], "ok": False,
              "fetched_at": now_iso(), "error": None}

    if not email or not password:
        result["error"] = "ACLED_EMAIL / ACLED_PASSWORD 환경변수 없음"
        return result

    try:
        token = get_acled_token(email, password)
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"토큰 발급 실패: {exc}"
        return result

    start = (datetime.now(timezone.utc) - timedelta(days=ACLED_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    params = {
        "country": "Saudi Arabia",
        "event_date": f"{start}|{end}",
        "event_date_where": "BETWEEN",
        "limit": 0,
    }
    try:
        resp = requests.get(
            "https://acleddata.com/api/acled/read",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data", [])
    except Exception as exc:  # noqa: BLE001 - 실패해도 파이프라인은 계속
        result["error"] = str(exc)
        return result

    events = []
    for row in rows:
        try:
            lat, lon = float(row["latitude"]), float(row["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        region = near_regions(lat, lon)
        if not region:
            continue
        events.append({
            "date": row.get("event_date"),
            "lat": lat,
            "lon": lon,
            "region": region,
            "type": row.get("event_type"),
            "notes": (row.get("notes") or "")[:280],
            "source": "ACLED",
        })

    events.sort(key=lambda e: e["date"], reverse=True)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECENT_WINDOW_DAYS)).date()
    count_7d = sum(1 for e in events if datetime.fromisoformat(e["date"]).date() >= cutoff)

    result.update({
        "events": events,
        "count_7d": count_7d,
        "count_90d_weekly": weekly_buckets(events),
        "ok": True,
        "error": None,
    })
    return result


def fetch_ukmto():
    """UKMTO 홍해/아덴만 사고 속보 (best-effort).

    UKMTO 사이트는 Cloudflare 봇 차단이 걸려있어 자동화 환경에서
    자주 막힐 수 있다. 실패 시 ok=false만 반환하고, 이전 데이터
    유지는 main()에서 처리한다.
    """
    result = {"events": [], "count_7d": 0, "ok": False, "fetched_at": now_iso(), "error": None}
    try:
        resp = requests.get("https://www.ukmto.org/indian-ocean/reports", headers=HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"fetch 실패(차단 가능성): {exc}"
        return result

    # 페이지 구조가 바뀌면 이 파싱은 깨질 수 있다 - best effort.
    # "DD Month YYYY" 형태의 날짜와 그 주변 텍스트를 사건으로 취급한다.
    date_pattern = re.compile(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})")
    matches = date_pattern.findall(html)
    if not matches:
        result["error"] = "페이지에서 사건 날짜 패턴을 찾지 못함 (구조 변경 가능성)"
        return result

    result["ok"] = True
    result["raw_dates_found"] = len(matches)
    # 정확한 위경도/제목 파싱은 실제 페이지 구조를 보고 추후 보강 필요.
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


def compute_risk(acled, ukmto, advisory):
    """세 신호를 종합한 단순 3단계 위험도. 규칙은 일부러 단순하게 유지."""
    recent = (acled.get("count_7d") or 0) + (ukmto.get("count_7d") or 0)
    level = advisory.get("level") or 2

    if recent >= 3 or level >= 4:
        return "alert", "경계"
    if recent >= 1 or level >= 3:
        return "caution", "주의"
    return "calm", "평온"


def main():
    previous = load_previous() or {}

    acled = fetch_acled()
    ukmto = fetch_ukmto()
    advisory = fetch_travel_advisory()

    # graceful degrade: 실패한 소스는 이전 데이터를 유지하고 ok/error만 갱신
    if not ukmto["ok"] and previous.get("ukmto", {}).get("events"):
        ukmto["events"] = previous["ukmto"]["events"]
        ukmto["count_7d"] = previous["ukmto"].get("count_7d", 0)
        ukmto["stale"] = True

    if not advisory["ok"] and previous.get("advisory", {}).get("level") is not None:
        advisory["level"] = previous["advisory"]["level"]
        advisory["text"] = previous["advisory"]["text"]
        advisory["stale"] = True

    if not acled["ok"] and previous.get("acled", {}).get("events"):
        acled["events"] = previous["acled"]["events"]
        acled["count_7d"] = previous["acled"].get("count_7d", 0)
        acled["count_90d_weekly"] = previous["acled"].get("count_90d_weekly", [])
        acled["stale"] = True

    risk_level, risk_label_ko = compute_risk(acled, ukmto, advisory)

    output = {
        "generated_at": now_iso(),
        "risk_level": risk_level,
        "risk_label_ko": risk_label_ko,
        "advisory": advisory,
        "acled": acled,
        "ukmto": ukmto,
        "regions": REGIONS,
    }

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"risk={risk_level} acled_ok={acled['ok']} ukmto_ok={ukmto['ok']} advisory_ok={advisory['ok']}")


if __name__ == "__main__":
    sys.exit(main())
