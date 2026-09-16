#!/usr/bin/env python3
"""
얀부·제다 상황판 데이터 수집.

  1. 외교부 해외안전여행(0404.go.kr) 사우디아라비아 페이지
     - 지역별 여행경보 단계 (얀부/제다가 어느 단계 지역에 속하는지)
     - 사우디 관련 안전공지 목록 + 각 공지 본문 첫 줄 요약
  2. 영국 FCDO 사우디 여행경보 (보조 신호)

실패한 소스는 이전 성공 데이터를 유지하고 ok=false, stale=true 로 표시한다.
"""
import html as htmllib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "latest.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

MOFA_BASE = "https://www.0404.go.kr"
MOFA_NTN_CD = "107"  # 사우디아라비아
MOFA_COUNTRY_URL = f"{MOFA_BASE}/ntnSafetyInfo/{MOFA_NTN_CD}/detail"
MOFA_NOTICE_URL = f"{MOFA_BASE}/bbs/safetyNtc/list?ntnCd={MOFA_NTN_CD}&pageSize=50"
FCDO_URL = "https://www.gov.uk/foreign-travel-advice/saudi-arabia"

REGIONS = [
    {"name": "얀부", "aliases": ["얀부", "Yanbu"], "lat": 24.0895, "lon": 38.0618},
    {"name": "제다", "aliases": ["제다", "젯다", "Jeddah"], "lat": 21.4858, "lon": 39.1925},
]

# 외교부 단계. 특별여행주의보는 2단계 이상·3단계 이하로 운용되므로 2.5로 둔다.
LEVELS = {
    "여행유의": 1,
    "여행자제": 2,
    "특별여행주의보": 2.5,
    "출국권고": 3,
    "여행금지": 4,
}

NOTICE_LIMIT = 8
WEEKS = 8


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def strip_html(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", htmllib.unescape(text)).strip()


def load_previous():
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------- 외교부

def parse_advisories(page):
    # 페이지에 주석 처리된 예시 <li>가 남아있어 주석을 먼저 걷어낸다.
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    block = re.search(r'<ul class="info-02">(.*?)</ul>', page, re.S)
    if not block:
        raise ValueError("info-02 블록을 찾지 못함 (페이지 구조 변경?)")
    advisories = []
    for li in re.findall(r"<li>(.*?)</li>", block.group(1), re.S):
        tag = re.search(r'<span class="box-tag-01[^"]*">(.*?)</span>', li, re.S)
        if not tag:
            continue
        level_name = strip_html(tag.group(1))
        regions = strip_html(li.replace(tag.group(0), ""))
        advisories.append({
            "level_name": level_name,
            "level": LEVELS.get(level_name),
            "regions": regions,
        })
    if not advisories:
        raise ValueError("경보 항목이 비어있음")
    return advisories


def region_level(advisories, region):
    named = [a for a in advisories if any(alias in a["regions"] for alias in region["aliases"])]
    if named:
        return max(named, key=lambda a: a["level"] or 0)
    rest = [a for a in advisories if "제외한" in a["regions"]]
    return rest[0] if rest else None


def parse_notices(page):
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    notices = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        link = re.search(r'<a href="(/bbs/safetyNtc/[^"]+)" class="btn title">(.*?)</a>', row, re.S)
        day = re.search(r"<td>\s*(\d{4}-\d{2}-\d{2})\s*</td>", row)
        if link and day:
            notices.append({
                "date": day.group(1),
                "title": strip_html(link.group(2)),
                "url": MOFA_BASE + htmllib.unescape(link.group(1)),
            })
    return notices


def fetch_summary(url):
    try:
        page = get(url)
    except requests.RequestException:
        return None
    body = re.search(r'<textarea id="textCnHtml"[^>]*>(.*?)</textarea>', page, re.S)
    if not body:
        return None
    text = strip_html(htmllib.unescape(body.group(1)))
    return text[:220] + ("…" if len(text) > 220 else "")


def weekly_counts(notices):
    monday = date.today() - timedelta(days=date.today().weekday())
    weeks = [monday - timedelta(weeks=i) for i in range(WEEKS - 1, -1, -1)]
    counter = Counter()
    for n in notices:
        d = date.fromisoformat(n["date"])
        counter[d - timedelta(days=d.weekday())] += 1
    return [{"week": w.isoformat(), "count": counter[w]} for w in weeks]


def fetch_mofa():
    result = {"ok": False, "error": None, "fetched_at": now_iso(),
              "source_url": MOFA_COUNTRY_URL, "notice_list_url": MOFA_NOTICE_URL}
    try:
        advisories = parse_advisories(get(MOFA_COUNTRY_URL))
        notices = parse_notices(get(MOFA_NOTICE_URL))
    except (requests.RequestException, ValueError) as exc:
        result["error"] = str(exc)
        return result

    notices.sort(key=lambda n: n["date"], reverse=True)
    for n in notices[:NOTICE_LIMIT]:
        n["summary"] = fetch_summary(n["url"])
        time.sleep(0.5)

    regions = []
    for region in REGIONS:
        matched = region_level(advisories, region) or {}
        regions.append({
            "name": region["name"], "lat": region["lat"], "lon": region["lon"],
            "level_name": matched.get("level_name"), "level": matched.get("level"),
        })

    result.update({
        "ok": True,
        "advisories": advisories,
        "regions": regions,
        "notices": notices[:NOTICE_LIMIT],
        "weekly_counts": weekly_counts(notices),
    })
    return result


# ---------------------------------------------------------------- FCDO

def fetch_fcdo():
    result = {"ok": False, "error": None, "fetched_at": now_iso(), "source_url": FCDO_URL}
    try:
        page = get(FCDO_URL)
    except requests.RequestException as exc:
        result["error"] = str(exc)
        return result

    if "advises against all travel to" in page:
        text = "일부 지역 전체 여행 금지 권고 (advises against all travel)"
    elif "advises against all but essential travel to" in page:
        text = "일부 지역 필수적이지 않은 여행 자제 권고 (all but essential travel)"
    else:
        text = "특별 경보 없음"
    result.update({"ok": True, "text": text})
    return result


# ---------------------------------------------------------------- main

def carry_over(current, previous, keys):
    previous_usable = previous.get("ok") or previous.get("stale")
    if current["ok"] or not previous_usable:
        return current
    for key in keys:
        if key in previous:
            current[key] = previous[key]
    current["stale"] = True
    return current


def main():
    previous = load_previous()

    mofa = carry_over(fetch_mofa(), previous.get("mofa", {}),
                      ["advisories", "regions", "notices", "weekly_counts"])
    fcdo = carry_over(fetch_fcdo(), previous.get("fcdo", {}), ["text"])

    worst = max((r for r in mofa.get("regions", []) if r.get("level")),
                key=lambda r: r["level"], default=None)

    output = {
        "generated_at": now_iso(),
        "overall": {"level": worst["level"], "level_name": worst["level_name"], "region": worst["name"]} if worst else None,
        "mofa": mofa,
        "fcdo": fcdo,
    }

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"mofa_ok={mofa['ok']} fcdo_ok={fcdo['ok']} overall={output['overall']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
